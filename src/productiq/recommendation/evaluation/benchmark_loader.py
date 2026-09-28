"""Load recommendation evaluation benchmarks (Phase 11.7)."""

from __future__ import annotations

import json
from pathlib import Path

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.evaluation.benchmark_schema import RecommendationBenchmark


def load_recommendation_benchmark(path: Path) -> RecommendationBenchmark:
    if not path.is_file():
        msg = f"recommendation benchmark not found: {path}"
        raise RecommendationError(msg)
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        return RecommendationBenchmark.model_validate(raw)
    except Exception as exc:
        msg = f"invalid recommendation benchmark JSON: {exc}"
        raise RecommendationError(msg) from exc


__all__ = ["load_recommendation_benchmark"]
