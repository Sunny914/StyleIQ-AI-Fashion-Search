"""Build PostgreSQL/pgvector HNSW index from validated embedding artifacts (Phase 4.12)."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.catalog_contract import (
    PRODUCT_EMBEDDING_COLUMN,
    PRODUCT_VECTOR_CATALOG_SCHEMA_VERSION,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.vector_catalog import (
    PRODUCT_EMBEDDING_HNSW_INDEX_NAME,
    count_catalog_products,
    count_products_with_embeddings,
    create_product_embedding_hnsw_index,
    ensure_product_vector_catalog_schema,
    hnsw_index_exists,
    verify_hnsw_index_operator_class,
)
from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.embedding_builder import (
    ProductEmbeddingManifest,
    load_product_embeddings_manifest,
)
from productiq.retrieval.embedding_schema import (
    EXPECTED_CATALOG_PRODUCT_COUNT,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    PRODUCTIQ_EMBEDDING_DIMENSION,
)
from productiq.retrieval.vector_index_loader import (
    VectorIndexLoadReport,
    load_product_embeddings_into_catalog,
    validate_embedding_artifact_for_vector_index,
    validate_embedding_parquet_subset_for_vector_index,
)
from productiq.retrieval.vector_index_schema import (
    CHECKSUM_ALGORITHM,
    DEFAULT_VECTOR_INDEX_LOAD_BATCH_SIZE,
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    PGVECTOR_DISTANCE_METRIC,
    PGVECTOR_INDEX_TYPE,
    PGVECTOR_OPERATOR_CLASS,
    PRODUCT_VECTOR_INDEX_MANIFEST_FILENAME,
    PRODUCT_VECTOR_INDEX_NAME,
    PRODUCT_VECTOR_INDEX_PIPELINE_PHASE,
    PRODUCT_VECTOR_INDEX_SCHEMA_VERSION,
)


class ProductVectorIndexManifest(BaseModel):
    """Lineage metadata for the PostgreSQL/pgvector product index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index_name: str
    schema_version: str
    catalog_schema_version: str
    index_type: str
    distance_metric: str
    pgvector_operator_class: str
    vector_dimension: int = Field(gt=0)
    hnsw_m: int = Field(gt=0)
    hnsw_ef_construction: int = Field(gt=0)
    hnsw_index_name: str
    source_embedding_artifact_path: str
    source_embedding_artifact_filename: str
    source_embedding_artifact_checksum: str
    source_representation_checksum: str | None = None
    embedding_model_id: str
    embedding_model_revision: str
    embedding_manifest_schema_version: str
    product_count: int = Field(ge=0)
    vectors_loaded: int = Field(ge=0)
    build_timestamp_utc: str
    load_duration_seconds: float = Field(ge=0.0)
    index_build_duration_seconds: float = Field(ge=0.0)
    total_build_duration_seconds: float = Field(ge=0.0)
    pipeline_phase: str
    checksum_algorithm: str
    index_size_bytes: int | None = None


@dataclass(frozen=True)
class ProductVectorIndexBuildResult:
    embeddings_path: Path
    manifest_path: Path
    embedding_manifest: ProductEmbeddingManifest
    load_report: VectorIndexLoadReport
    vector_index_manifest: ProductVectorIndexManifest
    catalog_product_count: int
    vectors_in_database: int
    hnsw_index_present: bool


@dataclass(frozen=True)
class ProductVectorIndexValidationReport:
    catalog_product_count: int
    vectors_with_embeddings: int
    expected_vectors: int
    hnsw_index_present: bool
    hnsw_operator_class: str
    vector_dimension: int


def _serialize_manifest(payload: dict[str, Any]) -> str:
    return f"{json.dumps(payload, indent=2, sort_keys=True)}\n"


def load_product_vector_index_manifest(path: Path) -> ProductVectorIndexManifest:
    manifest_path = Path(path)
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    return ProductVectorIndexManifest.model_validate(payload)


def publish_product_vector_index_manifest(
    manifest: ProductVectorIndexManifest,
    output_dir: Path,
) -> Path:
    output_directory = Path(output_dir)
    output_directory.mkdir(parents=True, exist_ok=True)
    manifest_path = output_directory / PRODUCT_VECTOR_INDEX_MANIFEST_FILENAME
    manifest_path.write_text(
        _serialize_manifest(manifest.model_dump(mode="json")),
        encoding="utf-8",
    )
    return manifest_path


def index_size_bytes(engine: Engine) -> int | None:
    sql = text(
        f"SELECT pg_relation_size('{PRODUCT_EMBEDDING_HNSW_INDEX_NAME}'::regclass)"
    )
    try:
        with engine.connect() as connection:
            return int(
                cast(
                    int,
                    connection.execute(sql).scalar_one(),
                )
            )
    except SQLAlchemyError:
        return None


def validate_product_vector_index_state(
    engine: Engine,
    *,
    expected_product_count: int,
    expected_dimension: int = PRODUCTIQ_EMBEDDING_DIMENSION,
) -> ProductVectorIndexValidationReport:
    """Validate PostgreSQL vector index state after build."""
    vectors = count_products_with_embeddings(engine)
    catalog_count = count_catalog_products(engine)
    if vectors != expected_product_count:
        msg = f"expected {expected_product_count} vectors, found {vectors}"
        raise SemanticRetrievalError(msg)
    if catalog_count < expected_product_count:
        msg = (
            f"catalog row count {catalog_count} is smaller than expected "
            f"{expected_product_count} vectors"
        )
        raise SemanticRetrievalError(msg)
    if not hnsw_index_exists(engine):
        msg = f"HNSW index {PRODUCT_EMBEDDING_HNSW_INDEX_NAME} is missing"
        raise SemanticRetrievalError(msg)

    operator_class = verify_hnsw_index_operator_class(engine)
    if operator_class != PGVECTOR_OPERATOR_CLASS:
        msg = (
            f"HNSW index operator class must be {PGVECTOR_OPERATOR_CLASS}, found {operator_class}"
        )
        raise SemanticRetrievalError(msg)

    dimension_sql = text(
        f"""
        SELECT vector_dims({PRODUCT_EMBEDDING_COLUMN})
        FROM {PRODUCTS_TABLE_NAME}
        WHERE {PRODUCT_EMBEDDING_COLUMN} IS NOT NULL
        LIMIT 1
        """
    )
    with engine.connect() as connection:
        dimension = int(connection.execute(dimension_sql).scalar_one())
    if dimension != expected_dimension:
        msg = f"database vector dimension must be {expected_dimension}, found {dimension}"
        raise SemanticRetrievalError(msg)

    return ProductVectorIndexValidationReport(
        catalog_product_count=catalog_count,
        vectors_with_embeddings=vectors,
        expected_vectors=expected_product_count,
        hnsw_index_present=True,
        hnsw_operator_class=operator_class,
        vector_dimension=dimension,
    )


def build_product_vector_index(
    engine: Engine,
    embeddings_path: Path,
    *,
    manifest_path: Path | None = None,
    output_dir: Path | None = None,
    chunk_size: int = DEFAULT_VECTOR_INDEX_LOAD_BATCH_SIZE,
    max_rows: int | None = None,
    rebuild_hnsw: bool = False,
    enforce_official_checksums: bool = True,
    skip_load: bool = False,
    skip_index: bool = False,
) -> ProductVectorIndexBuildResult:
    """Validate artifact, load vectors, create HNSW index, and publish lineage metadata."""
    resolved_embeddings = Path(embeddings_path)
    total_started = time.perf_counter()
    resolved_manifest = manifest_path or resolved_embeddings.parent / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME

    if max_rows is not None:
        validate_embedding_parquet_subset_for_vector_index(
            resolved_embeddings,
            expected_row_count=max_rows,
        )
        embedding_manifest = load_product_embeddings_manifest(resolved_manifest)
    else:
        embedding_manifest = validate_embedding_artifact_for_vector_index(
            resolved_embeddings,
            manifest_path=resolved_manifest,
            expected_product_count=EXPECTED_CATALOG_PRODUCT_COUNT,
            enforce_official_checksums=enforce_official_checksums,
        )

    ensure_product_vector_catalog_schema(engine)

    load_started = time.perf_counter()
    if skip_load:
        load_report = VectorIndexLoadReport(
            embeddings_path=resolved_embeddings,
            rows_read=0,
            rows_updated=0,
            rows_missing_product=0,
            chunk_size=chunk_size,
            duration_seconds=0.0,
        )
    else:
        load_report = load_product_embeddings_into_catalog(
            engine,
            resolved_embeddings,
            chunk_size=chunk_size,
            max_rows=max_rows,
        )
    load_duration = time.perf_counter() - load_started

    index_started = time.perf_counter()
    if not skip_index:
        create_product_embedding_hnsw_index(engine, rebuild=rebuild_hnsw)
    index_duration = time.perf_counter() - index_started

    expected_vectors = max_rows if max_rows is not None else embedding_manifest.product_count
    validation = validate_product_vector_index_state(
        engine,
        expected_product_count=expected_vectors,
    )

    total_duration = time.perf_counter() - total_started
    index_manifest = ProductVectorIndexManifest(
        index_name=PRODUCT_VECTOR_INDEX_NAME,
        schema_version=PRODUCT_VECTOR_INDEX_SCHEMA_VERSION,
        catalog_schema_version=PRODUCT_VECTOR_CATALOG_SCHEMA_VERSION,
        index_type=PGVECTOR_INDEX_TYPE,
        distance_metric=PGVECTOR_DISTANCE_METRIC,
        pgvector_operator_class=PGVECTOR_OPERATOR_CLASS,
        vector_dimension=PRODUCTIQ_EMBEDDING_DIMENSION,
        hnsw_m=HNSW_M,
        hnsw_ef_construction=HNSW_EF_CONSTRUCTION,
        hnsw_index_name=PRODUCT_EMBEDDING_HNSW_INDEX_NAME,
        source_embedding_artifact_path=str(resolved_embeddings.resolve()),
        source_embedding_artifact_filename=resolved_embeddings.name,
        source_embedding_artifact_checksum=embedding_manifest.checksum,
        source_representation_checksum=embedding_manifest.source_representation_checksum,
        embedding_model_id=embedding_manifest.model_id,
        embedding_model_revision=embedding_manifest.model_revision,
        embedding_manifest_schema_version=embedding_manifest.schema_version,
        product_count=embedding_manifest.product_count,
        vectors_loaded=validation.vectors_with_embeddings,
        build_timestamp_utc=datetime.now(tz=UTC).isoformat(),
        load_duration_seconds=load_duration,
        index_build_duration_seconds=index_duration,
        total_build_duration_seconds=total_duration,
        pipeline_phase=PRODUCT_VECTOR_INDEX_PIPELINE_PHASE,
        checksum_algorithm=CHECKSUM_ALGORITHM,
        index_size_bytes=index_size_bytes(engine),
    )

    publish_dir = output_dir or resolved_embeddings.parent
    manifest_out = publish_product_vector_index_manifest(index_manifest, publish_dir)

    return ProductVectorIndexBuildResult(
        embeddings_path=resolved_embeddings,
        manifest_path=manifest_out,
        embedding_manifest=embedding_manifest,
        load_report=load_report,
        vector_index_manifest=index_manifest,
        catalog_product_count=validation.catalog_product_count,
        vectors_in_database=validation.vectors_with_embeddings,
        hnsw_index_present=validation.hnsw_index_present,
    )


__all__ = [
    "ProductVectorIndexBuildResult",
    "ProductVectorIndexManifest",
    "ProductVectorIndexValidationReport",
    "build_product_vector_index",
    "index_size_bytes",
    "load_product_vector_index_manifest",
    "publish_product_vector_index_manifest",
    "validate_product_vector_index_state",
]
