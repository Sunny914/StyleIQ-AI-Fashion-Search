"""Recommendation selection and diversity configuration (Phase 11.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

RECOMMENDATION_SELECTION_CONFIG_VERSION = "11.6.0"


class RecommendationSelectionConfig(BaseModel):
    """Deterministic post-ranking selection and diversity limits."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    selection_version: str = Field(
        default=RECOMMENDATION_SELECTION_CONFIG_VERSION,
        min_length=1,
    )
    strict_constraints: bool = Field(
        default=True,
        description="When True, hard filter constraints and missing metadata reject candidates.",
    )
    max_per_brand: int | None = Field(
        default=None,
        ge=1,
        description="Maximum selected recommendations sharing the same brand key (None disables).",
    )
    max_per_product_type: int | None = Field(
        default=None,
        ge=1,
        description="Maximum selected recommendations sharing the same product_type key (None disables).",
    )


__all__ = [
    "RECOMMENDATION_SELECTION_CONFIG_VERSION",
    "RecommendationSelectionConfig",
]
