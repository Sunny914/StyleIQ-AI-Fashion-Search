"""Integration smoke tests for Phase 4.15 hybrid retrieval."""

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
from productiq.retrieval.hybrid_retriever import create_hybrid_retriever
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON

INTEGRATION_SKIP = os.getenv(INTEGRATION_ENV_VAR) != "1"
HYBRID_SMOKE_ENV_VAR = "PRODUCTIQ_HYBRID_RETRIEVAL_SMOKE"
HYBRID_SMOKE_SKIP_REASON = f"Set {HYBRID_SMOKE_ENV_VAR}=1 to run hybrid retrieval integration smoke."

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(INTEGRATION_SKIP, reason=INTEGRATION_SKIP_REASON),
    pytest.mark.skipif(os.getenv(HYBRID_SMOKE_ENV_VAR) != "1", reason=HYBRID_SMOKE_SKIP_REASON),
]


@pytest.fixture
def hybrid_retriever(integration_engine: Engine):
    vector_count = count_products_with_embeddings(integration_engine)
    if vector_count < 1_000:
        pytest.skip(
            "PostgreSQL has fewer than 1,000 product embeddings; "
            "run Phase 4.12 vector index build before hybrid retrieval smoke."
        )
    index_path = Path("resources/processed/bm25_lexical_index.pkl")
    parquet_path = Path("resources/processed/product_representations.parquet")
    if not index_path.is_file() and not parquet_path.is_file():
        pytest.skip("need BM25 index or representation parquet for hybrid integration")
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
                parquet_path,
                benchmark,
                max_docs_per_term=500,
                max_total_docs=8_000,
            )
    else:
        lexical, _ = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    semantic = create_semantic_retriever_from_engine(integration_engine, encoder)
    return create_hybrid_retriever(lexical, semantic)


def test_hybrid_retrieval_end_to_end(hybrid_retriever) -> None:
    request = RetrievalRequest(
        query=build_query_representation("black Nike running shoes"),
        top_k=20,
    )
    response = hybrid_retriever.retrieve(request)
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 20
    assert response.metadata.lexical_candidate_count is not None
    assert response.metadata.semantic_candidate_count is not None
    assert response.metadata.unique_candidate_count == response.candidate_count
    if response.candidate_count == 0:
        pytest.skip("both retrievers returned empty for query")
    assert response.candidate_count <= 40
    methods_seen: set[tuple[RetrievalMethod, ...]] = set()
    for candidate in response.candidates:
        assert candidate.method is RetrievalMethod.HYBRID
        methods_seen.add(candidate.resolved_retrieval_methods())
        if (
            candidate.bm25_score is not None
            and candidate.vector_score is not None
        ):
            assert candidate.score == 0.0
        elif candidate.bm25_score is not None:
            assert candidate.score == candidate.bm25_score
        elif candidate.vector_score is not None:
            assert candidate.score == candidate.vector_score
    assert len(methods_seen) >= 1
    if response.metadata.overlap_count and response.metadata.overlap_count > 0:
        both = [
            c
            for c in response.candidates
            if RetrievalMethod.BM25 in c.resolved_retrieval_methods()
            and RetrievalMethod.VECTOR in c.resolved_retrieval_methods()
        ]
        assert len(both) == response.metadata.overlap_count
