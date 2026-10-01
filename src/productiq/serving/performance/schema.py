"""Serving performance benchmark contracts (Phase 13.8.1).

Separate from search/recommendation *relevance* evaluation benchmarks.
Measures latency/throughput only.
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.statistics import compute_latency_statistics_ms
from productiq.serving.versioning import (
    PLANNED_ROUTE_PRODUCT,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
)


class ServingBenchmarkType(StrEnum):
    """How the benchmark driver invokes the system under test."""

    API = "api"
    SERVICE = "service"
    CONCURRENCY = "concurrency"
    PRODUCTION_SMOKE = "production_smoke"


class ServingPerformanceEndpoint(StrEnum):
    SEARCH = "search"
    RECOMMENDATION = "recommendation"
    PRODUCT = "product"
    HEALTH = "health"
    READY = "ready"


class LatencyMeasurementUnit(StrEnum):
    MILLISECONDS = "ms"


class ThroughputMeasurementUnit(StrEnum):
    REQUESTS_PER_SECOND = "requests_per_second"


class ServingBenchmarkConfiguration(BaseModel):
    """Measurement plan for one benchmark run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=SERVING_PERFORMANCE_CONTRACT_VERSION, min_length=1)
    benchmark_type: ServingBenchmarkType
    endpoint: ServingPerformanceEndpoint
    workload_id: str = Field(min_length=1)
    iterations: int = Field(ge=1, description="Measured iterations after warmups.")
    warmups: int = Field(ge=0, description="Discarded warmup iterations.")
    concurrency: int = Field(ge=1, description="Concurrent workers for concurrency benchmarks.")

    @field_validator("workload_id")
    @classmethod
    def strip_workload_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "workload_id must not be empty"
            raise ValueError(msg)
        return stripped


class ServingPerformanceWorkload(BaseModel):
    """Deterministic request description for a serving benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workload_id: str = Field(min_length=1)
    workload_name: str = Field(min_length=1)
    endpoint: ServingPerformanceEndpoint
    http_method: Literal["GET", "POST"]
    route_path: str = Field(min_length=1)
    request_body: dict[str, Any] | None = None
    path_parameters: dict[str, str] = Field(default_factory=dict)
    description: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_route_alignment(self) -> Self:
        if (
            self.endpoint is ServingPerformanceEndpoint.SEARCH
            and self.route_path != PLANNED_ROUTE_SEARCH
        ):
            msg = "search workload must target POST /api/v1/search"
            raise ValueError(msg)
        if (
            self.endpoint is ServingPerformanceEndpoint.RECOMMENDATION
            and self.route_path != PLANNED_ROUTE_RECOMMENDATIONS
        ):
            msg = "recommendation workload must target POST /api/v1/recommendations"
            raise ValueError(msg)
        if (
            self.endpoint is ServingPerformanceEndpoint.PRODUCT
            and self.route_path != PLANNED_ROUTE_PRODUCT
        ):
            msg = "product workload must use GET /api/v1/products/{product_id} template"
            raise ValueError(msg)
        return self


class LatencyStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit: LatencyMeasurementUnit = LatencyMeasurementUnit.MILLISECONDS
    sample_count: int = Field(ge=1)
    min_ms: float = Field(ge=0.0)
    p50_ms: float = Field(ge=0.0)
    p95_ms: float = Field(ge=0.0)
    p99_ms: float = Field(ge=0.0)
    max_ms: float = Field(ge=0.0)
    mean_ms: float = Field(ge=0.0)

    @model_validator(mode="after")
    def validate_ordering(self) -> Self:
        if not (self.min_ms <= self.p50_ms <= self.p95_ms <= self.p99_ms <= self.max_ms):
            msg = "latency percentiles must be monotonic (min ≤ p50 ≤ p95 ≤ p99 ≤ max)"
            raise ValueError(msg)
        return self

    @classmethod
    def from_samples_ms(cls, samples_ms: tuple[float, ...]) -> LatencyStatistics:
        stats = compute_latency_statistics_ms(samples_ms)
        return cls(
            sample_count=int(stats["sample_count"]),
            min_ms=float(stats["min_ms"]),
            p50_ms=float(stats["p50_ms"]),
            p95_ms=float(stats["p95_ms"]),
            p99_ms=float(stats["p99_ms"]),
            max_ms=float(stats["max_ms"]),
            mean_ms=float(stats["mean_ms"]),
        )


class ThroughputStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    unit: ThroughputMeasurementUnit = ThroughputMeasurementUnit.REQUESTS_PER_SECOND
    requests_per_second: float = Field(ge=0.0)


class BenchmarkErrorSummary(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    success_count: int = Field(ge=0)
    error_count: int = Field(ge=0)
    total_attempts: int = Field(ge=1)
    error_rate: float = Field(ge=0.0, le=1.0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.error_count > self.total_attempts:
            msg = "error_count must not exceed total_attempts"
            raise ValueError(msg)
        if self.success_count > self.total_attempts:
            msg = "success_count must not exceed total_attempts"
            raise ValueError(msg)
        if self.success_count + self.error_count != self.total_attempts:
            msg = "success_count + error_count must equal total_attempts"
            raise ValueError(msg)
        expected_rate = self.error_count / self.total_attempts
        if abs(expected_rate - self.error_rate) > 1e-9:
            msg = "error_rate must equal error_count / total_attempts"
            raise ValueError(msg)
        return self


class ServingEnvironmentMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    contract_version: str = Field(default=SERVING_PERFORMANCE_CONTRACT_VERSION, min_length=1)
    productiq_version: str = Field(min_length=1)
    hostname: str | None = None


class ServingConfigurationMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    api_version: str = Field(min_length=1)
    api_max_top_k: int = Field(ge=1)
    service_name: str = Field(min_length=1)
    artifact_identifiers: dict[str, str] = Field(default_factory=dict)


class ServingStageMeasurement(BaseModel):
    """Optional internal stage timing (when instrumentation exists)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    stage_name: str = Field(min_length=1)
    latency: LatencyStatistics
    notes: str | None = None


class ServingBenchmarkProvenance(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_run_id: str = Field(min_length=1)
    recorded_at_utc: datetime
    runner_name: str | None = None
    runner_version: str | None = None


class ServingBenchmarkRunResult(BaseModel):
    """Machine-readable output for one serving performance benchmark run."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=SERVING_PERFORMANCE_CONTRACT_VERSION, min_length=1)
    configuration: ServingBenchmarkConfiguration
    workload: ServingPerformanceWorkload
    latency: LatencyStatistics | None = None
    throughput: ThroughputStatistics | None = None
    errors: BenchmarkErrorSummary
    environment: ServingEnvironmentMetadata
    serving_configuration: ServingConfigurationMetadata
    provenance: ServingBenchmarkProvenance
    stage_measurements: tuple[ServingStageMeasurement, ...] = ()

    @model_validator(mode="after")
    def validate_latency_presence(self) -> Self:
        if self.errors.success_count > 0 and self.latency is None:
            msg = "latency is required when success_count > 0"
            raise ValueError(msg)
        if self.errors.success_count == 0 and self.latency is not None:
            msg = "latency must be omitted when all measured executions failed"
            raise ValueError(msg)
        return self


class ServingBenchmarkLatencyDelta(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    min_ms: float
    p50_ms: float
    p95_ms: float
    p99_ms: float
    max_ms: float
    mean_ms: float


class ServingBenchmarkRelativeLatencyDelta(BaseModel):
    """Percentage change vs baseline (100 * (comparison - baseline) / baseline)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    p50_pct: float | None = None
    p95_pct: float | None = None
    p99_pct: float | None = None
    mean_pct: float | None = None


class ServingBenchmarkComparison(BaseModel):
    """Absolute and relative latency deltas between two runs (no pass/fail thresholds)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    contract_version: str = Field(default=SERVING_PERFORMANCE_CONTRACT_VERSION, min_length=1)
    baseline_run_id: str = Field(min_length=1)
    comparison_run_id: str = Field(min_length=1)
    endpoint: ServingPerformanceEndpoint
    workload_id: str = Field(min_length=1)
    absolute_latency_delta_ms: ServingBenchmarkLatencyDelta
    relative_latency_delta_pct: ServingBenchmarkRelativeLatencyDelta
    throughput_delta_rps: float | None = None
    limitations: tuple[str, ...] = (
        "Comparison reports measurement deltas only; it does not select a winner.",
        "Absolute latency is not comparable across machines or environments.",
    )


__all__ = [
    "BenchmarkErrorSummary",
    "LatencyMeasurementUnit",
    "LatencyStatistics",
    "ServingBenchmarkComparison",
    "ServingBenchmarkConfiguration",
    "ServingBenchmarkLatencyDelta",
    "ServingBenchmarkProvenance",
    "ServingBenchmarkRelativeLatencyDelta",
    "ServingBenchmarkRunResult",
    "ServingBenchmarkType",
    "ServingConfigurationMetadata",
    "ServingEnvironmentMetadata",
    "ServingPerformanceEndpoint",
    "ServingPerformanceWorkload",
    "ServingStageMeasurement",
    "ThroughputMeasurementUnit",
    "ThroughputStatistics",
]
