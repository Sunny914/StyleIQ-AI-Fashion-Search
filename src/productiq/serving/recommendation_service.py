"""Production recommendation orchestration at the serving boundary (Phase 13.4)."""

from __future__ import annotations

import time

from productiq.observability.runtime.serving import (
    emit_recommendation_generation_completed,
    emit_recommendation_request_completed,
    measure_ms,
)
from productiq.recommendation.contracts import RecommendationRequest
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.serving.mappers import recommendation_response_to_api
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
)


class ProductionRecommendationServingService:
    """Application recommendation service: API contract → RecommendationPipeline → API mapping."""

    def __init__(self, pipeline: RecommendationPipeline) -> None:
        self._pipeline = pipeline

    def recommend(
        self,
        request: RecommendationApiRequest,
        *,
        request_id: str,
    ) -> RecommendationApiResponse:
        total_start = time.perf_counter()
        domain_request = RecommendationRequest(
            seed_product_id=request.seed_product_id,
            recommendation_type=request.recommendation_type,
            top_k=request.top_k,
            filters=request.filters,
        )
        pipeline_result = self._pipeline.recommend_with_metadata(domain_request)
        response = recommendation_response_to_api(pipeline_result.response, request_id=request_id)
        duration_ms = measure_ms(total_start)
        emit_recommendation_request_completed(
            duration_ms=duration_ms,
            recommendation_type=str(request.recommendation_type.value),
            result_count=response.returned_count,
            top_k=request.top_k,
        )
        emit_recommendation_generation_completed(
            duration_ms=duration_ms,
            candidate_count=pipeline_result.execution.candidate_count,
        )
        return response


__all__ = ["ProductionRecommendationServingService"]
