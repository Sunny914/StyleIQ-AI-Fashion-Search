"""Tests for Phase 13.8.7 performance baseline and regression framework."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from productiq.exceptions.base import ValidationError as ProductIQValidationError
from productiq.serving.performance.baseline_identity import (
    identities_match,
    identity_from_run_result,
)
from productiq.serving.performance.baseline_schema import (
    PerformanceThresholdPolicy,
    ServingPerformanceBaselineRecord,
)
from productiq.serving.performance.baseline_storage import (
    find_baseline_by_identity,
    pin_baseline_record,
    pin_run_result_as_baseline,
)
from productiq.serving.performance.comparison import relative_pct_delta
from productiq.serving.performance.contract_version import SERVING_PERFORMANCE_CONTRACT_VERSION
from productiq.serving.performance.provenance_compatibility import assess_provenance_compatibility
from productiq.serving.performance.regression_engine import (
    compare_to_baseline_record,
    compare_to_stored_baseline,
)
from productiq.serving.performance.regression_report import (
    render_performance_comparison_report_markdown,
)
from productiq.serving.performance.runner import BENCHMARK_RUNNER_VERSION
from productiq.serving.performance.schema import (
    BenchmarkErrorSummary,
    LatencyStatistics,
    ServingBenchmarkConfiguration,
    ServingBenchmarkProvenance,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceEndpoint,
    ThroughputStatistics,
)
from productiq.serving.performance.workloads import SEARCH_WORKLOAD_MINIMAL


def _latency_from_p50(p50: float) -> LatencyStatistics:
    samples = tuple(p50 + offset for offset in (0.0, 1.0, 2.0, 3.0, 4.0))
    return LatencyStatistics.from_samples_ms(samples)


def _sample_run(
    *,
    run_id: str,
    p50: float,
    benchmark_type: ServingBenchmarkType = ServingBenchmarkType.SERVICE,
    workload_id: str = SEARCH_WORKLOAD_MINIMAL.workload_id,
    rps: float = 100.0,
    error_rate: float = 0.0,
    artifact_ids: dict[str, str] | None = None,
) -> ServingBenchmarkRunResult:
    workload = SEARCH_WORKLOAD_MINIMAL
    if workload_id != workload.workload_id:
        workload = workload.model_copy(update={"workload_id": workload_id})
    config = ServingBenchmarkConfiguration(
        benchmark_type=benchmark_type,
        endpoint=ServingPerformanceEndpoint.SEARCH,
        workload_id=workload_id,
        iterations=10,
        warmups=2,
        concurrency=1,
    )
    return ServingBenchmarkRunResult(
        configuration=config,
        workload=workload,
        latency=_latency_from_p50(p50),
        throughput=ThroughputStatistics(requests_per_second=rps),
        errors=BenchmarkErrorSummary(
            success_count=10,
            error_count=int(error_rate * 10),
            total_attempts=10,
            error_rate=error_rate,
        ),
        environment=ServingEnvironmentMetadata(
            python_version="3.13.0",
            platform="test",
            productiq_version="0.1.0",
        ),
        serving_configuration=ServingConfigurationMetadata(
            api_version="v1",
            api_max_top_k=100,
            service_name="productiq",
            artifact_identifiers=artifact_ids or {},
        ),
        provenance=ServingBenchmarkProvenance(
            benchmark_run_id=run_id,
            recorded_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
            runner_name="pytest",
            runner_version=BENCHMARK_RUNNER_VERSION,
        ),
    )


def _baseline_record(
    *,
    run: ServingBenchmarkRunResult,
    baseline_id: str = "baseline-a",
) -> ServingPerformanceBaselineRecord:
    return ServingPerformanceBaselineRecord(
        baseline_id=baseline_id,
        identity=identity_from_run_result(run),
        environment=run.environment,
        serving_configuration=run.serving_configuration,
        result=run,
        pinned_at_utc=datetime(2026, 2, 1, tzinfo=UTC),
    )


def test_baseline_identity_storage_key_is_deterministic() -> None:
    identity = identity_from_run_result(_sample_run(run_id="r1", p50=10.0))
    assert identity.storage_key() == "search_service_serving_search_minimal_v1_w2_i10_c1"


def test_identities_match_detects_workload_mismatch() -> None:
    base = identity_from_run_result(_sample_run(run_id="a", p50=1.0))
    other = identity_from_run_result(
        _sample_run(run_id="b", p50=1.0, workload_id="other_workload"),
    )
    ok, mismatches = identities_match(base, other)
    assert not ok
    assert any("workload_id" in item for item in mismatches)


def test_identities_match_detects_boundary_mismatch() -> None:
    service = identity_from_run_result(_sample_run(run_id="a", p50=1.0))
    api = identity_from_run_result(
        _sample_run(run_id="b", p50=1.0, benchmark_type=ServingBenchmarkType.API),
    )
    ok, mismatches = identities_match(service, api)
    assert not ok
    assert any("benchmark_boundary" in item for item in mismatches)


def test_provenance_compatibility_rejects_runner_version_mismatch() -> None:
    baseline_run = _sample_run(run_id="base", p50=10.0)
    current_run = baseline_run.model_copy(
        update={
            "provenance": baseline_run.provenance.model_copy(
                update={"runner_version": "other-runner"},
            ),
        },
    )
    record = _baseline_record(run=baseline_run)
    result = assess_provenance_compatibility(
        record,
        current_run,
        current_identity=identity_from_run_result(current_run),
    )
    assert not result.compatible


def test_provenance_compatibility_rejects_artifact_identifier_mismatch() -> None:
    baseline_run = _sample_run(run_id="base", p50=10.0, artifact_ids={"catalog": "a"})
    current_run = _sample_run(run_id="cur", p50=10.0, artifact_ids={"catalog": "b"})
    record = _baseline_record(run=baseline_run)
    result = assess_provenance_compatibility(
        record,
        current_run,
        current_identity=identity_from_run_result(current_run),
    )
    assert not result.compatible


def test_baseline_record_json_round_trip() -> None:
    record = _baseline_record(run=_sample_run(run_id="base", p50=12.0))
    restored = ServingPerformanceBaselineRecord.model_validate_json(record.model_dump_json())
    assert restored.identity == record.identity


def test_pin_baseline_refuses_silent_overwrite(tmp_path: Path) -> None:
    record = _baseline_record(run=_sample_run(run_id="base", p50=10.0))
    pin_baseline_record(record, category="search", root=tmp_path)
    with pytest.raises(ProductIQValidationError, match="already exists"):
        pin_baseline_record(record, category="search", root=tmp_path)


def test_find_baseline_by_identity(tmp_path: Path) -> None:
    run = _sample_run(run_id="base", p50=10.0)
    record = pin_run_result_as_baseline(run, category="search", root=tmp_path)
    lookup = find_baseline_by_identity(record.identity, category="search", root=tmp_path)
    assert lookup.baseline is not None


def test_missing_baseline_lookup(tmp_path: Path) -> None:
    identity = identity_from_run_result(_sample_run(run_id="cur", p50=10.0))
    lookup = find_baseline_by_identity(identity, category="search", root=tmp_path)
    assert lookup.baseline is None


def test_compare_compatible_runs_produces_latency_deltas() -> None:
    baseline_run = _sample_run(run_id="base", p50=10.0)
    current_run = _sample_run(run_id="cur", p50=20.0)
    report = compare_to_baseline_record(_baseline_record(run=baseline_run), current_run)
    assert report.compatibility.compatible
    assert report.latency_comparison is not None
    assert report.latency_comparison.absolute_delta_ms["mean_ms"] == pytest.approx(10.0)
    base_mean = baseline_run.latency.mean_ms  # type: ignore[union-attr]
    expected_rel = 100.0 * 10.0 / base_mean
    assert report.latency_comparison.relative_delta_pct["mean_ms"] == pytest.approx(expected_rel)


def test_relative_pct_delta_zero_baseline_returns_none() -> None:
    assert relative_pct_delta(0.0, 5.0) is None


def test_compare_incompatible_boundary() -> None:
    baseline_run = _sample_run(run_id="base", p50=10.0)
    current_run = _sample_run(run_id="cur", p50=11.0, benchmark_type=ServingBenchmarkType.API)
    report = compare_to_baseline_record(_baseline_record(run=baseline_run), current_run)
    assert not report.compatibility.compatible


def test_threshold_policy_regression_flag() -> None:
    policy = PerformanceThresholdPolicy(latency_p95_relative_pct_increase=5.0)
    report = compare_to_baseline_record(
        _baseline_record(run=_sample_run(run_id="base", p50=10.0)),
        _sample_run(run_id="cur", p50=25.0),
        threshold_policy=policy,
    )
    assert report.regression_flags


def test_descriptive_comparison_without_thresholds() -> None:
    report = compare_to_baseline_record(
        _baseline_record(run=_sample_run(run_id="base", p50=10.0)),
        _sample_run(run_id="cur", p50=50.0),
    )
    assert report.regression_flags == ()


def test_compare_to_stored_baseline_not_found(tmp_path: Path) -> None:
    report = compare_to_stored_baseline(
        _sample_run(run_id="cur", p50=10.0),
        category="search",
        baselines_root=tmp_path,
    )
    assert "BASELINE_NOT_FOUND" in report.compatibility.mismatches


def test_deterministic_report_generation() -> None:
    baseline = _baseline_record(run=_sample_run(run_id="base", p50=10.0))
    current = _sample_run(run_id="cur", p50=12.0)
    report_a = compare_to_baseline_record(baseline, current)
    report_b = compare_to_baseline_record(baseline, current)
    assert report_a.model_dump_json() == report_b.model_dump_json()
    assert render_performance_comparison_report_markdown(report_a) == (
        render_performance_comparison_report_markdown(report_b)
    )


def test_report_json_round_trip() -> None:
    report = compare_to_baseline_record(
        _baseline_record(run=_sample_run(run_id="base", p50=10.0)),
        _sample_run(run_id="cur", p50=11.0),
    )
    restored = type(report).model_validate(json.loads(report.model_dump_json()))
    assert restored.model_dump_json() == report.model_dump_json()


def test_performance_contract_version_mismatch() -> None:
    baseline_run = _sample_run(run_id="base", p50=10.0)
    current_run = baseline_run.model_copy(update={"contract_version": "9.9.9"})
    compat = assess_provenance_compatibility(
        _baseline_record(run=baseline_run),
        current_run,
        current_identity=identity_from_run_result(current_run),
    )
    assert not compat.compatible
    assert baseline_run.contract_version == SERVING_PERFORMANCE_CONTRACT_VERSION
