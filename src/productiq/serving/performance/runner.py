"""Serving benchmark measurement engine (Phase 13.8.2)."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

from productiq.serving.performance.metadata import (
    build_environment_metadata,
    build_serving_configuration_metadata,
)
from productiq.serving.performance.schema import (
    BenchmarkErrorSummary,
    LatencyStatistics,
    ServingBenchmarkConfiguration,
    ServingBenchmarkProvenance,
    ServingBenchmarkRunResult,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceWorkload,
    ThroughputStatistics,
)
from productiq.serving.performance.timing import MonotonicTimer, PerfCounterTimer, elapsed_ms
from productiq.serving.performance.workloads import get_serving_performance_workload

BENCHMARK_RUNNER_NAME = "productiq.serving.performance.runner"
BENCHMARK_RUNNER_VERSION = "1.0.0"


def _time_execution(execute: Callable[[], None], timer: MonotonicTimer) -> float:
    start = timer.perf_counter()
    execute()
    end = timer.perf_counter()
    return elapsed_ms(start, end)


def _run_single(execute: Callable[[], None], timer: MonotonicTimer) -> tuple[bool, float]:
    try:
        latency_ms = _time_execution(execute, timer)
    except Exception:  # noqa: BLE001 - benchmark boundary counts any failure without leaking details
        return False, 0.0
    return True, latency_ms


def calculate_throughput_rps(successful_requests: int, wall_seconds: float) -> float:
    """Successful requests divided by measured benchmark wall duration."""
    if wall_seconds <= 0:
        return 0.0
    return successful_requests / wall_seconds


def _collect_measured_executions(
    execute: Callable[[], None],
    *,
    iterations: int,
    concurrency: int,
    timer: MonotonicTimer,
) -> tuple[tuple[float, ...], int, int, float]:
    successes: list[float] = []
    errors = 0
    benchmark_start = timer.perf_counter()
    if concurrency <= 1:
        for _ in range(iterations):
            ok, latency_ms = _run_single(execute, timer)
            if ok:
                successes.append(latency_ms)
            else:
                errors += 1
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_run_single, execute, timer) for _ in range(iterations)]
            for future in as_completed(futures):
                ok, latency_ms = future.result()
                if ok:
                    successes.append(latency_ms)
                else:
                    errors += 1
    benchmark_end = timer.perf_counter()
    wall_seconds = max(benchmark_end - benchmark_start, 0.0)
    return tuple(successes), len(successes), errors, wall_seconds


def run_serving_benchmark(
    configuration: ServingBenchmarkConfiguration,
    workload: ServingPerformanceWorkload,
    execute: Callable[[], None],
    *,
    benchmark_run_id: str | None = None,
    timer: MonotonicTimer | None = None,
    environment: ServingEnvironmentMetadata | None = None,
    serving_configuration: ServingConfigurationMetadata | None = None,
) -> ServingBenchmarkRunResult:
    """Execute warmups and measured iterations; build a ``ServingBenchmarkRunResult``."""
    if configuration.workload_id != workload.workload_id:
        msg = "configuration.workload_id must match workload.workload_id"
        raise ValueError(msg)

    monotonic_timer = timer or PerfCounterTimer()
    for _ in range(configuration.warmups):
        _run_single(execute, monotonic_timer)

    latency_samples, success_count, error_count, wall_seconds = _collect_measured_executions(
        execute,
        iterations=configuration.iterations,
        concurrency=configuration.concurrency,
        timer=monotonic_timer,
    )
    total_attempts = configuration.iterations
    if success_count + error_count != total_attempts:
        msg = "measured execution accounting mismatch"
        raise RuntimeError(msg)

    latency_stats = (
        LatencyStatistics.from_samples_ms(latency_samples) if success_count > 0 else None
    )
    throughput = ThroughputStatistics(
        requests_per_second=calculate_throughput_rps(success_count, wall_seconds),
    )
    errors = BenchmarkErrorSummary(
        success_count=success_count,
        error_count=error_count,
        total_attempts=total_attempts,
        error_rate=error_count / total_attempts,
    )
    run_id = benchmark_run_id or str(uuid.uuid4())
    return ServingBenchmarkRunResult(
        configuration=configuration,
        workload=workload,
        latency=latency_stats,
        throughput=throughput,
        errors=errors,
        environment=environment or build_environment_metadata(),
        serving_configuration=serving_configuration or build_serving_configuration_metadata(),
        provenance=ServingBenchmarkProvenance(
            benchmark_run_id=run_id,
            recorded_at_utc=datetime.now(tz=UTC),
            runner_name=BENCHMARK_RUNNER_NAME,
            runner_version=BENCHMARK_RUNNER_VERSION,
        ),
    )


def run_serving_benchmark_for_workload_id(
    configuration: ServingBenchmarkConfiguration,
    execute: Callable[[], None],
    *,
    benchmark_run_id: str | None = None,
    timer: MonotonicTimer | None = None,
) -> ServingBenchmarkRunResult:
    workload = get_serving_performance_workload(configuration.workload_id)
    return run_serving_benchmark(
        configuration,
        workload,
        execute,
        benchmark_run_id=benchmark_run_id,
        timer=timer,
    )


__all__ = [
    "BENCHMARK_RUNNER_NAME",
    "BENCHMARK_RUNNER_VERSION",
    "calculate_throughput_rps",
    "run_serving_benchmark",
    "run_serving_benchmark_for_workload_id",
]
