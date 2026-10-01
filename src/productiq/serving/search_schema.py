"""Public search API contracts (Phase 13.1).

Maps to ProductionRetrievalPipeline / ranked search domain paths in Phase 13.2.
Does not duplicate QueryRepresentation or retrieval mechanics.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.representation.query_contract import QueryFilterConstraints
from productiq.serving.config import ServingConfig


def resolve_api_max_top_k() -> int:
    """Resolve the HTTP top_k cap from ServingConfig (env-aware)."""
    return ServingConfig().api_max_top_k


def resolve_api_max_query_length() -> int:
    """Resolve the HTTP query length cap from ServingConfig (env-aware)."""
    return ServingConfig().api_max_query_length


class SearchApiRequest(BaseModel):
    """POST /api/v1/search body (query understanding applied in the service layer)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1, description="Natural-language search query text.")
    top_k: int = Field(gt=0, description="Final ranked results to return.")
    filters: QueryFilterConstraints | None = Field(
        default=None,
        description="Optional hard filters using the existing query/filter facet contract.",
    )

    @model_validator(mode="after")
    def validate_top_k_limit(self) -> SearchApiRequest:
        max_top_k = resolve_api_max_top_k()
        if self.top_k > max_top_k:
            msg = f"top_k must not exceed {max_top_k}"
            raise ValueError(msg)
        max_query = resolve_api_max_query_length()
        if len(self.query) > max_query:
            msg = f"query length must not exceed {max_query}"
            raise ValueError(msg)
        return self


class SearchResultItem(BaseModel):
    """One ranked search hit exposed to API clients (no native BM25/vector diagnostics)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    rank: int = Field(ge=1)


class SearchApiResponse(BaseModel):
    """Search response envelope."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: str = Field(min_length=1, description="Normalized query text echoed for traceability.")
    top_k: int = Field(gt=0)
    results: tuple[SearchResultItem, ...] = ()
    request_id: str = Field(min_length=1)
    returned_count: int = Field(ge=0)


__all__ = [
    "SearchApiRequest",
    "SearchApiResponse",
    "SearchResultItem",
    "resolve_api_max_query_length",
    "resolve_api_max_top_k",
]
