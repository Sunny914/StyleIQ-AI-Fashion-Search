"""Product route wiring helpers for the HTTP adapter (Phase 13.5)."""

from __future__ import annotations

from pathlib import Path

from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.settings import Settings, get_settings
from productiq.serving.catalog_read import ProductCatalogReadProvider
from productiq.serving.processed_catalog_provider import create_processed_parquet_catalog_provider
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.protocols import ProductServingService


def resolved_processed_catalog_path(settings: Settings | None = None) -> Path:
    """Return configured processed catalog path (no file I/O)."""
    resolved_settings = settings or get_settings()
    return resolve_runtime_artifact_paths(resolved_settings).processed_catalog


def create_product_serving_service_from_settings(
    settings: Settings | None = None,
) -> ProductServingService:
    """Wire product serving using the 14A/14B catalog path."""
    return create_product_serving_service_from_processed_parquet(
        resolved_processed_catalog_path(settings),
    )


def create_product_serving_service_from_catalog(
    catalog: ProductCatalogReadProvider,
) -> ProductServingService:
    return ProductionProductServingService(catalog)


def create_product_serving_service_from_processed_parquet(
    parquet_path: Path,
) -> ProductServingService:
    catalog = create_processed_parquet_catalog_provider(parquet_path)
    return ProductionProductServingService(catalog)


__all__ = [
    "create_product_serving_service_from_catalog",
    "create_product_serving_service_from_processed_parquet",
    "create_product_serving_service_from_settings",
    "resolved_processed_catalog_path",
]
