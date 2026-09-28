"""PostgreSQL integration tests for Phase 4.12 vector index."""

from __future__ import annotations

pytest_plugins = ["tests.database.conftest"]

import os
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import pytest
from sqlalchemy.engine import Engine

from productiq.database.catalog_ddl import create_product_catalog_tables
from productiq.database.loaders.catalog_loader import ProductCatalogLoader
from productiq.database.vector_catalog import (
    count_products_with_embeddings,
    ensure_product_vector_catalog_schema,
    hnsw_index_exists,
    verify_hnsw_index_operator_class,
)
from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_schema import (
    EMBEDDING_INPUT_PRODUCT_ID_COLUMN,
    EMBEDDING_OUTPUT_COLUMN,
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
)
from productiq.retrieval.pgvector_search import pgvector_operator_class_name, search_products_by_embedding
from productiq.retrieval.vector_index_builder import build_product_vector_index
from productiq.retrieval.vector_index_contract import validate_query_embedding_dimension
from tests.database.catalog_fixtures import make_product_records
from tests.database.test_catalog_integration import (
    _records_to_processed_dataframe,
    _write_processed_parquet,
)
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(os.getenv(INTEGRATION_ENV_VAR) != "1", reason=INTEGRATION_SKIP_REASON),
]

PROJECT_ROOT = Path(__file__).resolve().parents[2]
EMBEDDINGS_PATH = PROJECT_ROOT / "resources" / "processed" / PRODUCT_EMBEDDINGS_FILENAME
EMBEDDINGS_MANIFEST_PATH = PROJECT_ROOT / "resources" / "processed" / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME

VECTOR_INTEGRATION_ROWS = 32


def _write_embedding_subset_parquet(
    output_path: Path,
    *,
    source_embeddings: Path,
    product_ids: list[str],
) -> None:
    parquet_file = pq.ParquetFile(source_embeddings)
    id_to_vector: dict[str, list[float]] = {}
    for batch in parquet_file.iter_batches(batch_size=10_000):
        chunk = batch.to_pandas()
        for product_id, vector in zip(
            chunk[EMBEDDING_INPUT_PRODUCT_ID_COLUMN],
            chunk[EMBEDDING_OUTPUT_COLUMN],
            strict=True,
        ):
            product_id_str = str(product_id)
            if product_id_str in product_ids and product_id_str not in id_to_vector:
                id_to_vector[product_id_str] = [float(v) for v in vector]
            if len(id_to_vector) == len(product_ids):
                break
        if len(id_to_vector) == len(product_ids):
            break

    ordered_vectors = [id_to_vector[product_id] for product_id in product_ids]
    table = pa.table(
        {
            EMBEDDING_INPUT_PRODUCT_ID_COLUMN: product_ids,
            EMBEDDING_OUTPUT_COLUMN: pa.array(ordered_vectors, type=pa.list_(pa.float32(), 384)),
        }
    )
    pq.write_table(table, output_path)


@pytest.fixture
def vector_integration_setup(
    integration_engine: Engine,
    tmp_path: Path,
) -> tuple[Path, list[str], tuple[float, ...]]:
    if not EMBEDDINGS_PATH.is_file():
        pytest.skip("official embedding artifact unavailable")

    create_product_catalog_tables(integration_engine, checkfirst=True)
    ensure_product_vector_catalog_schema(integration_engine)

    parquet_file = pq.ParquetFile(EMBEDDINGS_PATH)
    first_batch = next(parquet_file.iter_batches(batch_size=VECTOR_INTEGRATION_ROWS))
    product_ids = [
        str(value) for value in first_batch.to_pandas()[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]
    ]

    if count_products_with_embeddings(integration_engine) < 1_000:
        catalog_parquet = tmp_path / "catalog_subset.parquet"
        records = make_product_records(len(product_ids))
        for index, product_id in enumerate(product_ids):
            records[index]["product_id"] = product_id
        _write_processed_parquet(catalog_parquet, records)
        ProductCatalogLoader(chunk_size=16).load_from_parquet(
            catalog_parquet,
            integration_engine,
            expected_row_count=len(product_ids),
        )

    subset_embeddings = tmp_path / "embeddings_subset.parquet"
    _write_embedding_subset_parquet(
        subset_embeddings,
        source_embeddings=EMBEDDINGS_PATH,
        product_ids=product_ids,
    )
    first_vector = tuple(float(v) for v in first_batch.to_pandas()[EMBEDDING_OUTPUT_COLUMN].iloc[0])
    yield subset_embeddings, product_ids, first_vector


def test_vector_index_small_integration_build_and_search(
    integration_engine: Engine,
    vector_integration_setup: tuple[Path, list[str], tuple[float, ...]],
) -> None:
    if count_products_with_embeddings(integration_engine) >= 1_000:
        pytest.skip(
            "subset index build requires an isolated database; full Phase 4.12 index is loaded"
        )
    subset_embeddings, product_ids, query_vector = vector_integration_setup
    result = build_product_vector_index(
        integration_engine,
        subset_embeddings,
        manifest_path=EMBEDDINGS_MANIFEST_PATH,
        chunk_size=16,
        max_rows=len(product_ids),
        enforce_official_checksums=False,
        output_dir=subset_embeddings.parent,
    )
    assert result.vectors_in_database == len(product_ids)
    assert hnsw_index_exists(integration_engine)
    assert verify_hnsw_index_operator_class(integration_engine) == pgvector_operator_class_name()

    response = search_products_by_embedding(integration_engine, query_vector, top_k=1)
    assert len(response.hits) == 1
    assert response.hits[0].product_id == product_ids[0]
    assert response.hits[0].similarity == pytest.approx(1.0, abs=1e-4)

    second = build_product_vector_index(
        integration_engine,
        subset_embeddings,
        manifest_path=EMBEDDINGS_MANIFEST_PATH,
        chunk_size=16,
        max_rows=len(product_ids),
        enforce_official_checksums=False,
        output_dir=subset_embeddings.parent,
    )
    assert second.vectors_in_database == len(product_ids)


def test_production_vector_index_search_smoke(integration_engine: Engine) -> None:
    if count_products_with_embeddings(integration_engine) < 1_000:
        pytest.skip("requires full Phase 4.12 vector index (>= 1,000 embeddings)")
    assert hnsw_index_exists(integration_engine)
    assert verify_hnsw_index_operator_class(integration_engine) == pgvector_operator_class_name()
    parquet_file = pq.ParquetFile(EMBEDDINGS_PATH)
    first_batch = next(parquet_file.iter_batches(batch_size=1))
    query_vector = tuple(
        float(v) for v in first_batch.to_pandas()[EMBEDDING_OUTPUT_COLUMN].iloc[0]
    )
    product_id = str(first_batch.to_pandas()[EMBEDDING_INPUT_PRODUCT_ID_COLUMN].iloc[0])
    response = search_products_by_embedding(integration_engine, query_vector, top_k=5)
    assert len(response.hits) >= 1
    assert response.hits[0].product_id == product_id
    assert response.hits[0].similarity == pytest.approx(1.0, abs=1e-4)


def test_vector_search_rejects_wrong_dimension(
    integration_engine: Engine,
    vector_integration_setup: tuple[Path, list[str], tuple[float, ...]],
) -> None:
    _, _, query_vector = vector_integration_setup
    with pytest.raises(SemanticRetrievalError):
        validate_query_embedding_dimension(len(query_vector) - 1)
    wrong = tuple(list(query_vector[:-1]))
    with pytest.raises(SemanticRetrievalError):
        search_products_by_embedding(integration_engine, wrong, top_k=5)
