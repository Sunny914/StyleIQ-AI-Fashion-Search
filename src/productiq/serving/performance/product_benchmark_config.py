"""Product serving performance benchmark settings (Phase 13.8.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ProductServingBenchmarkSettings(BaseModel):
    """Warm steady-state measurement defaults (concurrency baseline = 1 for 13.8.5)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    warmups: int = Field(default=5, ge=0)
    iterations: int = Field(default=30, ge=1)
    concurrency: int = Field(default=1, ge=1)


DEFAULT_PRODUCT_SERVING_BENCHMARK_SETTINGS = ProductServingBenchmarkSettings()


__all__ = ["DEFAULT_PRODUCT_SERVING_BENCHMARK_SETTINGS", "ProductServingBenchmarkSettings"]
