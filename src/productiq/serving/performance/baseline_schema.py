"""Performance baseline and regression contracts (Phase 13.8.7)."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from productiq.serving.performance.concurrency_schema import BenchmarkBoundary
from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.schema import (
    BenchmarkErrorSummary,
    LatencyStatistics,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceEndpoint,
    ThroughputStatistics,
)

PERFORMANCE_BASELINE_CONTRACT_VERSION = "1.0.0"


class BaselineLookupStatus(StrEnum):
    FOUND = "found"
    BASELINE_NOT_FOUND = "baseline_not_found"


class ProvenanceCompatibilityStatus(StrEnum):
    COMPATIBLE = "compatible"
    INCOMPATIBLE = "incompatible"


class BenchmarkRunIdentity(BaseModel):
    """Deterministic identity for a single benchmark measurement configuration."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    endpoint: ServingPerformanceEndpoint
    workload_id: str = Field(min_length=1)
    benchmark_boundary: BenchmarkBoundary
    concurrency: int = Field(ge=1)
    warmups: int = Field(ge=0)
    iterations: int = Field(ge=1)

    def storage_key(self) -> str:
        return (
            f"{self.endpoint.value}_{self.benchmark_boundary}_"
            f"{self.workload_id}_w{self.warmups}_i{self.iterations}_c{self.concurrency}"
        )


class ServingPerformanceBaselineRecord(BaseModel):
    """Pinned baseline tied to a specific benchmark configuration and result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=PERFORMANCE_BASELINE_CONTRACT_VERSION, min_length=1)
    performance_contract_version: str = Field(
        default=SERVING_PERFORMANCE_CONTRACT_VERSION,
        min_length=1,
    )
    baseline_id: str = Field(min_length=1)
    identity: BenchmarkRunIdentity
    environment: ServingEnvironmentMetadata
    serving_configuration: ServingConfigurationMetadata
    result: ServingBenchmarkRunResult
    pinned_at_utc: datetime
    source_artifact_path: str | None = None
    notes: str | None = None


class ProvenanceCompatibilityResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: ProvenanceCompatibilityStatus
    compatible: bool
    mismatches: tuple[str, ...] = ()
    provenance_differences: tuple[str, ...] = ()


class LatencyMetricComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline: LatencyStatistics
    current: LatencyStatistics
    absolute_delta_ms: dict[str, float]
    relative_delta_pct: dict[str, float | None]


class ReliabilityMetricComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline: BenchmarkErrorSummary
    current: BenchmarkErrorSummary
    success_count_delta: int
    error_count_delta: int
    error_rate_delta: float


class ThroughputMetricComparison(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    baseline_rps: float | None
    current_rps: float | None
    absolute_delta_rps: float | None
    relative_delta_pct: float | None


class PerformanceThresholdPolicy(BaseModel):
    """Optional thresholds; default comparison is descriptive only."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    latency_p95_relative_pct_increase: float | None = Field(
        default=None,
        ge=0.0,
        description="Flag when current p95 exceeds baseline by this percent.",
    )
    latency_p95_absolute_ms_increase: float | None = Field(default=None, ge=0.0)
    throughput_relative_pct_decrease: float | None = Field(default=None, ge=0.0)
    error_rate_absolute_increase: float | None = Field(default=None, ge=0.0)


class ThresholdObservation(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metric: str = Field(min_length=1)
    baseline_value: float | None
    current_value: float | None
    absolute_delta: float | None
    relative_delta_pct: float | None
    threshold: float | None
    observation: str = Field(min_length=1)
    regression_flag: bool = False


class PerformanceComparisonReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=PERFORMANCE_BASELINE_CONTRACT_VERSION, min_length=1)
    identity: BenchmarkRunIdentity
    compatibility: ProvenanceCompatibilityResult
    baseline_run_id: str | None = None
    current_run_id: str | None = None
    baseline_pinned_at_utc: datetime | None = None
    current_recorded_at_utc: datetime | None = None
    latency_comparison: LatencyMetricComparison | None = None
    throughput_comparison: ThroughputMetricComparison | None = None
    reliability_comparison: ReliabilityMetricComparison | None = None
    threshold_policy: PerformanceThresholdPolicy | None = None
    threshold_observations: tuple[ThresholdObservation, ...] = ()
    regression_flags: tuple[str, ...] = ()
    limitations: tuple[str, ...] = (
        "Comparison reports measurement deltas only; it does not select a winner.",
        "No statistical significance testing is performed in Phase 13.8.7.",
    )

    @model_validator(mode="after")
    def validate_comparison_presence(self) -> Self:
        if self.compatibility.compatible and self.latency_comparison is None:
            if self.baseline_run_id is not None:
                msg = "compatible comparison requires latency_comparison when baseline is present"
                raise ValueError(msg)
        return self


class BaselineLookupResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    status: BaselineLookupStatus
    baseline: ServingPerformanceBaselineRecord | None = None
    identity: BenchmarkRunIdentity


__all__ = [
    "PERFORMANCE_BASELINE_CONTRACT_VERSION",
    "BaselineLookupResult",
    "BaselineLookupStatus",
    "BenchmarkRunIdentity",
    "LatencyMetricComparison",
    "PerformanceComparisonReport",
    "PerformanceThresholdPolicy",
    "ProvenanceCompatibilityResult",
    "ProvenanceCompatibilityStatus",
    "ReliabilityMetricComparison",
    "ServingPerformanceBaselineRecord",
    "ThresholdObservation",
    "ThroughputMetricComparison",
]
