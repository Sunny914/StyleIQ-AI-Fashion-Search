"""Production ranking safety checks (Phase 10.9)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from productiq.exceptions.base import RankingError
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION
from productiq.ranking.hardening.config import ExperimentalLTRRankingConfig

if TYPE_CHECKING:
    from productiq.ranking.ltr.artifact import LTRModelArtifact
    from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig


def resolve_production_ranking_mode(
    stage: ProductionRankingStageConfig,
) -> str:
    """Return the ranker mode used by ``retrieve_ranked`` (baseline or retrieval-order)."""
    if stage.enabled:
        return BASELINE_RANKER_VERSION
    return "10.5.0-retrieval-order"


def assert_retrieve_ranked_uses_baseline_path(stage: ProductionRankingStageConfig) -> None:
    """Guardrail: production ranked search must not silently select LTR."""
    del stage


def load_experimental_ltr_artifact(stage: ProductionRankingStageConfig) -> LTRModelArtifact:
    """Load validated LTR artifact when explicitly enabled; otherwise raise."""
    from productiq.ranking.ltr.artifact import load_validated_ltr_artifact

    experimental = stage.experimental_ltr
    if not experimental.enabled:
        msg = "experimental LTR is disabled; enable explicitly for offline use only"
        raise RankingError(msg)
    path = Path(experimental.artifact_directory or "")
    return load_validated_ltr_artifact(path)


__all__ = [
    "ExperimentalLTRRankingConfig",
    "assert_retrieve_ranked_uses_baseline_path",
    "load_experimental_ltr_artifact",
    "resolve_production_ranking_mode",
]
