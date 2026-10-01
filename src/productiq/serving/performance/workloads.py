"""Default deterministic serving performance workloads (Phase 13.8.1)."""

from __future__ import annotations

from productiq.serving.performance.schema import (
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.versioning import (
    PLANNED_ROUTE_PRODUCT,
    PLANNED_ROUTE_RECOMMENDATIONS,
    PLANNED_ROUTE_SEARCH,
)

SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION = "1.0.0"

SEARCH_WORKLOAD_MINIMAL = ServingPerformanceWorkload(
    workload_id="serving_search_minimal_v1",
    workload_name="search_minimal",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={"query": "nike running shoes", "top_k": 5},
    description="Minimal valid POST /api/v1/search request for latency benchmarking.",
)

RECOMMENDATION_WORKLOAD_MINIMAL = ServingPerformanceWorkload(
    workload_id="serving_recommendation_minimal_v1",
    workload_name="recommendation_minimal",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={"seed_product_id": "P1", "top_k": 5, "recommendation_type": "similar"},
    description="Minimal valid POST /api/v1/recommendations request for latency benchmarking.",
)

PRODUCT_WORKLOAD_MINIMAL = ServingPerformanceWorkload(
    workload_id="serving_product_minimal_v1",
    workload_name="product_minimal",
    endpoint=ServingPerformanceEndpoint.PRODUCT,
    http_method="GET",
    route_path=PLANNED_ROUTE_PRODUCT,
    path_parameters={"product_id": "P1"},
    description="Minimal valid GET /api/v1/products/{product_id} request for latency benchmarking.",
)

DEFAULT_SERVING_PERFORMANCE_WORKLOADS: tuple[ServingPerformanceWorkload, ...] = (
    SEARCH_WORKLOAD_MINIMAL,
    RECOMMENDATION_WORKLOAD_MINIMAL,
    PRODUCT_WORKLOAD_MINIMAL,
)

WORKLOADS_BY_ID: dict[str, ServingPerformanceWorkload] = {
    workload.workload_id: workload for workload in DEFAULT_SERVING_PERFORMANCE_WORKLOADS
}


def get_serving_performance_workload(workload_id: str) -> ServingPerformanceWorkload:
    try:
        return WORKLOADS_BY_ID[workload_id]
    except KeyError as exc:
        msg = f"unknown serving performance workload_id: {workload_id}"
        raise KeyError(msg) from exc


__all__ = [
    "DEFAULT_SERVING_PERFORMANCE_WORKLOADS",
    "PRODUCT_WORKLOAD_MINIMAL",
    "RECOMMENDATION_WORKLOAD_MINIMAL",
    "SEARCH_WORKLOAD_MINIMAL",
    "SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION",
    "WORKLOADS_BY_ID",
    "get_serving_performance_workload",
]
