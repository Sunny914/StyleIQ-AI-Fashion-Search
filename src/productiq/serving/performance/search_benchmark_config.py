"""Search serving performance benchmark settings (Phase 13.8.3)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class SearchServingBenchmarkSettings(BaseModel):
    """Warm steady-state measurement defaults (concurrency baseline = 1 for 13.8.3)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    warmups: int = Field(default=5, ge=0)
    iterations: int = Field(default=30, ge=1)
    concurrency: int = Field(default=1, ge=1)


DEFAULT_SEARCH_SERVING_BENCHMARK_SETTINGS = SearchServingBenchmarkSettings()


__all__ = ["DEFAULT_SEARCH_SERVING_BENCHMARK_SETTINGS", "SearchServingBenchmarkSettings"]
