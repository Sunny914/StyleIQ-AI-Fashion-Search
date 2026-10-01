"""HTTP/API benchmark executors (Phase 13.8.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from fastapi.testclient import TestClient

from productiq.serving.performance.runner import run_serving_benchmark
from productiq.serving.performance.schema import (
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceWorkload,
)
from productiq.serving.performance.timing import MonotonicTimer
from productiq.serving.performance.workloads import get_serving_performance_workload

if TYPE_CHECKING:
    from fastapi import FastAPI


class ApiBenchmarkExecutionError(Exception):
    """Internal signal for non-success HTTP responses (not exported in artifacts)."""


def resolve_workload_path(workload: ServingPerformanceWorkload) -> str:
    if workload.path_parameters:
        return workload.route_path.format(**workload.path_parameters)
    return workload.route_path


def build_api_execute_callable(
    client: TestClient,
    workload: ServingPerformanceWorkload,
) -> Callable[[], None]:
    path = resolve_workload_path(workload)

    def _execute() -> None:
        if workload.http_method == "POST":
            response = client.post(path, json=workload.request_body)
        else:
            response = client.get(path)
        if response.status_code >= 400:
            raise ApiBenchmarkExecutionError("http_error")

    return _execute


def run_api_benchmark(
    client: TestClient,
    configuration: ServingBenchmarkConfiguration,
    *,
    workload: ServingPerformanceWorkload | None = None,
    benchmark_run_id: str | None = None,
    timer: MonotonicTimer | None = None,
    environment: ServingEnvironmentMetadata | None = None,
    serving_configuration: ServingConfigurationMetadata | None = None,
) -> ServingBenchmarkRunResult:
    resolved_workload = workload or get_serving_performance_workload(configuration.workload_id)
    execute = build_api_execute_callable(client, resolved_workload)
    return run_serving_benchmark(
        configuration,
        resolved_workload,
        execute,
        benchmark_run_id=benchmark_run_id,
        timer=timer,
        environment=environment,
        serving_configuration=serving_configuration,
    )


def run_api_benchmark_app(
    app: FastAPI,
    configuration: ServingBenchmarkConfiguration,
    *,
    workload: ServingPerformanceWorkload | None = None,
    benchmark_run_id: str | None = None,
    timer: MonotonicTimer | None = None,
) -> ServingBenchmarkRunResult:
    with TestClient(app) as client:
        return run_api_benchmark(
            client,
            configuration,
            workload=workload,
            benchmark_run_id=benchmark_run_id,
            timer=timer,
        )


__all__ = [
    "ApiBenchmarkExecutionError",
    "build_api_execute_callable",
    "resolve_workload_path",
    "run_api_benchmark",
    "run_api_benchmark_app",
]
