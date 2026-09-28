"""PostgreSQL pgvector catalog schema helpers for Phase 4.12."""

from __future__ import annotations

from sqlalchemy import Engine, Index, inspect, text
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.catalog_contract import (
    PRODUCT_EMBEDDING_COLUMN,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.models.product import Product
from productiq.database.pgvector import ensure_pgvector_extension
from productiq.exceptions import DatabaseError, PgvectorExtensionError, SemanticRetrievalError
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.vector_index_schema import (
    HNSW_EF_CONSTRUCTION,
    HNSW_M,
    PGVECTOR_OPERATOR_CLASS,
)

PRODUCT_EMBEDDING_HNSW_INDEX_NAME = "ix_products_embedding_hnsw_cosine"


def _embedding_column_exists(engine: Engine) -> bool:
    inspector = inspect(engine)
    columns = {column["name"] for column in inspector.get_columns(PRODUCTS_TABLE_NAME)}
    return PRODUCT_EMBEDDING_COLUMN in columns


def ensure_product_embedding_column(engine: Engine) -> None:
    """Add ``vector(384)`` to ``products`` when missing (idempotent)."""
    ensure_pgvector_extension(engine)
    if _embedding_column_exists(engine):
        return
    ddl = text(
        f"""
        ALTER TABLE {PRODUCTS_TABLE_NAME}
        ADD COLUMN {PRODUCT_EMBEDDING_COLUMN} vector({PRODUCTIQ_EMBEDDING_DIMENSION})
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(ddl)
    except SQLAlchemyError as exc:
        msg = f"Failed to add {PRODUCT_EMBEDDING_COLUMN} column to {PRODUCTS_TABLE_NAME}"
        raise PgvectorExtensionError(msg) from exc


def ensure_product_vector_catalog_schema(engine: Engine) -> None:
    """Ensure pgvector extension and the product embedding column exist."""
    ensure_product_embedding_column(engine)


def hnsw_index_exists(engine: Engine) -> bool:
    inspector = inspect(engine)
    index_names = {index["name"] for index in inspector.get_indexes(PRODUCTS_TABLE_NAME)}
    return PRODUCT_EMBEDDING_HNSW_INDEX_NAME in index_names


def drop_product_embedding_hnsw_index(engine: Engine) -> None:
    sql = text(f"DROP INDEX IF EXISTS {PRODUCT_EMBEDDING_HNSW_INDEX_NAME}")
    try:
        with engine.begin() as connection:
            connection.execute(sql)
    except SQLAlchemyError as exc:
        msg = f"Failed to drop HNSW index {PRODUCT_EMBEDDING_HNSW_INDEX_NAME}"
        raise DatabaseError(msg) from exc


def create_product_embedding_hnsw_index(
    engine: Engine,
    *,
    rebuild: bool = False,
    m: int = HNSW_M,
    ef_construction: int = HNSW_EF_CONSTRUCTION,
) -> None:
    """Create the cosine HNSW index on ``products.embedding`` (idempotent unless rebuild)."""
    ensure_product_vector_catalog_schema(engine)
    if m <= 0 or ef_construction <= 0:
        msg = "HNSW parameters m and ef_construction must be positive"
        raise SemanticRetrievalError(msg)
    if rebuild and hnsw_index_exists(engine):
        drop_product_embedding_hnsw_index(engine)
    if hnsw_index_exists(engine):
        return
    create_sql = text(
        f"""
        CREATE INDEX {PRODUCT_EMBEDDING_HNSW_INDEX_NAME}
        ON {PRODUCTS_TABLE_NAME}
        USING hnsw ({PRODUCT_EMBEDDING_COLUMN} {PGVECTOR_OPERATOR_CLASS})
        WITH (m = {int(m)}, ef_construction = {int(ef_construction)})
        """
    )
    try:
        with engine.begin() as connection:
            connection.execute(create_sql)
    except SQLAlchemyError as exc:
        msg = f"Failed to create HNSW index {PRODUCT_EMBEDDING_HNSW_INDEX_NAME}"
        raise DatabaseError(msg) from exc


def expected_hnsw_index_definition() -> Index:
    """Return the SQLAlchemy Index metadata mirror used in ORM docs/tests."""
    return Index(
        PRODUCT_EMBEDDING_HNSW_INDEX_NAME,
        Product.embedding,
        postgresql_using="hnsw",
        postgresql_ops={PRODUCT_EMBEDDING_COLUMN: PGVECTOR_OPERATOR_CLASS},
        postgresql_with={"m": HNSW_M, "ef_construction": HNSW_EF_CONSTRUCTION},
    )


def count_products_with_embeddings(engine: Engine) -> int:
    sql = text(
        f"""
        SELECT COUNT(*)
        FROM {PRODUCTS_TABLE_NAME}
        WHERE {PRODUCT_EMBEDDING_COLUMN} IS NOT NULL
        """
    )
    with engine.connect() as connection:
        return int(connection.execute(sql).scalar_one())


def count_catalog_products(engine: Engine) -> int:
    sql = text(f"SELECT COUNT(*) FROM {PRODUCTS_TABLE_NAME}")
    with engine.connect() as connection:
        return int(connection.execute(sql).scalar_one())


def verify_hnsw_index_operator_class(engine: Engine) -> str:
    """Return pgvector opclass name for the product embedding HNSW index."""
    sql = text(
        """
        SELECT opc.opcname
        FROM pg_index idx
        JOIN pg_class cls ON cls.oid = idx.indexrelid
        JOIN pg_am am ON am.oid = cls.relam
        JOIN pg_opclass opc ON opc.oid = idx.indclass[0]
        WHERE cls.relname = :index_name
          AND am.amname = 'hnsw'
        """
    )
    with engine.connect() as connection:
        result = connection.execute(sql, {"index_name": PRODUCT_EMBEDDING_HNSW_INDEX_NAME}).scalar_one_or_none()
    if result is None:
        msg = f"HNSW index {PRODUCT_EMBEDDING_HNSW_INDEX_NAME} was not found"
        raise SemanticRetrievalError(msg)
    return str(result)


__all__ = [
    "PRODUCT_EMBEDDING_HNSW_INDEX_NAME",
    "count_catalog_products",
    "count_products_with_embeddings",
    "create_product_embedding_hnsw_index",
    "drop_product_embedding_hnsw_index",
    "ensure_product_embedding_column",
    "ensure_product_vector_catalog_schema",
    "expected_hnsw_index_definition",
    "hnsw_index_exists",
    "verify_hnsw_index_operator_class",
]
