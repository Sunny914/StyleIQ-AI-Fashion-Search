"""Production ranking stage configuration (Phase 10.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from productiq.ranking.baseline_config import BaselineRankingConfig
from productiq.ranking.hardening.config import ExperimentalLTRRankingConfig

RANKING_PIPELINE_INTEGRATION_VERSION = "10.5.0"
RETRIEVAL_ORDER_RANKING_VERSION = "10.5.0-retrieval-order"


class ProductionRankingStageConfig(BaseModel):
    """Deterministic ranking stage settings for production search integration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    enabled: bool = Field(
        default=True,
        description="When false, retrieve_ranked preserves retrieval order without baseline scoring.",
    )
    baseline_config: BaselineRankingConfig = Field(default_factory=BaselineRankingConfig)
    experimental_ltr: ExperimentalLTRRankingConfig = Field(
        default_factory=ExperimentalLTRRankingConfig,
        description="Opt-in offline LTR settings; retrieve_ranked does not use LTR.",
    )


__all__ = [
    "RANKING_PIPELINE_INTEGRATION_VERSION",
    "RETRIEVAL_ORDER_RANKING_VERSION",
    "ExperimentalLTRRankingConfig",
    "ProductionRankingStageConfig",
]
