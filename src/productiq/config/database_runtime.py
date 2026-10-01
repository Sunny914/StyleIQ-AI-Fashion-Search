"""PostgreSQL / pgvector runtime contract (Phase 14B)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.config.database_config import validate_database_url
from productiq.config.settings import Settings
from productiq.database.catalog_contract import (
    PRODUCT_EMBEDDING_COLUMN,
    PRODUCT_VECTOR_CATALOG_SCHEMA_VERSION,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.vector_catalog import PRODUCT_EMBEDDING_HNSW_INDEX_NAME
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.vector_index_schema import PGVECTOR_OPERATOR_CLASS


@dataclass(frozen=True, slots=True)
class PostgresRuntimeContract:
    """Documented database expectations sourced from ProductIQ implementation."""

    engine_driver: str = "postgresql+psycopg"
    pgvector_extension: str = "vector"
    embedding_dimension: int = PRODUCTIQ_EMBEDDING_DIMENSION
    products_table: str = PRODUCTS_TABLE_NAME
    embedding_column: str = PRODUCT_EMBEDDING_COLUMN
    vector_catalog_schema_version: str = PRODUCT_VECTOR_CATALOG_SCHEMA_VERSION
    hnsw_index_name: str = PRODUCT_EMBEDDING_HNSW_INDEX_NAME
    pgvector_operator_class: str = PGVECTOR_OPERATOR_CLASS
    persistence: str = "PostgreSQL durable store; pgvector column on products"


@dataclass(frozen=True, slots=True)
class DatabaseConfigurationSummary:
    """Resolved connection configuration without exposing secrets."""

    host: str
    port: int
    database_name: str
    database_user: str
    redacted_url: str


def postgres_runtime_contract() -> PostgresRuntimeContract:
    """Return static pgvector/database contract metadata."""
    return PostgresRuntimeContract()


def summarize_database_configuration(settings: Settings) -> DatabaseConfigurationSummary:
    """Summarize database settings for deployment manifests."""
    validate_database_url(settings.database_url)
    return DatabaseConfigurationSummary(
        host=settings.database_host,
        port=settings.database_port,
        database_name=settings.database_name,
        database_user=settings.database_user,
        redacted_url=settings.redacted_database_url,
    )


__all__ = [
    "DatabaseConfigurationSummary",
    "PostgresRuntimeContract",
    "postgres_runtime_contract",
    "summarize_database_configuration",
]
