"""Integration smoke tests for Phase 4.13 semantic retrieval (BGE + pgvector)."""

from __future__ import annotations

pytest_plugins = ["tests.database.conftest"]

import math
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalMethod, RetrievalRequest
from productiq.database.vector_catalog import count_products_with_embeddings
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON

INTEGRATION_SKIP = os.getenv(INTEGRATION_ENV_VAR) != "1"
SEMANTIC_SMOKE_ENV_VAR = "PRODUCTIQ_SEMANTIC_RETRIEVAL_SMOKE"
SEMANTIC_SMOKE_SKIP_REASON = f"Set {SEMANTIC_SMOKE_ENV_VAR}=1 to run BGE + pgvector semantic retrieval smoke."

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(INTEGRATION_SKIP, reason=INTEGRATION_SKIP_REASON),
    pytest.mark.skipif(os.getenv(SEMANTIC_SMOKE_ENV_VAR) != "1", reason=SEMANTIC_SMOKE_SKIP_REASON),
]


@pytest.fixture
def semantic_retriever(integration_engine: Engine):
    vector_count = count_products_with_embeddings(integration_engine)
    if vector_count < 1_000:
        pytest.skip(
            "PostgreSQL has fewer than 1,000 product embeddings; "
            "run Phase 4.12 vector index build before semantic retrieval smoke."
        )
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    return create_semantic_retriever_from_engine(integration_engine, encoder)


def test_semantic_retrieval_end_to_end(
    integration_engine: Engine,
    semantic_retriever,
) -> None:
    request = RetrievalRequest(
        query=build_query_representation("black running shoes"),
        top_k=10,
    )
    response = semantic_retriever.retrieve(request)
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 10
    assert response.candidate_count <= 10
    assert response.candidate_count > 0

    previous_score = math.inf
    for candidate in response.candidates:
        assert candidate.method is RetrievalMethod.VECTOR
        assert math.isfinite(candidate.score)
        assert -1.0 <= candidate.score <= 1.0 + 1e-6
        assert candidate.score <= previous_score + 1e-6
        previous_score = candidate.score

    product_ids = [candidate.product_id for candidate in response.candidates]
    with integration_engine.connect() as connection:
        found = connection.execute(
            text("SELECT COUNT(*) FROM products WHERE product_id = ANY(:ids)"),
            {"ids": product_ids},
        ).scalar_one()
    assert int(found) == len(product_ids)


def test_semantic_retrieval_uses_pgvector_index(semantic_retriever) -> None:
    request = RetrievalRequest(
        query=build_query_representation("casual cotton t-shirt"),
        top_k=5,
    )
    response = semantic_retriever.retrieve(request)
    assert 0 < response.candidate_count <= 5
