"""Product context for recommendation feature extraction (Phase 11.4)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.representation.filtering import FilteringRepresentation


class RecommendationProductContext(BaseModel):
    """Injected catalog metadata for one candidate (no database loading)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    filtering: FilteringRepresentation | None = None

    @model_validator(mode="after")
    def validate_filtering_alignment(self) -> RecommendationProductContext:
        if self.filtering is not None and self.filtering.product_id != self.product_id:
            msg = "filtering.product_id must match RecommendationProductContext.product_id"
            raise ValueError(msg)
        return self


__all__ = ["RecommendationProductContext"]
