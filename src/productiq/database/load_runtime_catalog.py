"""Explicit catalog + embedding load for Compose (Phase 15C).

Reuses ProductCatalogLoader and vector index builders. Does not run at API import.
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine

from data.export.schema import AJIO_PROCESSED_ROW_COUNT
from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.settings import get_settings
from productiq.database.bootstrap_compose import (
    FIXTURE_PRODUCT_ID_PREFIX,
    bootstrap_productiq_database,
    load_compose_integration_demo_catalog,
    verify_compose_database_contract,
)
from productiq.database.catalog_pipeline import load_processed_catalog
from productiq.database.engine import create_engine_from_settings, normalize_database_url
from productiq.database.vector_catalog import count_catalog_products, count_products_with_embeddings
from productiq.logging import get_logger
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.vector_index_builder import build_product_vector_index

FULL_CATALOG_ROW_COUNT = AJIO_PROCESSED_ROW_COUNT
CATALOG_MODE_FIXTURE = "fixture"
CATALOG_MODE_FULL = "full"
CATALOG_MODE_PARTIAL = "partial"
CATALOG_MODE_EMPTY = "empty"


@dataclass(frozen=True)
class CatalogRuntimeStatus:
    """Safe catalog/data status for readiness and audits (no secrets)."""

    mode: str
    product_count: int
    embedding_count: int
    expected_full_count: int = FULL_CATALOG_ROW_COUNT
    fixture_prefix: str = FIXTURE_PRODUCT_ID_PREFIX


def classify_catalog_mode(product_count: int, *, fixture_id_count: int = 0) -> str:
    """Label catalog contents so fixture rows cannot be confused with the full AJIO set."""
    if product_count <= 0:
        return CATALOG_MODE_EMPTY
    if product_count == FULL_CATALOG_ROW_COUNT:
        return CATALOG_MODE_FULL
    if product_count <= 32 and fixture_id_count == product_count:
        return CATALOG_MODE_FIXTURE
    return CATALOG_MODE_PARTIAL


def inspect_catalog_runtime_status(engine: Engine) -> CatalogRuntimeStatus:
    from sqlalchemy import text

    product_count = count_catalog_products(engine)
    embedding_count = count_products_with_embeddings(engine)
    fixture_id_count = 0
    if product_count > 0:
        sql = text(
            "SELECT COUNT(*) FROM products WHERE product_id LIKE :prefix",
        )
        with engine.connect() as connection:
            fixture_id_count = int(
                connection.execute(sql, {"prefix": f"{FIXTURE_PRODUCT_ID_PREFIX}%"}).scalar_one(),
            )
    mode = classify_catalog_mode(product_count, fixture_id_count=fixture_id_count)
    return CatalogRuntimeStatus(
        mode=mode,
        product_count=product_count,
        embedding_count=embedding_count,
    )


def load_runtime_catalog(
    engine: Engine,
    *,
    mode: str,
    catalog_parquet: Path | None = None,
    embeddings_parquet: Path | None = None,
    expected_row_count: int | None = None,
    max_embedding_rows: int | None = None,
    enforce_official_checksums: bool = False,
    vector_manifest_dir: Path | None = None,
) -> dict[str, Any]:
    """Bootstrap schema and load catalog rows + embeddings.

    ``mode=fixture`` inserts labeled compose-demo rows (not the 367k catalog).
    ``mode=full`` upserts the processed Parquet and loads embedding vectors.
    Upserts are restartable: catalog uses ON CONFLICT product_id; embeddings UPDATE by id.
    """
    logger = get_logger(__name__)
    bootstrap_productiq_database(engine)
    report: dict[str, Any] = {"mode": mode, "dimension": PRODUCTIQ_EMBEDDING_DIMENSION}

    if mode == CATALOG_MODE_FIXTURE:
        inserted = load_compose_integration_demo_catalog(engine)
        report["fixture_rows_upserted"] = inserted
        logger.info("Loaded labeled compose-demo fixture rows: %s", inserted)
    elif mode in {CATALOG_MODE_FULL, CATALOG_MODE_PARTIAL}:
        if catalog_parquet is None:
            msg = "catalog parquet path is required for full/partial load"
            raise ValueError(msg)
        expected = expected_row_count
        if mode == CATALOG_MODE_FULL and expected is None:
            expected = FULL_CATALOG_ROW_COUNT
        pipeline = load_processed_catalog(
            catalog_parquet,
            engine=engine,
            expected_row_count=expected,
            create_tables=True,
            validate_after_load=True,
        )
        report["catalog_rows_after"] = pipeline.load_report.catalog_row_count_after
        report["catalog_rows_upserted"] = pipeline.load_report.rows_upserted
        if embeddings_parquet is not None:
            vector_result = build_product_vector_index(
                engine,
                embeddings_parquet,
                output_dir=vector_manifest_dir,
                max_rows=max_embedding_rows,
                enforce_official_checksums=enforce_official_checksums,
            )
            report["vectors_loaded"] = vector_result.vectors_in_database
            report["hnsw_index_present"] = vector_result.hnsw_index_present
    else:
        msg = f"unsupported load mode: {mode}"
        raise ValueError(msg)

    status = inspect_catalog_runtime_status(engine)
    report["catalog_status"] = asdict(status)
    report["schema"] = verify_compose_database_contract(engine)
    return report


def _engine_from_url(database_url: str | None) -> Engine:
    if database_url:
        from sqlalchemy import create_engine

        return create_engine(normalize_database_url(database_url), pool_pre_ping=True)
    return create_engine_from_settings(get_settings())


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load ProductIQ catalog/embeddings into PostgreSQL (explicit operator step).",
    )
    parser.add_argument("--database-url", default=None)
    parser.add_argument(
        "--mode",
        choices=(CATALOG_MODE_FIXTURE, CATALOG_MODE_FULL, CATALOG_MODE_PARTIAL),
        default=CATALOG_MODE_FIXTURE,
        help="fixture = 3 labeled demo rows; full = 367172-row processed catalog",
    )
    parser.add_argument("--catalog-parquet", type=Path, default=None)
    parser.add_argument("--embeddings-parquet", type=Path, default=None)
    parser.add_argument("--expected-row-count", type=int, default=None)
    parser.add_argument("--max-embedding-rows", type=int, default=None)
    parser.add_argument("--enforce-official-checksums", action="store_true")
    parser.add_argument(
        "--vector-manifest-dir",
        type=Path,
        default=None,
        help="Writable directory for the vector-index manifest. Defaults to the embeddings directory.",
    )
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    settings = get_settings()
    paths = resolve_runtime_artifact_paths(settings)
    catalog_path = args.catalog_parquet or paths.processed_catalog
    embeddings_path = args.embeddings_parquet or paths.embeddings
    engine = _engine_from_url(args.database_url)
    try:
        report = load_runtime_catalog(
            engine,
            mode=args.mode,
            catalog_parquet=catalog_path if args.mode != CATALOG_MODE_FIXTURE else None,
            embeddings_parquet=embeddings_path if args.mode != CATALOG_MODE_FIXTURE else None,
            expected_row_count=args.expected_row_count,
            max_embedding_rows=args.max_embedding_rows,
            enforce_official_checksums=args.enforce_official_checksums,
            vector_manifest_dir=args.vector_manifest_dir,
        )
        payload = json.dumps(report, indent=2, sort_keys=True, default=str)
        print(payload)
        return 0
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
