"""Integration smoke tests for Phase 4.16 RRF hybrid retrieval."""

from __future__ import annotations

pytest_plugins = ["tests.database.conftest"]

import os
from pathlib import Path

import pytest
from sqlalchemy.engine import Engine

from productiq.database.vector_catalog import count_products_with_embeddings
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalMethod, RetrievalRequest
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.rrf_hybrid_retriever import create_rrf_hybrid_retriever
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON

RRF_SMOKE_ENV_VAR = "PRODUCTIQ_RRF_RETRIEVAL_SMOKE"

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv(INTEGRATION_ENV_VAR) != "1", reason=INTEGRATION_SKIP_REASON),
    pytest.mark.skipif(os.getenv(RRF_SMOKE_ENV_VAR) != "1", reason=f"Set {RRF_SMOKE_ENV_VAR}=1"),
]


@pytest.fixture
def rrf_retriever(integration_engine: Engine):
    if count_products_with_embeddings(integration_engine) < 1_000:
        pytest.skip("vector index not loaded")
    index_path = Path("resources/processed/bm25_lexical_index.pkl")
    parquet_path = Path("resources/processed/product_representations.parquet")
    from productiq.retrieval import create_bm25_retriever_from_index_path
    from productiq.retrieval.evaluation import (
        build_benchmark_scoped_bm25_retriever,
        load_lexical_retrieval_benchmark,
    )

    benchmark = load_lexical_retrieval_benchmark(
        Path("resources/evaluation/lexical_retrieval_benchmark_v1.json")
    )
    if index_path.is_file():
        try:
            lexical = create_bm25_retriever_from_index_path(index_path)
        except MemoryError:
            lexical, _ = build_benchmark_scoped_bm25_retriever(
                parquet_path, benchmark, max_docs_per_term=500, max_total_docs=8_000
            )
    else:
        lexical, _ = build_benchmark_scoped_bm25_retriever(
            parquet_path, benchmark, max_docs_per_term=500, max_total_docs=8_000
        )
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    semantic = create_semantic_retriever_from_engine(integration_engine, encoder)
    return create_rrf_hybrid_retriever(lexical, semantic, config=RRFConfig(rank_constant=60))


def test_rrf_hybrid_retrieval_integration(rrf_retriever) -> None:
    request = RetrievalRequest(
        query=build_query_representation("black Nike running shoes"),
        top_k=20,
    )
    response = rrf_retriever.retrieve(request)
    assert response.candidate_count <= 20
    assert response.metadata is not None
    assert response.metadata.rrf_rank_constant == 60
    assert response.metadata.fused_candidate_count == response.candidate_count
    fusion_scores = [c.fusion_score for c in response.candidates]
    assert all(score is not None and score > 0 for score in fusion_scores)
    assert fusion_scores == sorted(fusion_scores, reverse=True)
    product_ids = [c.product_id for c in response.candidates]
    assert len(product_ids) == len(set(product_ids))
    for candidate in response.candidates:
        assert candidate.method is RetrievalMethod.HYBRID
        if candidate.bm25_score is not None and candidate.vector_score is not None:
            assert candidate.fusion_score != candidate.bm25_score
            assert candidate.fusion_score != candidate.vector_score
