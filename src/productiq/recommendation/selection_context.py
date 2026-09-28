"""Context supplied to recommendation selection (Phase 11.6)."""

from __future__ import annotations

from collections.abc import Mapping

from pydantic import BaseModel, ConfigDict, Field

from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.representation.schema import ProductRepresentation


class RecommendationSelectionContext(BaseModel):
    """Injected catalog metadata for hard constraints and diversity keys (no I/O)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str | None = None
    filtering_by_product_id: Mapping[str, FilteringRepresentation] = Field(default_factory=dict)
    product_by_product_id: Mapping[str, ProductRepresentation] = Field(default_factory=dict)
    query_constraints: QueryFilterConstraints | None = None


__all__ = ["RecommendationSelectionContext"]
