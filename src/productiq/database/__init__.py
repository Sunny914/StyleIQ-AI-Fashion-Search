"""Database connectivity and session management."""

from productiq.database.base import Base
from productiq.database.catalog_contract import (
    CATALOG_COLUMN_COUNT,
    CATALOG_COLUMN_ORDER,
    CATALOG_NULLABLE_ATTRIBUTE_COLUMNS,
    CATALOG_REQUIRED_COLUMNS,
    CATALOG_SOURCE_CHECK_VALUE,
    PRODUCT_CATALOG_DB_SCHEMA_VERSION,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.catalog_ddl import create_product_catalog_tables
from productiq.database.catalog_pipeline import CatalogPipelineReport, load_processed_catalog
from productiq.database.catalog_validation import CatalogValidationReport, validate_product_catalog
from productiq.database.engine import (
    create_engine_from_settings,
    get_engine,
    normalize_database_url,
    reset_database_state,
)
from productiq.database.health import check_database_health
from productiq.database.loaders import (
    DEFAULT_CATALOG_LOAD_CHUNK_SIZE,
    CatalogLoadReport,
    ProductCatalogLoader,
    validate_processed_parquet,
)
from productiq.database.models.product import Product
from productiq.database.pgvector import (
    PGVECTOR_EXTENSION_NAME,
    check_pgvector_extension,
    ensure_pgvector_extension,
    is_pgvector_extension_enabled,
    is_pgvector_python_available,
    require_pgvector_python_support,
)
from productiq.database.repository import ProductRepository
from productiq.database.session import (
    create_session_factory,
    get_session_factory,
    reset_session_factory,
    session_scope,
)

__all__ = [
    "CATALOG_COLUMN_COUNT",
    "CATALOG_COLUMN_ORDER",
    "CATALOG_NULLABLE_ATTRIBUTE_COLUMNS",
    "CATALOG_REQUIRED_COLUMNS",
    "CATALOG_SOURCE_CHECK_VALUE",
    "DEFAULT_CATALOG_LOAD_CHUNK_SIZE",
    "PGVECTOR_EXTENSION_NAME",
    "PRODUCTS_TABLE_NAME",
    "PRODUCT_CATALOG_DB_SCHEMA_VERSION",
    "Base",
    "CatalogLoadReport",
    "CatalogPipelineReport",
    "CatalogValidationReport",
    "Product",
    "ProductCatalogLoader",
    "ProductRepository",
    "check_database_health",
    "check_pgvector_extension",
    "create_engine_from_settings",
    "create_product_catalog_tables",
    "create_session_factory",
    "ensure_pgvector_extension",
    "get_engine",
    "get_session_factory",
    "is_pgvector_extension_enabled",
    "is_pgvector_python_available",
    "load_processed_catalog",
    "normalize_database_url",
    "require_pgvector_python_support",
    "reset_database_state",
    "reset_session_factory",
    "session_scope",
    "validate_processed_parquet",
    "validate_product_catalog",
]
