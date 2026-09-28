"""Recommendation layer configuration (Phase 11.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_RECOMMENDATION_CONTRACT_VERSION = "11.1.0"
DEFAULT_RECOMMENDATION_TIE_BREAK_KEY: Literal["product_id"] = "product_id"
DEFAULT_MAX_RECOMMENDATION_TOP_K = 100


class RecommendationConfig(BaseModel):
    """Frozen recommendation contract metadata (no retrieval or ranker parameters in 11.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    recommendation_contract_version: str = Field(
        default=DEFAULT_RECOMMENDATION_CONTRACT_VERSION,
        min_length=1,
        description="Recommendation contract / orchestration version label.",
    )
    max_top_k: int = Field(
        default=DEFAULT_MAX_RECOMMENDATION_TOP_K,
        gt=0,
        description="Upper bound for RecommendationRequest.top_k at the contract layer.",
    )
    tie_break_key: Literal["product_id"] = Field(
        default=DEFAULT_RECOMMENDATION_TIE_BREAK_KEY,
        description="Stable secondary key when recommendation scores tie (deterministic ordering).",
    )


__all__ = [
    "DEFAULT_MAX_RECOMMENDATION_TOP_K",
    "DEFAULT_RECOMMENDATION_CONTRACT_VERSION",
    "DEFAULT_RECOMMENDATION_TIE_BREAK_KEY",
    "RecommendationConfig",
]
