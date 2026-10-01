"""Recommendation API route (Phase 13.4)."""

from __future__ import annotations

from fastapi import APIRouter

from productiq.api.dependencies import RecommendationServiceDep, RequestIdDep
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
)

recommendations_router = APIRouter(tags=["recommendations"])


@recommendations_router.post("/recommendations", response_model=RecommendationApiResponse)
def post_recommendations(
    body: RecommendationApiRequest,
    service: RecommendationServiceDep,
    request_id: RequestIdDep,
) -> RecommendationApiResponse:
    return service.recommend(body, request_id=request_id)


__all__ = ["post_recommendations", "recommendations_router"]
