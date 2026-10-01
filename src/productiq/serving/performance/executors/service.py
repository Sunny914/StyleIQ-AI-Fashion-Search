"""Service-level benchmark executors (Phase 13.8.2)."""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from productiq.serving.performance.runner import run_serving_benchmark
from productiq.serving.performance.schema import (
    ServingBenchmarkConfiguration,
    ServingBenchmarkRunResult,
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.performance.timing import MonotonicTimer
from productiq.serving.performance.workloads import get_serving_performance_workload
from productiq.serving.recommendation_schema import RecommendationApiRequest
from productiq.serving.search_schema import SearchApiRequest

if TYPE_CHECKING:
    from productiq.serving.protocols import (
        ProductServingService,
        RecommendationServingService,
        SearchServingService,
    )

_BENCHMARK_REQUEST_ID = "serving-benchmark"


class ServiceBenchmarkExecutionError(Exception):
    """Internal signal for service-level benchmark failures."""


def build_service_execute_callable(
    workload: ServingPerformanceWorkload,
    *,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
) -> Callable[[], None]:
    def _execute() -> None:
        if workload.endpoint is ServingPerformanceEndpoint.SEARCH:
            if search_service is None:
                raise ServiceBenchmarkExecutionError("search_service_missing")
            body = workload.request_body or {}
            search_request = SearchApiRequest.model_validate(body)
            search_service.search(search_request, request_id=_BENCHMARK_REQUEST_ID)
            return
        if workload.endpoint is ServingPerformanceEndpoint.RECOMMENDATION:
            if recommendation_service is None:
                raise ServiceBenchmarkExecutionError("recommendation_service_missing")
            body = workload.request_body or {}
            recommendation_request = RecommendationApiRequest.model_validate(body)
            recommendation_service.recommend(
                recommendation_request,
                request_id=_BENCHMARK_REQUEST_ID,
            )
            return
        if workload.endpoint is ServingPerformanceEndpoint.PRODUCT:
            if product_service is None:
                raise ServiceBenchmarkExecutionError("product_service_missing")
            product_id = workload.path_parameters.get("product_id")
            if not product_id:
                raise ServiceBenchmarkExecutionError("product_id_missing")
            product_service.get_product(product_id, request_id=_BENCHMARK_REQUEST_ID)
            return
        raise ServiceBenchmarkExecutionError("unsupported_endpoint")

    return _execute


def run_service_benchmark(
    configuration: ServingBenchmarkConfiguration,
    *,
    workload: ServingPerformanceWorkload | None = None,
    search_service: SearchServingService | None = None,
    recommendation_service: RecommendationServingService | None = None,
    product_service: ProductServingService | None = None,
    benchmark_run_id: str | None = None,
    timer: MonotonicTimer | None = None,
    environment: ServingEnvironmentMetadata | None = None,
    serving_configuration: ServingConfigurationMetadata | None = None,
) -> ServingBenchmarkRunResult:
    resolved_workload = workload or get_serving_performance_workload(configuration.workload_id)
    execute = build_service_execute_callable(
        resolved_workload,
        search_service=search_service,
        recommendation_service=recommendation_service,
        product_service=product_service,
    )
    return run_serving_benchmark(
        configuration,
        resolved_workload,
        execute,
        benchmark_run_id=benchmark_run_id,
        timer=timer,
        environment=environment,
        serving_configuration=serving_configuration,
    )


__all__ = [
    "ServiceBenchmarkExecutionError",
    "build_service_execute_callable",
    "run_service_benchmark",
]
