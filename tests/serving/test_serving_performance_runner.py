"""Tests for Phase 13.8.2 serving benchmark harness."""

from __future__ import annotations

import json
from threading import Lock

import pytest

from productiq.api.app import create_app
from productiq.serving.performance import (
    ServingBenchmarkConfiguration,
    ServingBenchmarkType,
    ServingPerformanceEndpoint,
    run_api_benchmark_app,
    run_service_benchmark,
    run_serving_benchmark,
)
from productiq.serving.performance.runner import calculate_throughput_rps
from productiq.serving.performance.schema import BenchmarkErrorSummary
from productiq.serving.performance.statistics import compute_latency_statistics_ms
from productiq.serving.performance.timing import ScriptedTimer
from productiq.serving.performance.workloads import SEARCH_WORKLOAD_MINIMAL
from tests.api.fakes import RecordingSearchService


def _config(**overrides: object) -> ServingBenchmarkConfiguration:
    base = {
        "benchmark_type": ServingBenchmarkType.SERVICE,
        "endpoint": ServingPerformanceEndpoint.SEARCH,
        "workload_id": SEARCH_WORKLOAD_MINIMAL.workload_id,
        "iterations": 3,
        "warmups": 2,
        "concurrency": 1,
    }
    base.update(overrides)
    return ServingBenchmarkConfiguration(**base)


def test_runner_executes_warmups_and_iterations() -> None:
    calls = {"count": 0}

    def execute() -> None:
        calls["count"] += 1

    timer = ScriptedTimer((0.001,) * 100)
    result = run_serving_benchmark(
        _config(warmups=2, iterations=3),
        SEARCH_WORKLOAD_MINIMAL,
        execute,
        timer=timer,
        benchmark_run_id="run-accounting",
    )
    assert calls["count"] == 5
    assert result.errors.total_attempts == 3
    assert result.errors.success_count == 3
    assert result.errors.error_count == 0
    assert result.latency is not None
    assert result.latency.sample_count == 3


def test_runner_mixed_success_and_error_excludes_failures_from_latency() -> None:
    calls = {"count": 0}

    def execute() -> None:
        calls["count"] += 1
        if calls["count"] % 2 == 0:
            raise RuntimeError("boom")

    timer = ScriptedTimer((0.002,) * 50)
    result = run_serving_benchmark(
        _config(warmups=0, iterations=4),
        SEARCH_WORKLOAD_MINIMAL,
        execute,
        timer=timer,
    )
    assert result.errors.success_count == 2
    assert result.errors.error_count == 2
    assert result.latency is not None
    assert result.latency.sample_count == 2


def test_runner_all_errors_omit_latency() -> None:
    def execute() -> None:
        raise RuntimeError("always")

    timer = ScriptedTimer((0.001,) * 20)
    result = run_serving_benchmark(
        _config(warmups=0, iterations=2),
        SEARCH_WORKLOAD_MINIMAL,
        execute,
        timer=timer,
    )
    assert result.errors.success_count == 0
    assert result.latency is None
    assert result.throughput is not None
    assert result.throughput.requests_per_second == 0.0


def test_throughput_uses_success_count_over_wall_seconds() -> None:
    assert calculate_throughput_rps(10, 2.0) == 5.0
    assert calculate_throughput_rps(0, 1.0) == 0.0
    assert calculate_throughput_rps(3, 0.0) == 0.0


def test_concurrency_accounting() -> None:
    lock = Lock()
    calls = {"count": 0}

    def execute() -> None:
        with lock:
            calls["count"] += 1

    result = run_serving_benchmark(
        _config(warmups=0, iterations=8, concurrency=4),
        SEARCH_WORKLOAD_MINIMAL,
        execute,
    )
    assert calls["count"] == 8
    assert result.errors.success_count == 8
    assert result.errors.error_count == 0


def test_api_executor_with_fake_app() -> None:
    app = create_app(search_service=RecordingSearchService())
    config = _config(benchmark_type=ServingBenchmarkType.API)
    timer = ScriptedTimer((0.001,) * 40)
    result = run_api_benchmark_app(app, config, timer=timer, benchmark_run_id="api-run")
    assert result.errors.success_count == config.iterations
    assert result.provenance.runner_name is not None
    payload = json.loads(result.model_dump_json())
    assert payload["provenance"]["benchmark_run_id"] == "api-run"


def test_service_executor_with_fake_service() -> None:
    config = _config(benchmark_type=ServingBenchmarkType.SERVICE)
    timer = ScriptedTimer((0.001,) * 40)
    result = run_service_benchmark(
        config,
        search_service=RecordingSearchService(),
        timer=timer,
    )
    assert result.errors.success_count == config.iterations
    assert result.latency is not None


def test_statistics_reject_nan() -> None:
    with pytest.raises(ValueError, match="finite"):
        compute_latency_statistics_ms((1.0, float("nan")))


def test_error_summary_requires_success_plus_error_equals_total() -> None:
    with pytest.raises(ValueError, match="success_count \\+ error_count"):
        BenchmarkErrorSummary(
            success_count=1,
            error_count=1,
            total_attempts=3,
            error_rate=1 / 3,
        )
