"""Production search orchestration at the serving boundary (Phase 13.3)."""

from __future__ import annotations

import time

from productiq.observability.runtime.emitter import observe_stage
from productiq.observability.runtime.serving import (
    emit_search_request_completed,
    emit_search_stage_from_timings,
    measure_ms,
)
from productiq.observability.tracing import SpanKind
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.serving.mappers import ranked_search_to_api_response
from productiq.serving.search_schema import SearchApiRequest, SearchApiResponse


class ProductionSearchServingService:
    """Application search service: query contract → ranked retrieval → API mapping."""

    def __init__(self, pipeline: ProductionRetrievalPipeline) -> None:
        self._pipeline = pipeline

    def search(self, request: SearchApiRequest, *, request_id: str) -> SearchApiResponse:
        _ = request_id
        total_start = time.perf_counter()
        with observe_stage("search.query_representation", kind=SpanKind.DOMAIN, operation="search"):
            query = build_query_representation(
                request.query,
                constraints=request.filters,
            )
        with observe_stage("search.retrieve_rank", kind=SpanKind.DOMAIN, operation="search"):
            ranked = self._pipeline.retrieve_ranked(
                RetrievalRequest(query=query, top_k=request.top_k),
            )
        with observe_stage("search.response_mapping", kind=SpanKind.SERVING, operation="search"):
            response = ranked_search_to_api_response(
                ranked,
                query=query.query_text,
                top_k=request.top_k,
                request_id=request_id,
            )
        duration_ms = measure_ms(total_start)
        emit_search_request_completed(
            duration_ms=duration_ms,
            result_count=response.returned_count,
            top_k=request.top_k,
            query_length=len(request.query),
            candidate_count=ranked.candidate_count_after_filter,
        )
        timings = ranked.timings_ms
        if timings is not None:
            emit_search_stage_from_timings(
                retrieval_ms=timings.retrieval_ms,
                ranking_ms=timings.ranking_ms,
                candidate_count=ranked.candidate_count_after_filter,
                result_count=response.returned_count,
            )
        return response


__all__ = ["ProductionSearchServingService"]
