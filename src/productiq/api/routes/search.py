"""Search API route (Phase 13.3)."""

from __future__ import annotations

from fastapi import APIRouter

from productiq.api.dependencies import RequestIdDep, SearchServiceDep
from productiq.serving.search_schema import SearchApiRequest, SearchApiResponse

search_router = APIRouter(tags=["search"])


@search_router.post("/search", response_model=SearchApiResponse)
def post_search(
    body: SearchApiRequest,
    service: SearchServiceDep,
    request_id: RequestIdDep,
) -> SearchApiResponse:
    return service.search(body, request_id=request_id)


__all__ = ["post_search", "search_router"]
