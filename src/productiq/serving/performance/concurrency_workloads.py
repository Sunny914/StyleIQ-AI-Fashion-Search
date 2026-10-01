"""Concurrency experiment workloads — reuse existing serving performance catalogs (Phase 13.8.6)."""

from __future__ import annotations

from productiq.serving.performance.product_workloads import PRODUCT_SERVING_EXISTING_V1
from productiq.serving.performance.recommendation_workloads import (
    RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
)
from productiq.serving.performance.schema import (
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.performance.search_workloads import SEARCH_SERVING_LEXICAL_V1

CONCURRENCY_EXPERIMENT_WORKLOAD_BY_ENDPOINT: dict[ServingPerformanceEndpoint, ServingPerformanceWorkload] = {
    ServingPerformanceEndpoint.SEARCH: SEARCH_SERVING_LEXICAL_V1,
    ServingPerformanceEndpoint.RECOMMENDATION: RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
    ServingPerformanceEndpoint.PRODUCT: PRODUCT_SERVING_EXISTING_V1,
}


def concurrency_workload_for_endpoint(
    endpoint: ServingPerformanceEndpoint,
) -> ServingPerformanceWorkload:
    try:
        return CONCURRENCY_EXPERIMENT_WORKLOAD_BY_ENDPOINT[endpoint]
    except KeyError as exc:
        msg = f"no concurrency experiment workload for endpoint: {endpoint.value}"
        raise KeyError(msg) from exc


__all__ = [
    "CONCURRENCY_EXPERIMENT_WORKLOAD_BY_ENDPOINT",
    "concurrency_workload_for_endpoint",
]
