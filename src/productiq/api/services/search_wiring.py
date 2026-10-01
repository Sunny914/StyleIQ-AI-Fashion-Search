"""Search route wiring helpers for the HTTP adapter (Phase 13.3)."""

from __future__ import annotations

from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.serving.protocols import SearchServingService
from productiq.serving.search_service import ProductionSearchServingService


def create_search_serving_service_from_pipeline(
    pipeline: ProductionRetrievalPipeline,
) -> SearchServingService:
    """Wrap an existing production retrieval pipeline for HTTP serving."""
    return ProductionSearchServingService(pipeline)


__all__ = ["create_search_serving_service_from_pipeline"]
