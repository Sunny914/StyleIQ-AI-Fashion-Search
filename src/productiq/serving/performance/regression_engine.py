"""Performance baseline comparison and optional regression flags (Phase 13.8.7)."""

from __future__ import annotations

from pathlib import Path

from productiq.exceptions.base import ValidationError
from productiq.serving.performance.baseline_identity import identity_from_run_result
from productiq.serving.performance.baseline_schema import (
    BaselineLookupStatus,
    BenchmarkRunIdentity,
    LatencyMetricComparison,
    PerformanceComparisonReport,
    PerformanceThresholdPolicy,
    ProvenanceCompatibilityResult,
    ProvenanceCompatibilityStatus,
    ReliabilityMetricComparison,
    ServingPerformanceBaselineRecord,
    ThresholdObservation,
    ThroughputMetricComparison,
)
from productiq.serving.performance.baseline_storage import find_baseline_by_identity
from productiq.serving.performance.comparison import (
    compare_serving_benchmark_runs,
    relative_pct_delta,
)
from productiq.serving.performance.concurrency_schema import BenchmarkBoundary
from productiq.serving.performance.provenance_compatibility import assess_provenance_compatibility
from productiq.serving.performance.schema import ServingBenchmarkRunResult


def _latency_comparison(
    baseline: ServingBenchmarkRunResult,
    current: ServingBenchmarkRunResult,
) -> LatencyMetricComparison:
    if baseline.latency is None or current.latency is None:
        msg = "both runs must include latency statistics"
        raise ValidationError(msg)
    base = baseline.latency
    cur = current.latency
    fields = ("min_ms", "mean_ms", "p50_ms", "p95_ms", "p99_ms", "max_ms")
    absolute = {name: float(getattr(cur, name) - getattr(base, name)) for name in fields}
    relative = {name: relative_pct_delta(getattr(base, name), getattr(cur, name)) for name in fields}
    return LatencyMetricComparison(
        baseline=base,
        current=cur,
        absolute_delta_ms=absolute,
        relative_delta_pct=relative,
    )


def _throughput_comparison(
    baseline: ServingBenchmarkRunResult,
    current: ServingBenchmarkRunResult,
) -> ThroughputMetricComparison:
    base_rps = baseline.throughput.requests_per_second if baseline.throughput else None
    cur_rps = current.throughput.requests_per_second if current.throughput else None
    absolute: float | None = None
    relative: float | None = None
    if base_rps is not None and cur_rps is not None:
        absolute = cur_rps - base_rps
        relative = relative_pct_delta(base_rps, cur_rps)
    return ThroughputMetricComparison(
        baseline_rps=base_rps,
        current_rps=cur_rps,
        absolute_delta_rps=absolute,
        relative_delta_pct=relative,
    )


def _reliability_comparison(
    baseline: ServingBenchmarkRunResult,
    current: ServingBenchmarkRunResult,
) -> ReliabilityMetricComparison:
    base = baseline.errors
    cur = current.errors
    return ReliabilityMetricComparison(
        baseline=base,
        current=cur,
        success_count_delta=cur.success_count - base.success_count,
        error_count_delta=cur.error_count - base.error_count,
        error_rate_delta=cur.error_rate - base.error_rate,
    )


def _apply_threshold_policy(
    *,
    policy: PerformanceThresholdPolicy,
    latency: LatencyMetricComparison,
    throughput: ThroughputMetricComparison | None,
    reliability: ReliabilityMetricComparison,
) -> tuple[tuple[ThresholdObservation, ...], tuple[str, ...]]:
    observations: list[ThresholdObservation] = []
    flags: list[str] = []

    if policy.latency_p95_relative_pct_increase is not None:
        rel = latency.relative_delta_pct.get("p95_ms")
        threshold = policy.latency_p95_relative_pct_increase
        breach = rel is not None and rel > threshold
        observations.append(
            ThresholdObservation(
                metric="latency.p95_ms.relative_pct",
                baseline_value=latency.baseline.p95_ms,
                current_value=latency.current.p95_ms,
                absolute_delta=latency.absolute_delta_ms.get("p95_ms"),
                relative_delta_pct=rel,
                threshold=threshold,
                observation="OBSERVATION: p95 relative delta vs baseline",
                regression_flag=breach,
            ),
        )
        if breach:
            flags.append("latency.p95_ms.relative_pct")

    if policy.latency_p95_absolute_ms_increase is not None:
        abs_delta = latency.absolute_delta_ms.get("p95_ms")
        threshold = policy.latency_p95_absolute_ms_increase
        breach = abs_delta is not None and abs_delta > threshold
        observations.append(
            ThresholdObservation(
                metric="latency.p95_ms.absolute_ms",
                baseline_value=latency.baseline.p95_ms,
                current_value=latency.current.p95_ms,
                absolute_delta=abs_delta,
                relative_delta_pct=latency.relative_delta_pct.get("p95_ms"),
                threshold=threshold,
                observation="OBSERVATION: p95 absolute delta vs baseline",
                regression_flag=breach,
            ),
        )
        if breach:
            flags.append("latency.p95_ms.absolute_ms")

    if policy.throughput_relative_pct_decrease is not None and throughput is not None:
        rel = throughput.relative_delta_pct
        threshold = policy.throughput_relative_pct_decrease
        breach = rel is not None and rel < -threshold
        observations.append(
            ThresholdObservation(
                metric="throughput.relative_pct",
                baseline_value=throughput.baseline_rps,
                current_value=throughput.current_rps,
                absolute_delta=throughput.absolute_delta_rps,
                relative_delta_pct=rel,
                threshold=threshold,
                observation="OBSERVATION: throughput relative change vs baseline",
                regression_flag=breach,
            ),
        )
        if breach:
            flags.append("throughput.relative_pct")

    if policy.error_rate_absolute_increase is not None:
        delta = reliability.error_rate_delta
        threshold = policy.error_rate_absolute_increase
        breach = delta > threshold
        observations.append(
            ThresholdObservation(
                metric="errors.error_rate.absolute",
                baseline_value=reliability.baseline.error_rate,
                current_value=reliability.current.error_rate,
                absolute_delta=delta,
                relative_delta_pct=relative_pct_delta(
                    reliability.baseline.error_rate,
                    reliability.current.error_rate,
                ),
                threshold=threshold,
                observation="OBSERVATION: error rate absolute delta vs baseline",
                regression_flag=breach,
            ),
        )
        if breach:
            flags.append("errors.error_rate.absolute")

    return tuple(observations), tuple(flags)


def _parse_boundary(benchmark_boundary: str | None) -> BenchmarkBoundary | None:
    if benchmark_boundary in ("api", "service"):
        return benchmark_boundary  # type: ignore[return-value]
    return None


def compare_to_baseline_record(
    baseline: ServingPerformanceBaselineRecord,
    current: ServingBenchmarkRunResult,
    *,
    benchmark_boundary: str | None = None,
    threshold_policy: PerformanceThresholdPolicy | None = None,
) -> PerformanceComparisonReport:
    explicit = _parse_boundary(benchmark_boundary)
    current_identity = identity_from_run_result(current, benchmark_boundary=explicit)
    compatibility = assess_provenance_compatibility(
        baseline,
        current,
        current_identity=current_identity,
    )
    if not compatibility.compatible:
        return PerformanceComparisonReport(
            identity=current_identity,
            compatibility=compatibility,
            baseline_run_id=baseline.result.provenance.benchmark_run_id,
            current_run_id=current.provenance.benchmark_run_id,
            baseline_pinned_at_utc=baseline.pinned_at_utc,
            current_recorded_at_utc=current.provenance.recorded_at_utc,
            threshold_policy=threshold_policy,
        )

    _ = compare_serving_benchmark_runs(baseline.result, current)
    latency = _latency_comparison(baseline.result, current)
    throughput = _throughput_comparison(baseline.result, current)
    reliability = _reliability_comparison(baseline.result, current)

    observations: tuple[ThresholdObservation, ...] = ()
    regression_flags: tuple[str, ...] = ()
    if threshold_policy is not None:
        observations, regression_flags = _apply_threshold_policy(
            policy=threshold_policy,
            latency=latency,
            throughput=throughput,
            reliability=reliability,
        )

    return PerformanceComparisonReport(
        identity=current_identity,
        compatibility=compatibility,
        baseline_run_id=baseline.result.provenance.benchmark_run_id,
        current_run_id=current.provenance.benchmark_run_id,
        baseline_pinned_at_utc=baseline.pinned_at_utc,
        current_recorded_at_utc=current.provenance.recorded_at_utc,
        latency_comparison=latency,
        throughput_comparison=throughput,
        reliability_comparison=reliability,
        threshold_policy=threshold_policy,
        threshold_observations=observations,
        regression_flags=regression_flags,
    )


def compare_to_stored_baseline(
    current: ServingBenchmarkRunResult,
    *,
    category: str,
    benchmark_boundary: str | None = None,
    threshold_policy: PerformanceThresholdPolicy | None = None,
    baselines_root: Path | None = None,
) -> PerformanceComparisonReport:
    explicit = _parse_boundary(benchmark_boundary)
    identity = identity_from_run_result(current, benchmark_boundary=explicit)
    lookup = find_baseline_by_identity(identity, category=category, root=baselines_root)
    if lookup.status is BaselineLookupStatus.BASELINE_NOT_FOUND or lookup.baseline is None:
        return PerformanceComparisonReport(
            identity=identity,
            compatibility=ProvenanceCompatibilityResult(
                status=ProvenanceCompatibilityStatus.INCOMPATIBLE,
                compatible=False,
                mismatches=("BASELINE_NOT_FOUND",),
            ),
            current_run_id=current.provenance.benchmark_run_id,
            current_recorded_at_utc=current.provenance.recorded_at_utc,
            threshold_policy=threshold_policy,
        )
    return compare_to_baseline_record(
        lookup.baseline,
        current,
        benchmark_boundary=benchmark_boundary,
        threshold_policy=threshold_policy,
    )


def incompatible_report_from_mismatch(
    *,
    identity: BenchmarkRunIdentity,
    current: ServingBenchmarkRunResult,
    mismatches: tuple[str, ...],
) -> PerformanceComparisonReport:
    return PerformanceComparisonReport(
        identity=identity,
        compatibility=ProvenanceCompatibilityResult(
            status=ProvenanceCompatibilityStatus.INCOMPATIBLE,
            compatible=False,
            mismatches=mismatches,
        ),
        current_run_id=current.provenance.benchmark_run_id,
        current_recorded_at_utc=current.provenance.recorded_at_utc,
    )


__all__ = [
    "compare_to_baseline_record",
    "compare_to_stored_baseline",
    "incompatible_report_from_mismatch",
]
