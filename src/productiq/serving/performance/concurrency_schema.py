"""Concurrency sweep result contracts (Phase 13.8.6)."""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.schema import (
    ServingBenchmarkRunResult,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceEndpoint,
)

CONCURRENCY_SWEEP_CONTRACT_VERSION = "1.0.0"

BenchmarkBoundary = Literal["api", "service"]


class ConcurrencySweepConfiguration(BaseModel):
    """Describes one endpoint/boundary sweep (workload fixed across concurrency levels)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=CONCURRENCY_SWEEP_CONTRACT_VERSION, min_length=1)
    performance_contract_version: str = Field(
        default=SERVING_PERFORMANCE_CONTRACT_VERSION,
        min_length=1,
    )
    endpoint: ServingPerformanceEndpoint
    workload_id: str = Field(min_length=1)
    benchmark_boundary: BenchmarkBoundary
    warmups: int = Field(ge=0)
    iterations: int = Field(ge=1)
    concurrency_levels: tuple[int, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_levels(self) -> Self:
        if any(level < 1 for level in self.concurrency_levels):
            msg = "concurrency_levels must be >= 1"
            raise ValueError(msg)
        return self


class ConcurrencyBenchmarkSweepResult(BaseModel):
    """Aggregated results for one workload at multiple concurrency levels."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=CONCURRENCY_SWEEP_CONTRACT_VERSION, min_length=1)
    sweep_configuration: ConcurrencySweepConfiguration
    sweep_run_id: str = Field(min_length=1)
    recorded_at_utc: datetime
    environment: ServingEnvironmentMetadata
    serving_configuration: ServingConfigurationMetadata
    run_results: tuple[ServingBenchmarkRunResult, ...] = Field(min_length=1)
    thread_safety_notes: tuple[str, ...] = ()
    limitations: tuple[str, ...] = (
        "Descriptive measurements only; no configuration is ranked or recommended.",
        "Throughput uses successful requests divided by measured wall time per level.",
        "Warmups are executed independently at each concurrency level.",
    )

    @model_validator(mode="after")
    def validate_run_alignment(self) -> Self:
        expected_levels = set(self.sweep_configuration.concurrency_levels)
        observed_levels = {
            result.configuration.concurrency for result in self.run_results
        }
        if observed_levels != expected_levels:
            msg = "run_results concurrency levels must match sweep_configuration"
            raise ValueError(msg)
        for result in self.run_results:
            if result.configuration.workload_id != self.sweep_configuration.workload_id:
                msg = "all run_results must share the sweep workload_id"
                raise ValueError(msg)
            if result.workload.workload_id != self.sweep_configuration.workload_id:
                msg = "all run_results workloads must match sweep workload_id"
                raise ValueError(msg)
        return self


class ConcurrencyBenchmarkSuiteResult(BaseModel):
    """Optional bundle of API/service sweeps across endpoints."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=CONCURRENCY_SWEEP_CONTRACT_VERSION, min_length=1)
    suite_run_id: str = Field(min_length=1)
    recorded_at_utc: datetime
    sweeps: tuple[ConcurrencyBenchmarkSweepResult, ...] = Field(min_length=1)


__all__ = [
    "CONCURRENCY_SWEEP_CONTRACT_VERSION",
    "BenchmarkBoundary",
    "ConcurrencyBenchmarkSuiteResult",
    "ConcurrencyBenchmarkSweepResult",
    "ConcurrencySweepConfiguration",
]
