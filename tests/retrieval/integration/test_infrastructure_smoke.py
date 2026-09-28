"""Infrastructure smoke checks for production retrieval integration (Phase 4.20)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.database.health import check_database_health
from productiq.database.vector_catalog import count_products_with_embeddings, hnsw_index_exists
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import create_bm25_retriever_from_index_path
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.embedding_schema import (
    EXPECTED_CATALOG_PRODUCT_COUNT,
    PRODUCTIQ_EMBEDDING_DIMENSION,
)
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from tests.retrieval.integration.conftest import (
    BM25_INDEX_PATH,
    MIN_LIVE_EMBEDDING_ROWS,
    production_retrieval_pytestmark,
)

pytestmark = production_retrieval_pytestmark


def test_postgresql_connection_and_health(live_retrieval_engine: Engine) -> None:
    check_database_health(live_retrieval_engine)
    with live_retrieval_engine.connect() as connection:
        database_name = connection.execute(text("SELECT current_database()")).scalar_one()
    assert database_name == "productIQ"


def test_products_table_exists(live_retrieval_engine: Engine) -> None:
    with live_retrieval_engine.connect() as connection:
        exists = connection.execute(
            text("SELECT to_regclass('public.products') IS NOT NULL")
        ).scalar_one()
    assert exists is True


def test_catalog_row_count_within_contract(live_retrieval_engine: Engine) -> None:
    with live_retrieval_engine.connect() as connection:
        row_count = connection.execute(text("SELECT COUNT(*) FROM products")).scalar_one()
    count = int(row_count)
    assert count >= MIN_LIVE_EMBEDDING_ROWS
    if count == EXPECTED_CATALOG_PRODUCT_COUNT:
        assert count == 367_172


def test_embedding_dimension_contract() -> None:
    assert PRODUCTIQ_EMBEDDING_DIMENSION == 384


def test_vector_rows_available(live_retrieval_engine: Engine) -> None:
    embedded = count_products_with_embeddings(live_retrieval_engine)
    assert embedded >= MIN_LIVE_EMBEDDING_ROWS


def test_hnsw_index_present_when_vectors_loaded(live_retrieval_engine: Engine) -> None:
    if count_products_with_embeddings(live_retrieval_engine) < MIN_LIVE_EMBEDDING_ROWS:
        pytest.skip("insufficient embeddings for HNSW check")
    assert hnsw_index_exists(live_retrieval_engine) is True


def test_bm25_artifact_loads() -> None:
    if not BM25_INDEX_PATH.is_file():
        pytest.skip(f"BM25 artifact missing: {BM25_INDEX_PATH}")
    retriever = create_bm25_retriever_from_index_path(BM25_INDEX_PATH)
    response = retriever.retrieve(
        RetrievalRequest(query=build_query_representation("nike shoes"), top_k=5),
    )
    assert response.candidate_count <= 5


def test_bge_encoder_initializes() -> None:
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    vector = encoder.encode_query("running shoes")
    assert vector.dimension == PRODUCTIQ_EMBEDDING_DIMENSION


def test_pgvector_semantic_search_returns_catalog_ids(live_retrieval_engine: Engine) -> None:
    if count_products_with_embeddings(live_retrieval_engine) < MIN_LIVE_EMBEDDING_ROWS:
        pytest.skip("insufficient embeddings for pgvector smoke")
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    semantic = create_semantic_retriever_from_engine(live_retrieval_engine, encoder)
    response = semantic.retrieve(
        RetrievalRequest(query=build_query_representation("running shoes"), top_k=5),
    )
    assert 0 < response.candidate_count <= 5
    product_ids = [candidate.product_id for candidate in response.candidates]
    with live_retrieval_engine.connect() as connection:
        found = connection.execute(
            text("SELECT COUNT(*) FROM products WHERE product_id = ANY(:ids)"),
            {"ids": product_ids},
        ).scalar_one()
    assert int(found) == len(product_ids)
