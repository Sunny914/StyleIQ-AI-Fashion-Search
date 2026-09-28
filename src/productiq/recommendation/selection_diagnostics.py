"""Selection diagnostics (Phase 11.6)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from productiq.recommendation.contracts import RankedRecommendation


class RecommendationSelectionDecision(StrEnum):
    SELECTED = "selected"
    REJECTED = "rejected"


class RecommendationSelectionRejectionReason(StrEnum):
    SEED_EXCLUDED = "seed_excluded"
    DUPLICATE_PRODUCT = "duplicate_product"
    FILTER_CONSTRAINT = "filter_constraint"
    FILTER_METADATA_MISSING = "filter_metadata_missing"
    MAX_PER_BRAND = "max_per_brand"
    MAX_PER_PRODUCT_TYPE = "max_per_product_type"


class RecommendationSelectionDiagnostic(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    decision: RecommendationSelectionDecision
    reason: RecommendationSelectionRejectionReason | None = None
    input_rank: int | None = Field(default=None, ge=1)
    recommendation_score: float | None = None


class RecommendationSelectionResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    selected: tuple[RankedRecommendation, ...] = ()
    diagnostics: tuple[RecommendationSelectionDiagnostic, ...] = ()


def selection_result_to_dict(result: RecommendationSelectionResult) -> dict[str, Any]:
    return result.model_dump(mode="json")


__all__ = [
    "RecommendationSelectionDecision",
    "RecommendationSelectionDiagnostic",
    "RecommendationSelectionRejectionReason",
    "RecommendationSelectionResult",
    "selection_result_to_dict",
]
