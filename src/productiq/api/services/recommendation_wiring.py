"""Recommendation route wiring helpers for the HTTP adapter (Phase 13.4)."""

from __future__ import annotations

from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.serving.protocols import RecommendationServingService
from productiq.serving.recommendation_service import ProductionRecommendationServingService


def create_recommendation_serving_service_from_pipeline(
    pipeline: RecommendationPipeline,
) -> RecommendationServingService:
    """Wrap an existing RecommendationPipeline for HTTP serving."""
    return ProductionRecommendationServingService(pipeline)


__all__ = ["create_recommendation_serving_service_from_pipeline"]
