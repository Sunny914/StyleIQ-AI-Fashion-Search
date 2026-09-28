"""Ranking pipeline hardening (Phase 10.9)."""

from __future__ import annotations

import importlib
from typing import Any

from productiq.ranking.hardening.config import (
    RANKING_FAILURE_ANALYSIS_VERSION,
    RANKING_HARDENING_VERSION,
    ExperimentalLTRRankingConfig,
)

__all__ = [
    "RANKING_FAILURE_ANALYSIS_VERSION",
    "RANKING_HARDENING_VERSION",
    "ExperimentalLTRRankingConfig",
    "assert_retrieve_ranked_uses_baseline_path",
    "load_experimental_ltr_artifact",
    "resolve_production_ranking_mode",
]

_LAZY = {
    "assert_retrieve_ranked_uses_baseline_path": "production_safety",
    "load_experimental_ltr_artifact": "production_safety",
    "resolve_production_ranking_mode": "production_safety",
}


def __getattr__(name: str) -> Any:
    if name not in _LAZY:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module = importlib.import_module(f"{__name__}.{_LAZY[name]}")
    return getattr(module, name)
