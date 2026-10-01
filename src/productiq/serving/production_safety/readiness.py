"""Readiness probe assembly (Phase 13.10-A)."""

from __future__ import annotations

from productiq.api.services.application_services import ApplicationServices
from productiq.serving.health import (
    DependencyReadinessStatus,
    ReadinessCheck,
    ReadinessResponse,
    ReadinessStatus,
)
from productiq.serving.protocols import (
    ProductServingService,
    RecommendationServingService,
    SearchServingService,
)

_SEARCH_EXTERNAL_CHECKS: tuple[tuple[str, str], ...] = (
    ("search_retrieval_database", "external database probe not implemented"),
    ("search_vector_index", "vector index probe not implemented"),
    ("search_bm25_index", "BM25 index probe not implemented"),
)

_RECOMMENDATION_EXTERNAL_CHECKS: tuple[tuple[str, str], ...] = (
    ("recommendation_catalog", "catalog dependency probe not implemented"),
    ("recommendation_context", "product context probe not implemented"),
)

_PRODUCT_EXTERNAL_CHECKS: tuple[tuple[str, str], ...] = (
    ("product_catalog", "catalog read probe not implemented"),
)


def _not_checked(name: str, message: str) -> ReadinessCheck:
    return ReadinessCheck(
        name=name,
        status=DependencyReadinessStatus.NOT_CHECKED,
        message=message,
    )


def _search_checks(service: SearchServingService | None) -> tuple[ReadinessCheck, ...]:
    if service is None:
        return (
            ReadinessCheck(
                name="search_serving",
                status=DependencyReadinessStatus.NOT_READY,
                message="not configured",
            ),
        )
    checks: list[ReadinessCheck] = [
        ReadinessCheck(
            name="search_serving",
            status=DependencyReadinessStatus.CONFIGURED,
            message="configured",
        ),
    ]
    checks.extend(_not_checked(name, msg) for name, msg in _SEARCH_EXTERNAL_CHECKS)
    return tuple(checks)


def _recommendation_checks(service: RecommendationServingService | None) -> tuple[ReadinessCheck, ...]:
    if service is None:
        return (
            ReadinessCheck(
                name="recommendation_serving",
                status=DependencyReadinessStatus.NOT_READY,
                message="not configured",
            ),
        )
    checks: list[ReadinessCheck] = [
        ReadinessCheck(
            name="recommendation_serving",
            status=DependencyReadinessStatus.CONFIGURED,
            message="configured",
        ),
    ]
    checks.extend(_not_checked(name, msg) for name, msg in _RECOMMENDATION_EXTERNAL_CHECKS)
    return tuple(checks)


def _product_checks(service: ProductServingService | None) -> tuple[ReadinessCheck, ...]:
    if service is None:
        return (
            ReadinessCheck(
                name="product_serving",
                status=DependencyReadinessStatus.NOT_READY,
                message="not configured",
            ),
        )
    checks: list[ReadinessCheck] = [
        ReadinessCheck(
            name="product_serving",
            status=DependencyReadinessStatus.CONFIGURED,
            message="configured",
        ),
    ]
    checks.extend(_not_checked(name, msg) for name, msg in _PRODUCT_EXTERNAL_CHECKS)
    return tuple(checks)


def build_readiness_response(application_services: ApplicationServices) -> ReadinessResponse:
    """Aggregate readiness without expensive dependency I/O."""
    checks = (
        *_search_checks(application_services.search_service),
        *_recommendation_checks(application_services.recommendation_service),
        *_product_checks(application_services.product_service),
    )
    configured = {
        "search_serving": application_services.search_service is not None,
        "recommendation_serving": application_services.recommendation_service is not None,
        "product_serving": application_services.product_service is not None,
    }
    blocking = False
    for check in checks:
        if check.status is not DependencyReadinessStatus.NOT_READY:
            continue
        if configured.get(check.name):
            blocking = True
            break
    if not any(configured.values()) or blocking:
        status = ReadinessStatus.NOT_READY
    else:
        status = ReadinessStatus.READY
    return ReadinessResponse(status=status, checks=checks)


__all__ = ["build_readiness_response"]
