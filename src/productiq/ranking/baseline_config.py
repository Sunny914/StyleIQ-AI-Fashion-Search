"""Deterministic baseline ranker configuration (Phase 10.4)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.ranking.config import DEFAULT_TIE_BREAK_KEY

BASELINE_RANKER_VERSION = "10.4.0"


class BaselineFeatureWeights(BaseModel):
    """Explicit reference weights (not learned, not tuned in Phase 10.4)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    bm25_score: float = Field(default=0.12, ge=0.0)
    bm25_rank: float = Field(default=0.08, ge=0.0)
    vector_similarity: float = Field(default=0.12, ge=0.0)
    vector_rank: float = Field(default=0.08, ge=0.0)
    rrf_score: float = Field(default=0.18, ge=0.0)
    retrieved_by_bm25: float = Field(default=0.0, ge=0.0)
    retrieved_by_vector: float = Field(default=0.0, ge=0.0)
    retrieved_by_both: float = Field(default=0.03, ge=0.0)
    brand_match: float = Field(default=0.10, ge=0.0)
    color_match: float = Field(default=0.06, ge=0.0)
    product_type_match: float = Field(default=0.05, ge=0.0)
    category_gender_match: float = Field(default=0.04, ge=0.0)
    material_match: float = Field(default=0.03, ge=0.0)
    matched_attribute_count: float = Field(default=0.04, ge=0.0)
    attribute_overlap: float = Field(default=0.07, ge=0.0)
    constraint_match: float = Field(default=0.0, ge=0.0)
    discount_price_inr: float = Field(default=0.0, ge=0.0)
    original_price_inr: float = Field(default=0.0, ge=0.0)
    discount_amount_inr: float = Field(default=0.0, ge=0.0)


class BaselineRankingConfig(BaseModel):
    """Frozen deterministic baseline ranker settings."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_version: str = Field(default=BASELINE_RANKER_VERSION, min_length=1)
    weights: BaselineFeatureWeights = Field(default_factory=BaselineFeatureWeights)
    missing_value_contribution: float = Field(
        default=0.0,
        description=(
            "Score contribution when a normalized feature value is None "
            "(weight * missing_value_contribution; feature remains missing)."
        ),
    )
    tie_break_key: Literal["product_id"] = Field(default=DEFAULT_TIE_BREAK_KEY)

    @model_validator(mode="after")
    def validate_positive_total_weight(self) -> BaselineRankingConfig:
        total = sum(self.weights.model_dump().values())
        if total <= 0.0:
            msg = "baseline feature weights must sum to a positive value"
            raise ValueError(msg)
        return self


__all__ = [
    "BASELINE_RANKER_VERSION",
    "BaselineFeatureWeights",
    "BaselineRankingConfig",
]
