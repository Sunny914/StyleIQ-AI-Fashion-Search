"""Canonical search serving performance workloads (Phase 13.8.3).

Distinct from Phase 12 search *relevance* evaluation benchmarks.
Small, stable workload set for latency measurement only.
"""

from __future__ import annotations

from productiq.serving.performance.schema import (
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH

SEARCH_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION = "1.0.0"

SEARCH_SERVING_LEXICAL_V1 = ServingPerformanceWorkload(
    workload_id="search_serving_lexical_v1",
    workload_name="simple_lexical",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={"query": "cotton shirt", "top_k": 10},
    description="Short lexical product-type query.",
)

SEARCH_SERVING_BRAND_V1 = ServingPerformanceWorkload(
    workload_id="search_serving_brand_v1",
    workload_name="brand_query",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={"query": "Nike", "top_k": 10},
    description="Brand-focused query.",
)

SEARCH_SERVING_ATTRIBUTE_V1 = ServingPerformanceWorkload(
    workload_id="search_serving_attribute_v1",
    workload_name="attribute_heavy",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={"query": "men blue slim fit denim jeans", "top_k": 10},
    description="Multi-attribute natural-language query.",
)

SEARCH_SERVING_NATURAL_V1 = ServingPerformanceWorkload(
    workload_id="search_serving_natural_v1",
    workload_name="natural_language",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={"query": "comfortable running shoes for daily wear", "top_k": 10},
    description="Longer natural-language discovery query.",
)

SEARCH_SERVING_FILTER_V1 = ServingPerformanceWorkload(
    workload_id="search_serving_filter_v1",
    workload_name="structured_filters",
    endpoint=ServingPerformanceEndpoint.SEARCH,
    http_method="POST",
    route_path=PLANNED_ROUTE_SEARCH,
    request_body={
        "query": "running shoes",
        "top_k": 10,
        "filters": {"brand": "nike", "category_gender": "Men"},
    },
    description="Query with structured hard-filter constraints.",
)

SEARCH_SERVING_PERFORMANCE_WORKLOADS: tuple[ServingPerformanceWorkload, ...] = (
    SEARCH_SERVING_LEXICAL_V1,
    SEARCH_SERVING_BRAND_V1,
    SEARCH_SERVING_ATTRIBUTE_V1,
    SEARCH_SERVING_NATURAL_V1,
    SEARCH_SERVING_FILTER_V1,
)

SEARCH_SERVING_WORKLOADS_BY_ID: dict[str, ServingPerformanceWorkload] = {
    workload.workload_id: workload for workload in SEARCH_SERVING_PERFORMANCE_WORKLOADS
}


def get_search_serving_performance_workload(workload_id: str) -> ServingPerformanceWorkload:
    try:
        return SEARCH_SERVING_WORKLOADS_BY_ID[workload_id]
    except KeyError as exc:
        msg = f"unknown search serving performance workload_id: {workload_id}"
        raise KeyError(msg) from exc


__all__ = [
    "SEARCH_SERVING_ATTRIBUTE_V1",
    "SEARCH_SERVING_BRAND_V1",
    "SEARCH_SERVING_FILTER_V1",
    "SEARCH_SERVING_LEXICAL_V1",
    "SEARCH_SERVING_NATURAL_V1",
    "SEARCH_SERVING_PERFORMANCE_WORKLOADS",
    "SEARCH_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION",
    "SEARCH_SERVING_WORKLOADS_BY_ID",
    "get_search_serving_performance_workload",
]
