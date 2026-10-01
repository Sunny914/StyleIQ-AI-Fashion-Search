"""Construct ApplicationServices using service-specific wiring helpers (Phase 13.6)."""

from __future__ import annotations

from pathlib import Path

from productiq.api.services.application_services import ApplicationServices
from productiq.api.services.product_wiring import (
    create_product_serving_service_from_catalog,
    create_product_serving_service_from_processed_parquet,
)
from productiq.api.services.recommendation_wiring import (
    create_recommendation_serving_service_from_pipeline,
)
from productiq.api.services.search_wiring import create_search_serving_service_from_pipeline
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.serving.catalog_read import ProductCatalogReadProvider
from productiq.serving.config import ServingConfig
from productiq.serving.protocols import (
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)


def build_application_services(
    *,
    serving_config: ServingConfig | None = None,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
    search_pipeline: ProductionRetrievalPipeline | None = None,
    recommendation_pipeline: RecommendationPipeline | None = None,
    catalog: ProductCatalogReadProvider | None = None,
    processed_catalog_parquet: Path | None = None,
) -> ApplicationServices:
    """Single composition root for HTTP serving services."""
    config = serving_config or ServingConfig()
    resolved_search = search_service
    if resolved_search is None and search_pipeline is not None:
        resolved_search = create_search_serving_service_from_pipeline(search_pipeline)
    resolved_recommendation = recommendation_service
    if resolved_recommendation is None and recommendation_pipeline is not None:
        resolved_recommendation = create_recommendation_serving_service_from_pipeline(
            recommendation_pipeline,
        )
    resolved_product = product_service
    if resolved_product is None and catalog is not None:
        resolved_product = create_product_serving_service_from_catalog(catalog)
    elif resolved_product is None and processed_catalog_parquet is not None:
        resolved_product = create_product_serving_service_from_processed_parquet(
            processed_catalog_parquet,
        )
    return ApplicationServices(
        serving_config=config,
        search_service=resolved_search,
        recommendation_service=resolved_recommendation,
        product_service=resolved_product,
    )


__all__ = ["build_application_services"]
