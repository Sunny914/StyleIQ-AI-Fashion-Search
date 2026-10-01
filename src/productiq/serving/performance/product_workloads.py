"""Canonical product serving performance workloads (Phase 13.8.5).

Distinct from generic ``workloads.py`` minimal fixtures (which use test IDs).
Uses real ``product_catalog.parquet`` product IDs for latency measurement.
"""

from __future__ import annotations

from collections.abc import Sequence

from productiq.exceptions.base import CatalogValidationError
from productiq.serving.catalog_read import ProductCatalogReadProvider
from productiq.serving.performance.schema import (
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.versioning import PLANNED_ROUTE_PRODUCT

PRODUCT_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION = "1.0.0"

# Verified present in resources/processed/product_catalog.parquet (evaluation-aligned IDs).
PRODUCT_SERVING_EXISTING_PRODUCT_ID_V1 = "460946942002"
PRODUCT_SERVING_EXISTING_PRODUCT_ID_ALT_V1 = "460825114005"
PRODUCT_SERVING_EXISTING_PRODUCT_ID_RICH_V1 = "441118465014"

# Deterministic ID guaranteed absent from the processed catalog (validated offline).
PRODUCT_SERVING_MISSING_PRODUCT_ID_V1 = "productiq_perf_missing_v1"

PRODUCT_SERVING_EXISTING_V1 = ServingPerformanceWorkload(
    workload_id="product_serving_existing_v1",
    workload_name="existing_catalog_product",
    endpoint=ServingPerformanceEndpoint.PRODUCT,
    http_method="GET",
    route_path=PLANNED_ROUTE_PRODUCT,
    path_parameters={"product_id": PRODUCT_SERVING_EXISTING_PRODUCT_ID_V1},
    description="Existing product (Nike running seed aligned with evaluation catalog).",
)

PRODUCT_SERVING_EXISTING_ALT_V1 = ServingPerformanceWorkload(
    workload_id="product_serving_existing_alt_v1",
    workload_name="existing_catalog_product_alt",
    endpoint=ServingPerformanceEndpoint.PRODUCT,
    http_method="GET",
    route_path=PLANNED_ROUTE_PRODUCT,
    path_parameters={"product_id": PRODUCT_SERVING_EXISTING_PRODUCT_ID_ALT_V1},
    description="Alternate existing catalog product.",
)

PRODUCT_SERVING_EXISTING_RICH_V1 = ServingPerformanceWorkload(
    workload_id="product_serving_existing_rich_v1",
    workload_name="existing_rich_public_fields",
    endpoint=ServingPerformanceEndpoint.PRODUCT,
    http_method="GET",
    route_path=PLANNED_ROUTE_PRODUCT,
    path_parameters={"product_id": PRODUCT_SERVING_EXISTING_PRODUCT_ID_RICH_V1},
    description="Existing product with populated description and image_url fields.",
)

PRODUCT_SERVING_MISSING_V1 = ServingPerformanceWorkload(
    workload_id="product_serving_missing_v1",
    workload_name="missing_product_not_found",
    endpoint=ServingPerformanceEndpoint.PRODUCT,
    http_method="GET",
    route_path=PLANNED_ROUTE_PRODUCT,
    path_parameters={"product_id": PRODUCT_SERVING_MISSING_PRODUCT_ID_V1},
    description=(
        "Deterministic missing product_id; expected HTTP 404 / ProductNotFoundError. "
        "Not part of the primary latency baseline (benchmark runner counts HTTP>=400 as errors)."
    ),
)

PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS: tuple[ServingPerformanceWorkload, ...] = (
    PRODUCT_SERVING_EXISTING_V1,
    PRODUCT_SERVING_EXISTING_ALT_V1,
    PRODUCT_SERVING_EXISTING_RICH_V1,
)

PRODUCT_SERVING_PERFORMANCE_WORKLOADS: tuple[ServingPerformanceWorkload, ...] = (
    *PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS,
    PRODUCT_SERVING_MISSING_V1,
)

PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS: tuple[str, ...] = tuple(
    str(workload.path_parameters["product_id"])
    for workload in PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS
)

PRODUCT_SERVING_WORKLOADS_BY_ID: dict[str, ServingPerformanceWorkload] = {
    workload.workload_id: workload for workload in PRODUCT_SERVING_PERFORMANCE_WORKLOADS
}


def get_product_serving_performance_workload(workload_id: str) -> ServingPerformanceWorkload:
    try:
        return PRODUCT_SERVING_WORKLOADS_BY_ID[workload_id]
    except KeyError as exc:
        msg = f"unknown product serving performance workload_id: {workload_id}"
        raise KeyError(msg) from exc


def validate_product_serving_performance_existing_products(
    catalog: ProductCatalogReadProvider,
    *,
    product_ids: Sequence[str] = PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS,
) -> None:
    missing = [product_id for product_id in product_ids if catalog.get_product(product_id) is None]
    if missing:
        msg = f"product serving performance catalog missing product_id(s): {missing}"
        raise CatalogValidationError(msg)


def validate_product_serving_performance_missing_product_absent(
    catalog: ProductCatalogReadProvider,
    *,
    missing_product_id: str = PRODUCT_SERVING_MISSING_PRODUCT_ID_V1,
) -> None:
    if catalog.get_product(missing_product_id) is not None:
        msg = f"missing workload product_id unexpectedly present in catalog: {missing_product_id!r}"
        raise CatalogValidationError(msg)


__all__ = [
    "PRODUCT_SERVING_EXISTING_ALT_V1",
    "PRODUCT_SERVING_EXISTING_PRODUCT_ID_ALT_V1",
    "PRODUCT_SERVING_EXISTING_PRODUCT_ID_RICH_V1",
    "PRODUCT_SERVING_EXISTING_PRODUCT_ID_V1",
    "PRODUCT_SERVING_EXISTING_RICH_V1",
    "PRODUCT_SERVING_EXISTING_V1",
    "PRODUCT_SERVING_MISSING_PRODUCT_ID_V1",
    "PRODUCT_SERVING_MISSING_V1",
    "PRODUCT_SERVING_PERFORMANCE_EXISTING_PRODUCT_IDS",
    "PRODUCT_SERVING_PERFORMANCE_SUCCESS_WORKLOADS",
    "PRODUCT_SERVING_PERFORMANCE_WORKLOADS",
    "PRODUCT_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION",
    "PRODUCT_SERVING_WORKLOADS_BY_ID",
    "get_product_serving_performance_workload",
    "validate_product_serving_performance_existing_products",
    "validate_product_serving_performance_missing_product_absent",
]
