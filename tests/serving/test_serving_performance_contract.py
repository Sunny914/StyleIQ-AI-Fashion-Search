"""Tests for Phase 13.8.1 serving performance benchmark contracts."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import ValidationError as ProductIQValidationError
from productiq.serving.performance import (
    SERVING_PERFORMANCE_CONTRACT_VERSION,
    LatencyStatistics,
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingBenchmarkType,
    ServingPerformanceEndpoint,
    compare_serving_benchmark_runs,
    compute_latency_statistics_ms,
    get_serving_performance_workload,
)
from productiq.serving.performance.schema import (
    BenchmarkErrorSummary,
    ServingBenchmarkProvenance,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ThroughputStatistics,
)
from productiq.serving.performance.workloads import (
    DEFAULT_SERVING_PERFORMANCE_WORKLOADS,
    SEARCH_WORKLOAD_MINIMAL,
)


def test_valid_benchmark_configuration() -> None:
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.API,
        endpoint=ServingPerformanceEndpoint.SEARCH,
        workload_id=SEARCH_WORKLOAD_MINIMAL.workload_id,
        iterations=50,
        warmups=5,
        concurrency=1,
    )
    assert config.contract_version == SERVING_PERFORMANCE_CONTRACT_VERSION


@pytest.mark.parametrize("iterations", [0, -1])
def test_invalid_iterations_rejected(iterations: int) -> None:
    with pytest.raises(ValidationError):
        ServingBenchmarkConfiguration(
            benchmark_type=ServingBenchmarkType.API,
            endpoint=ServingPerformanceEndpoint.SEARCH,
            workload_id="serving_search_minimal_v1",
            iterations=iterations,
            warmups=0,
            concurrency=1,
        )


@pytest.mark.parametrize("warmups", [-1])
def test_invalid_warmups_rejected(warmups: int) -> None:
    with pytest.raises(ValidationError):
        ServingBenchmarkConfiguration(
            benchmark_type=ServingBenchmarkType.CONCURRENCY,
            endpoint=ServingPerformanceEndpoint.SEARCH,
            workload_id="serving_search_minimal_v1",
            iterations=1,
            warmups=warmups,
            concurrency=2,
        )


@pytest.mark.parametrize("concurrency", [0, -3])
def test_invalid_concurrency_rejected(concurrency: int) -> None:
    with pytest.raises(ValidationError):
        ServingBenchmarkConfiguration(
            benchmark_type=ServingBenchmarkType.CONCURRENCY,
            endpoint=ServingPerformanceEndpoint.SEARCH,
            workload_id="serving_search_minimal_v1",
            iterations=1,
            warmups=0,
            concurrency=concurrency,
        )


def test_latency_statistics_from_samples() -> None:
    stats = LatencyStatistics.from_samples_ms((10.0, 20.0, 30.0, 40.0, 100.0))
    assert stats.min_ms == 10.0
    assert stats.max_ms == 100.0
    assert stats.p50_ms == 30.0
    assert stats.sample_count == 5


def test_latency_statistics_rejects_non_monotonic_manual_payload() -> None:
    with pytest.raises(ValidationError):
        LatencyStatistics(
            sample_count=3,
            min_ms=10.0,
            p50_ms=5.0,
            p95_ms=20.0,
            p99_ms=25.0,
            max_ms=30.0,
            mean_ms=15.0,
        )


def test_compute_latency_statistics_empty_rejected() -> None:
    with pytest.raises(ValueError, match="empty"):
        compute_latency_statistics_ms(())


def test_default_workloads_are_unique_and_valid() -> None:
    ids = [workload.workload_id for workload in DEFAULT_SERVING_PERFORMANCE_WORKLOADS]
    assert len(ids) == len(set(ids))
    for workload_id in ids:
        loaded = get_serving_performance_workload(workload_id)
        assert loaded.workload_id == workload_id


def _sample_run(*, run_id: str, p50: float) -> ServingBenchmarkRunResult:
    workload = SEARCH_WORKLOAD_MINIMAL
    config = ServingBenchmarkConfiguration(
        benchmark_type=ServingBenchmarkType.SERVICE,
        endpoint=ServingPerformanceEndpoint.SEARCH,
        workload_id=workload.workload_id,
        iterations=10,
        warmups=2,
        concurrency=1,
    )
    samples = tuple(p50 + offset for offset in (0.0, 1.0, 2.0, 3.0, 4.0))
    return ServingBenchmarkRunResult(
        configuration=config,
        workload=workload,
        latency=LatencyStatistics.from_samples_ms(samples),
        throughput=ThroughputStatistics(requests_per_second=100.0),
        errors=BenchmarkErrorSummary(
            success_count=10,
            error_count=0,
            total_attempts=10,
            error_rate=0.0,
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
        ),
        provenance=ServingBenchmarkProvenance(
            benchmark_run_id=run_id,
            recorded_at_utc=datetime(2026, 1, 1, tzinfo=UTC),
            runner_name="pytest",
        ),
    )


def test_result_round_trip_json() -> None:
    run = _sample_run(run_id="run-a", p50=12.0)
    payload = json.loads(run.model_dump_json())
    restored = ServingBenchmarkRunResult.model_validate(payload)
    assert restored.provenance.benchmark_run_id == "run-a"
    assert restored.latency.p50_ms == restored.latency.p50_ms


def test_malformed_result_rejected() -> None:
    with pytest.raises(ValidationError):
        ServingBenchmarkRunResult.model_validate({"configuration": {"bad": True}})


def test_compare_runs_absolute_and_relative_delta() -> None:
    baseline = _sample_run(run_id="baseline", p50=10.0)
    comparison = _sample_run(run_id="comparison", p50=20.0)
    delta = compare_serving_benchmark_runs(baseline, comparison)
    assert (
        delta.absolute_latency_delta_ms.p50_ms
        == comparison.latency.p50_ms - baseline.latency.p50_ms
    )
    assert delta.relative_latency_delta_pct.p50_pct == pytest.approx(
        100.0
        * (comparison.latency.p50_ms - baseline.latency.p50_ms)
        / baseline.latency.p50_ms,
    )
    assert delta.throughput_delta_rps == 0.0


def test_compare_rejects_mismatched_workload() -> None:
    baseline = _sample_run(run_id="baseline", p50=10.0)
    comparison = _sample_run(run_id="comparison", p50=11.0)
    comparison = comparison.model_copy(
        update={
            "configuration": comparison.configuration.model_copy(
                update={"workload_id": "other"},
            ),
        },
    )
    with pytest.raises(ProductIQValidationError, match="workload_id"):
        compare_serving_benchmark_runs(baseline, comparison)


def test_contract_version_constant() -> None:
    assert SERVING_PERFORMANCE_CONTRACT_VERSION.startswith("1.")
