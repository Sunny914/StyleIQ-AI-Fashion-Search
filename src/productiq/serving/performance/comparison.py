"""Compare serving performance benchmark runs (Phase 13.8.1)."""

from __future__ import annotations

from productiq.exceptions.base import ValidationError
from productiq.serving.performance.schema import (
    ServingBenchmarkComparison,
    ServingBenchmarkLatencyDelta,
    ServingBenchmarkRelativeLatencyDelta,
    ServingBenchmarkRunResult,
)


def relative_pct_delta(baseline: float, comparison: float) -> float | None:
    """Percentage change vs baseline (100 * (comparison - baseline) / baseline)."""
    if baseline == 0.0:
        return None
    return 100.0 * (comparison - baseline) / baseline


def _relative_pct(baseline: float, comparison: float) -> float | None:
    return relative_pct_delta(baseline, comparison)


def compare_serving_benchmark_runs(
    baseline: ServingBenchmarkRunResult,
    comparison: ServingBenchmarkRunResult,
) -> ServingBenchmarkComparison:
    if baseline.configuration.endpoint != comparison.configuration.endpoint:
        msg = "endpoint must match for serving benchmark comparison"
        raise ValidationError(msg)
    if baseline.configuration.workload_id != comparison.configuration.workload_id:
        msg = "workload_id must match for serving benchmark comparison"
        raise ValidationError(msg)
    if baseline.workload.workload_id != comparison.workload.workload_id:
        msg = "workload identity must match for serving benchmark comparison"
        raise ValidationError(msg)

    if baseline.latency is None or comparison.latency is None:
        msg = "both runs must include latency statistics for comparison"
        raise ValidationError(msg)

    base_latency = baseline.latency
    comp_latency = comparison.latency
    absolute = ServingBenchmarkLatencyDelta(
        min_ms=comp_latency.min_ms - base_latency.min_ms,
        p50_ms=comp_latency.p50_ms - base_latency.p50_ms,
        p95_ms=comp_latency.p95_ms - base_latency.p95_ms,
        p99_ms=comp_latency.p99_ms - base_latency.p99_ms,
        max_ms=comp_latency.max_ms - base_latency.max_ms,
        mean_ms=comp_latency.mean_ms - base_latency.mean_ms,
    )
    relative = ServingBenchmarkRelativeLatencyDelta(
        p50_pct=_relative_pct(base_latency.p50_ms, comp_latency.p50_ms),
        p95_pct=_relative_pct(base_latency.p95_ms, comp_latency.p95_ms),
        p99_pct=_relative_pct(base_latency.p99_ms, comp_latency.p99_ms),
        mean_pct=_relative_pct(base_latency.mean_ms, comp_latency.mean_ms),
    )
    throughput_delta: float | None = None
    if baseline.throughput is not None and comparison.throughput is not None:
        throughput_delta = (
            comparison.throughput.requests_per_second - baseline.throughput.requests_per_second
        )

    return ServingBenchmarkComparison(
        baseline_run_id=baseline.provenance.benchmark_run_id,
        comparison_run_id=comparison.provenance.benchmark_run_id,
        endpoint=baseline.configuration.endpoint,
        workload_id=baseline.configuration.workload_id,
        absolute_latency_delta_ms=absolute,
        relative_latency_delta_pct=relative,
        throughput_delta_rps=throughput_delta,
    )


__all__ = ["compare_serving_benchmark_runs", "relative_pct_delta"]
