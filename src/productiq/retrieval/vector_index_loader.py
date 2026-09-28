"""Batched loader from product_embeddings.parquet into PostgreSQL/pgvector."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.database.catalog_contract import PRODUCT_EMBEDDING_COLUMN, PRODUCTS_TABLE_NAME
from productiq.database.vector_catalog import ensure_product_vector_catalog_schema
from productiq.exceptions.base import SemanticRetrievalError
from productiq.logging import get_logger
from productiq.retrieval.embedding_builder import (
    ProductEmbeddingManifest,
    validate_embedding_vectors,
    validate_embeddings_parquet_integrity,
    validate_product_embeddings_parquet,
)
from productiq.retrieval.embedding_schema import (
    BGE_PRIMARY_MODEL_ID,
    DEFAULT_EMBEDDING_READ_BATCH_SIZE,
    EMBEDDING_INPUT_PRODUCT_ID_COLUMN,
    EMBEDDING_OUTPUT_COLUMN,
    EXPECTED_CATALOG_PRODUCT_COUNT,
    NORMALIZATION_L2,
    PRODUCTIQ_EMBEDDING_DIMENSION,
    SIMILARITY_METRIC_COSINE,
)
from productiq.retrieval.vector_index_schema import (
    DEFAULT_VECTOR_INDEX_LOAD_BATCH_SIZE,
    OFFICIAL_EMBEDDING_ARTIFACT_CHECKSUM,
    OFFICIAL_SOURCE_REPRESENTATION_CHECKSUM,
)

_CATALOG_EXISTENCE_BATCH_SIZE = 10_000

_UPDATE_EMBEDDING_SQL = text(
    f"""
    UPDATE {PRODUCTS_TABLE_NAME}
    SET {PRODUCT_EMBEDDING_COLUMN} = CAST(:embedding AS vector)
    WHERE product_id = :product_id
    """
)


@dataclass(frozen=True)
class VectorIndexLoadReport:
    """Summary of embedding vectors loaded into PostgreSQL."""

    embeddings_path: Path
    rows_read: int
    rows_updated: int
    rows_missing_product: int
    chunk_size: int
    duration_seconds: float

    def summary(self) -> str:
        return "\n".join(
            [
                f"Embeddings: {self.embeddings_path.name}",
                f"Rows read: {self.rows_read}",
                f"Rows updated: {self.rows_updated}",
                f"Missing catalog products: {self.rows_missing_product}",
                f"Chunk size: {self.chunk_size}",
                f"Duration (s): {self.duration_seconds:.3f}",
            ]
        )


def validate_embedding_artifact_for_vector_index(
    embeddings_path: Path,
    *,
    manifest_path: Path | None = None,
    expected_product_count: int | None = EXPECTED_CATALOG_PRODUCT_COUNT,
    enforce_official_checksums: bool = True,
) -> ProductEmbeddingManifest:
    """Validate embedding parquet + manifest before any database write."""
    manifest = validate_product_embeddings_parquet(
        embeddings_path,
        expected_row_count=expected_product_count,
        expected_dimension=PRODUCTIQ_EMBEDDING_DIMENSION,
        expected_source_checksum=OFFICIAL_SOURCE_REPRESENTATION_CHECKSUM
        if enforce_official_checksums
        else None,
        manifest_path=manifest_path,
    )
    if manifest.embedding_dimension != PRODUCTIQ_EMBEDDING_DIMENSION:
        msg = f"embedding dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}"
        raise SemanticRetrievalError(msg)
    if manifest.model_id != BGE_PRIMARY_MODEL_ID:
        msg = f"embedding model must be {BGE_PRIMARY_MODEL_ID}"
        raise SemanticRetrievalError(msg)
    if not manifest.model_revision.strip():
        msg = "embedding manifest must include model_revision"
        raise SemanticRetrievalError(msg)
    if manifest.normalization_method.lower() != NORMALIZATION_L2:
        msg = f"normalization must be {NORMALIZATION_L2}"
        raise SemanticRetrievalError(msg)
    if manifest.similarity_metric.lower() != SIMILARITY_METRIC_COSINE:
        msg = f"similarity metric must be {SIMILARITY_METRIC_COSINE}"
        raise SemanticRetrievalError(msg)
    if enforce_official_checksums and manifest.checksum != OFFICIAL_EMBEDDING_ARTIFACT_CHECKSUM:
        msg = "embedding artifact checksum does not match the official Phase 4.11 artifact"
        raise SemanticRetrievalError(msg)
    return manifest


def validate_embedding_parquet_subset_for_vector_index(
    embeddings_path: Path,
    *,
    expected_row_count: int,
) -> None:
    """Validate a row-limited parquet slice before subset index builds."""
    validate_embeddings_parquet_integrity(
        embeddings_path,
        expected_row_count=expected_row_count,
        expected_dimension=PRODUCTIQ_EMBEDDING_DIMENSION,
    )


def _normalize_product_id(value: object) -> str:
    if value is None:
        msg = "product_id must not be null"
        raise SemanticRetrievalError(msg)
    product_id = str(value).strip()
    if not product_id:
        msg = "product_id must not be empty"
        raise SemanticRetrievalError(msg)
    return product_id


def _embedding_to_pgvector_literal(vector: np.ndarray[Any, np.dtype[np.float32]]) -> str:
    components = ",".join(f"{float(component):.8g}" for component in vector.reshape(-1))
    return f"[{components}]"


def _assert_catalog_contains_product_ids(engine: Engine, product_ids: list[str]) -> None:
    if not product_ids:
        return
    check_sql = text(
        f"""
        SELECT product_id
        FROM {PRODUCTS_TABLE_NAME}
        WHERE product_id = ANY(:product_ids)
        """
    )
    with engine.connect() as connection:
        result = connection.execute(check_sql, {"product_ids": product_ids})
        found = {str(row[0]) for row in result}
    missing = set(product_ids) - found
    if missing:
        sample = sorted(missing)[:5]
        msg = (
            f"{len(missing)} embedding product_id values are missing from {PRODUCTS_TABLE_NAME}; "
            f"examples: {sample}"
        )
        raise SemanticRetrievalError(msg)


def validate_catalog_alignment_for_embeddings(
    engine: Engine,
    embeddings_path: Path,
    *,
    max_rows: int | None = None,
) -> None:
    """Ensure embedding product IDs exist in ``products`` (streaming, batched)."""
    parquet_file = pq.ParquetFile(embeddings_path)
    seen: set[str] = set()
    rows = 0
    pending_ids: list[str] = []

    for batch in parquet_file.iter_batches(
        batch_size=DEFAULT_EMBEDDING_READ_BATCH_SIZE,
        columns=[EMBEDDING_INPUT_PRODUCT_ID_COLUMN],
    ):
        chunk = batch.to_pandas()
        for value in chunk[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]:
            if max_rows is not None and rows >= max_rows:
                break
            product_id = _normalize_product_id(value)
            if product_id in seen:
                msg = f"duplicate product_id in embeddings artifact: {product_id}"
                raise SemanticRetrievalError(msg)
            seen.add(product_id)
            pending_ids.append(product_id)
            rows += 1
            if len(pending_ids) >= _CATALOG_EXISTENCE_BATCH_SIZE:
                _assert_catalog_contains_product_ids(engine, pending_ids)
                pending_ids.clear()
        if max_rows is not None and rows >= max_rows:
            break

    _assert_catalog_contains_product_ids(engine, pending_ids)

    if not seen:
        msg = "embeddings artifact contains no product_id values"
        raise SemanticRetrievalError(msg)


def load_product_embeddings_into_catalog(
    engine: Engine,
    embeddings_path: Path,
    *,
    chunk_size: int = DEFAULT_VECTOR_INDEX_LOAD_BATCH_SIZE,
    max_rows: int | None = None,
    validate_catalog_alignment: bool = True,
) -> VectorIndexLoadReport:
    """Stream embeddings from parquet and update vectors on existing catalog rows."""
    import time

    logger = get_logger(__name__)
    if chunk_size <= 0:
        msg = "vector index loader chunk_size must be positive"
        raise SemanticRetrievalError(msg)

    resolved = Path(embeddings_path)
    ensure_product_vector_catalog_schema(engine)
    if validate_catalog_alignment:
        validate_catalog_alignment_for_embeddings(engine, resolved, max_rows=max_rows)

    parquet_file = pq.ParquetFile(resolved)
    rows_read = 0
    rows_updated = 0
    rows_missing_product = 0
    started = time.perf_counter()

    for batch_index, batch in enumerate(
        parquet_file.iter_batches(batch_size=chunk_size),
        start=1,
    ):
        chunk = batch.to_pandas()
        product_ids = [
            _normalize_product_id(value) for value in chunk[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]
        ]
        vectors = np.asarray(chunk[EMBEDDING_OUTPUT_COLUMN].tolist(), dtype=np.float32)
        validate_embedding_vectors(vectors, expected_dimension=PRODUCTIQ_EMBEDDING_DIMENSION)

        with engine.begin() as connection:
            for product_id, vector in zip(product_ids, vectors, strict=True):
                if max_rows is not None and rows_read >= max_rows:
                    break
                literal = _embedding_to_pgvector_literal(vector)
                result = connection.execute(
                    _UPDATE_EMBEDDING_SQL,
                    {"product_id": product_id, "embedding": literal},
                )
                rowcount = int(getattr(result, "rowcount", 0) or 0)
                if rowcount == 0:
                    rows_missing_product += 1
                    msg = f"catalog row missing for embedding product_id={product_id}"
                    raise SemanticRetrievalError(msg)
                rows_updated += rowcount
                rows_read += 1

        logger.info(
            "Vector load batch %s complete (%s rows processed)",
            batch_index,
            rows_read,
        )
        if max_rows is not None and rows_read >= max_rows:
            break

    duration = time.perf_counter() - started
    return VectorIndexLoadReport(
        embeddings_path=resolved,
        rows_read=rows_read,
        rows_updated=rows_updated,
        rows_missing_product=rows_missing_product,
        chunk_size=chunk_size,
        duration_seconds=duration,
    )


__all__ = [
    "VectorIndexLoadReport",
    "load_product_embeddings_into_catalog",
    "validate_catalog_alignment_for_embeddings",
    "validate_embedding_artifact_for_vector_index",
    "validate_embedding_parquet_subset_for_vector_index",
]
