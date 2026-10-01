"""Canonical recommendation serving performance workloads (Phase 13.8.4).

Distinct from Phase 11 recommendation *relevance* evaluation benchmarks.
Uses real catalog seed product IDs documented in ``productiq_recommendation_v1.json``.
SIMILAR recommendations only.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.exceptions.base import CatalogValidationError
from productiq.recommendation.seed_embedding import PostgresSeedEmbeddingProvider
from productiq.recommendation.seed_product import PostgresSeedProductResolver
from productiq.serving.performance.schema import (
    ServingPerformanceEndpoint,
    ServingPerformanceWorkload,
)
from productiq.serving.versioning import PLANNED_ROUTE_RECOMMENDATIONS

RECOMMENDATION_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION = "1.0.0"

_DEFAULT_TOP_K = 10
_SIMILAR_BODY = {"recommendation_type": "similar", "top_k": _DEFAULT_TOP_K}

RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1 = ServingPerformanceWorkload(
    workload_id="recommendation_serving_brand_activity_v1",
    workload_name="brand_activity_nike_running",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={
        "seed_product_id": "460946942002",
        **_SIMILAR_BODY,
    },
    description="Nike running seed (Phase 11 evaluation brand_activity group).",
)

RECOMMENDATION_SERVING_BRAND_ACTIVITY_ALT_V1 = ServingPerformanceWorkload(
    workload_id="recommendation_serving_brand_activity_alt_v1",
    workload_name="brand_activity_nike_running_alt",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={
        "seed_product_id": "460825114005",
        **_SIMILAR_BODY,
    },
    description="Alternate Nike running seed from the same evaluation group.",
)

RECOMMENDATION_SERVING_BRAND_COLOR_V1 = ServingPerformanceWorkload(
    workload_id="recommendation_serving_brand_color_v1",
    workload_name="brand_color_black_nike",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={
        "seed_product_id": "469193981005",
        **_SIMILAR_BODY,
    },
    description="Black Nike seed (brand_color evaluation group).",
)

RECOMMENDATION_SERVING_MATERIAL_V1 = ServingPerformanceWorkload(
    workload_id="recommendation_serving_material_v1",
    workload_name="material_focus_seed",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={
        "seed_product_id": "441123902006",
        **_SIMILAR_BODY,
    },
    description="Material-focused catalog seed from evaluation benchmark.",
)

RECOMMENDATION_SERVING_FILTER_V1 = ServingPerformanceWorkload(
    workload_id="recommendation_serving_filter_v1",
    workload_name="similar_with_structured_filters",
    endpoint=ServingPerformanceEndpoint.RECOMMENDATION,
    http_method="POST",
    route_path=PLANNED_ROUTE_RECOMMENDATIONS,
    request_body={
        "seed_product_id": "460946942002",
        "recommendation_type": "similar",
        "top_k": _DEFAULT_TOP_K,
        "filters": {"brand": "nike", "category_gender": "Men"},
    },
    description="SIMILAR seed with structured hard-filter constraints on the request.",
)

RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS: tuple[ServingPerformanceWorkload, ...] = (
    RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1,
    RECOMMENDATION_SERVING_BRAND_ACTIVITY_ALT_V1,
    RECOMMENDATION_SERVING_BRAND_COLOR_V1,
    RECOMMENDATION_SERVING_MATERIAL_V1,
    RECOMMENDATION_SERVING_FILTER_V1,
)

RECOMMENDATION_SERVING_WORKLOADS_BY_ID: dict[str, ServingPerformanceWorkload] = {
    workload.workload_id: workload for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS
}

RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS: tuple[str, ...] = tuple(
    dict.fromkeys(
        str((workload.request_body or {}).get("seed_product_id"))
        for workload in RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS
    ),
)


def get_recommendation_serving_performance_workload(workload_id: str) -> ServingPerformanceWorkload:
    try:
        return RECOMMENDATION_SERVING_WORKLOADS_BY_ID[workload_id]
    except KeyError as exc:
        msg = f"unknown recommendation serving performance workload_id: {workload_id}"
        raise KeyError(msg) from exc


def validate_recommendation_serving_performance_seeds_in_catalog(
    session: Session,
    *,
    seed_product_ids: Sequence[str] = RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS,
) -> None:
    """Ensure performance workload seeds resolve in PostgreSQL (production catalog)."""
    resolver = PostgresSeedProductResolver(session)
    missing: list[str] = []
    for seed_product_id in seed_product_ids:
        try:
            resolver.resolve_seed_product(seed_product_id)
        except CatalogValidationError:
            missing.append(seed_product_id)
    if missing:
        msg = f"recommendation performance seed(s) missing from catalog: {missing}"
        raise CatalogValidationError(msg)


def validate_recommendation_serving_performance_seed_embeddings(
    engine: Engine,
    *,
    seed_product_ids: Sequence[str] = RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS,
) -> None:
    """Ensure seeds have pgvector embeddings required for vector candidate generation."""
    provider = PostgresSeedEmbeddingProvider(engine)
    missing: list[str] = []
    for seed_product_id in seed_product_ids:
        try:
            provider.load_seed_embedding(seed_product_id)
        except CatalogValidationError:
            missing.append(seed_product_id)
    if missing:
        msg = f"recommendation performance seed embedding(s) missing: {missing}"
        raise CatalogValidationError(msg)


__all__ = [
    "RECOMMENDATION_SERVING_BRAND_ACTIVITY_ALT_V1",
    "RECOMMENDATION_SERVING_BRAND_ACTIVITY_V1",
    "RECOMMENDATION_SERVING_BRAND_COLOR_V1",
    "RECOMMENDATION_SERVING_FILTER_V1",
    "RECOMMENDATION_SERVING_MATERIAL_V1",
    "RECOMMENDATION_SERVING_PERFORMANCE_SEED_IDS",
    "RECOMMENDATION_SERVING_PERFORMANCE_WORKLOADS",
    "RECOMMENDATION_SERVING_PERFORMANCE_WORKLOAD_CATALOG_VERSION",
    "RECOMMENDATION_SERVING_WORKLOADS_BY_ID",
    "get_recommendation_serving_performance_workload",
    "validate_recommendation_serving_performance_seed_embeddings",
    "validate_recommendation_serving_performance_seeds_in_catalog",
]
