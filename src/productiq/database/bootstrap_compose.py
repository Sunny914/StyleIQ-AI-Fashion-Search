"""Deterministic PostgreSQL/pgvector bootstrap for Compose (Phase 15B).

Uses existing catalog DDL and vector catalog helpers — no parallel schema.
"""

from __future__ import annotations

import argparse
import json
from typing import Any

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.config.settings import get_settings
from productiq.database.catalog_contract import (
    PRODUCT_EMBEDDING_COLUMN,
    PRODUCTS_TABLE_NAME,
)
from productiq.database.catalog_ddl import create_product_catalog_tables
from productiq.database.engine import create_engine_from_settings, normalize_database_url
from productiq.database.models.product import Product
from productiq.database.pgvector import (
    PGVECTOR_EXTENSION_NAME,
    ensure_pgvector_extension,
    is_pgvector_extension_enabled,
)
from productiq.database.vector_catalog import (
    PRODUCT_EMBEDDING_HNSW_INDEX_NAME,
    count_catalog_products,
    create_product_embedding_hnsw_index,
    ensure_product_vector_catalog_schema,
    hnsw_index_exists,
    verify_hnsw_index_operator_class,
)
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.vector_index_schema import PGVECTOR_OPERATOR_CLASS


def bootstrap_productiq_database(
    engine: Engine,
    *,
    create_hnsw_index: bool = True,
) -> None:
    """Enable pgvector, create products table, embedding column, and optional HNSW index."""
    ensure_pgvector_extension(engine)
    create_product_catalog_tables(engine, checkfirst=True)
    ensure_product_vector_catalog_schema(engine)
    if create_hnsw_index:
        create_product_embedding_hnsw_index(engine)


def _unit_embedding(seed: int) -> list[float]:
    vector = [0.0] * PRODUCTIQ_EMBEDDING_DIMENSION
    vector[seed % PRODUCTIQ_EMBEDDING_DIMENSION] = 1.0
    return vector


FIXTURE_PRODUCT_ID_PREFIX = "compose-demo-"


def _demo_product_rows() -> list[dict[str, object]]:
    """Labeled demo rows for Compose smoke tests (not the 367k reference catalog)."""
    base: dict[str, object] = {
        "product_url": "https://example.com/compose-demo",
        "image_url": "https://example.com/compose-demo.jpg",
        "color_is_coded": False,
        "discount_price_inr": 100,
        "original_price_inr": 200,
        "price_anomaly": False,
        "source": "ajio",
        "fit": "regular",
        "pattern": "solid",
        "sleeve": None,
        "neckline": None,
        "material": None,
        "product_features": None,
        "style_attributes": None,
    }
    return [
        {
            **base,
            "product_id": "compose-demo-001",
            "brand": "Nike",
            "brand_normalized": "nike",
            "description": "Nike running shoes black mesh trainers for men",
            "category_gender": "Men",
            "color_raw": "black",
            "color_normalized": "black",
            "product_type": "shoes",
        },
        {
            **base,
            "product_id": "compose-demo-002",
            "brand": "Zara",
            "brand_normalized": "zara",
            "description": "Zara floral midi dress red cotton summer wear for women",
            "category_gender": "Women",
            "color_raw": "red",
            "color_normalized": "red",
            "product_type": "dress",
        },
        {
            **base,
            "product_id": "compose-demo-003",
            "brand": "Puma",
            "brand_normalized": "puma",
            "description": "Puma slim fit cotton shirt navy blue formal men",
            "category_gender": "Men",
            "color_raw": "navy",
            "color_normalized": "blue",
            "product_type": "shirt",
        },
    ]


def load_compose_integration_demo_catalog(engine: Engine) -> int:
    """Insert labeled demo catalog rows for Compose smoke tests (not production scale)."""
    demo_rows = _demo_product_rows()
    inserted = 0
    with Session(engine) as session:
        for index, row in enumerate(demo_rows):
            session.merge(Product(**row, embedding=_unit_embedding(index)))
            inserted += 1
        session.commit()
    return inserted


def _embedding_column_type(engine: Engine) -> str | None:
    sql = text(
        """
        SELECT format_type(a.atttypid, a.atttypmod)
        FROM pg_attribute a
        JOIN pg_class c ON c.oid = a.attrelid
        WHERE c.relname = :table_name
          AND a.attname = :column_name
          AND NOT a.attisdropped
        """
    )
    with engine.connect() as connection:
        return connection.execute(
            sql,
            {"table_name": PRODUCTS_TABLE_NAME, "column_name": PRODUCT_EMBEDDING_COLUMN},
        ).scalar_one_or_none()


def verify_compose_database_contract(engine: Engine) -> dict[str, Any]:
    """Verify Phase 14/4.12 pgvector contract; never includes connection secrets."""
    checks: dict[str, Any] = {}
    checks["postgres_reachable"] = True
    with engine.connect() as connection:
        checks["database_name"] = connection.execute(text("SELECT current_database()")).scalar_one()
    checks["vector_extension_installed"] = is_pgvector_extension_enabled(engine)
    inspector = inspect(engine)
    checks["products_table_exists"] = PRODUCTS_TABLE_NAME in inspector.get_table_names()
    columns = {c["name"]: c for c in inspector.get_columns(PRODUCTS_TABLE_NAME)}
    checks["embedding_column_exists"] = PRODUCT_EMBEDDING_COLUMN in columns
    col_type = _embedding_column_type(engine)
    checks["embedding_column_type"] = col_type
    checks["embedding_dimension"] = PRODUCTIQ_EMBEDDING_DIMENSION
    checks["embedding_type_is_vector"] = col_type is not None and col_type.startswith("vector(")
    checks["hnsw_index_exists"] = hnsw_index_exists(engine)
    if checks["hnsw_index_exists"]:
        checks["hnsw_operator_class"] = verify_hnsw_index_operator_class(engine)
        checks["hnsw_cosine_opclass"] = checks["hnsw_operator_class"] == PGVECTOR_OPERATOR_CLASS
    else:
        checks["hnsw_operator_class"] = None
        checks["hnsw_cosine_opclass"] = False
    checks["catalog_row_count"] = count_catalog_products(engine)
    checks["pgvector_extension_name"] = PGVECTOR_EXTENSION_NAME
    checks["hnsw_index_name"] = PRODUCT_EMBEDDING_HNSW_INDEX_NAME
    return checks


def _engine_from_database_url(database_url: str) -> Engine:
    from sqlalchemy import create_engine

    return create_engine(normalize_database_url(database_url), pool_pre_ping=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap ProductIQ PostgreSQL/pgvector schema.")
    parser.add_argument(
        "--database-url",
        default=None,
        help="Override DATABASE_URL (default: application settings)",
    )
    parser.add_argument(
        "--load-demo-fixture",
        action="store_true",
        help="Load small labeled demo catalog rows for Compose integration smoke tests",
    )
    parser.add_argument(
        "--verify-only",
        action="store_true",
        help="Run contract verification without mutating schema",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print verification JSON to stdout",
    )
    args = parser.parse_args(argv)

    if args.database_url:
        engine = _engine_from_database_url(normalize_database_url(args.database_url))
    else:
        engine = create_engine_from_settings(get_settings())

    try:
        if args.verify_only:
            report = verify_compose_database_contract(engine)
        else:
            bootstrap_productiq_database(engine)
            if args.load_demo_fixture:
                load_compose_integration_demo_catalog(engine)
            report = verify_compose_database_contract(engine)
        if args.json:
            print(json.dumps(report, indent=2, sort_keys=True))
        else:
            print(json.dumps({k: report[k] for k in sorted(report)}, indent=2))
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
