"""Phase 13.10-C integrated production serving audit tests."""

from __future__ import annotations

import json

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.observability import ObservabilityMiddleware
from productiq.api.middleware.request_id import RequestIdMiddleware
from productiq.api.middleware.resilience import ResilienceMiddleware
from productiq.config.environment import AppEnvironment
from productiq.config.settings import Settings
from productiq.observability.metrics import MetricName
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorCode
from productiq.serving.health import DependencyReadinessStatus
from productiq.serving.production_safety.readiness import build_readiness_response
from productiq.serving.resilience.keys import build_rate_limit_key, resolve_client_identifier
from productiq.serving.resilience.rate_limit import FixedWindowRateLimiter
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_READY,
    PLANNED_ROUTE_SEARCH,
)
from tests.api.fakes import RecordingRecommendationService, RecordingSearchService


def test_middleware_stack_order_request_id_outermost() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        app_settings=Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION),
    )
    names = [middleware.cls.__name__ for middleware in app.user_middleware]
    assert names[0] == RequestIdMiddleware.__name__
    assert ObservabilityMiddleware.__name__ in names
    assert ResilienceMiddleware.__name__ in names
    assert names.index(RequestIdMiddleware.__name__) < names.index(ObservabilityMiddleware.__name__)
    assert names.index(ObservabilityMiddleware.__name__) < names.index(ResilienceMiddleware.__name__)


def test_request_id_visible_to_observability_on_success() -> None:
    app = create_app(search_service=RecordingSearchService())
    collector = app.state.observability_sink
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "hat", "top_k": 1},
            headers={"X-Request-ID": "final-audit-req"},
        )
    assert response.status_code == 200
    events, _, _ = collector.snapshot()
    assert any(event.request_id == "final-audit-req" for event in events)


def test_rate_limit_rejection_is_observable() -> None:
    config = ServingConfig(rate_limit_enabled=True, rate_limit_requests_per_window=1)
    app = create_app(serving_config=config, search_service=RecordingSearchService())
    collector = app.state.observability_sink
    with TestClient(app) as client:
        client.post(PLANNED_ROUTE_SEARCH, json={"query": "a", "top_k": 1})
        rejected = client.post(PLANNED_ROUTE_SEARCH, json={"query": "b", "top_k": 1})
    assert rejected.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.RATE_LIMITED]
    _, metrics, _ = collector.snapshot()
    assert any(
        metric.name is MetricName.API_ERRORS_TOTAL
        and metric.labels.get("error_code") == ApiErrorCode.RATE_LIMITED.value
        for metric in metrics
    )


def test_all_api_error_codes_have_http_status() -> None:
    for code in ApiErrorCode:
        assert code in HTTP_STATUS_BY_API_ERROR


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ApiErrorCode.INVALID_REQUEST, 400),
        (ApiErrorCode.NOT_FOUND, 404),
        (ApiErrorCode.RATE_LIMITED, 429),
        (ApiErrorCode.CONFIGURATION_ERROR, 503),
        (ApiErrorCode.SERVICE_UNAVAILABLE, 503),
        (ApiErrorCode.OVERLOADED, 503),
        (ApiErrorCode.INTERNAL_ERROR, 500),
    ],
)
def test_error_taxonomy_http_mapping(code: ApiErrorCode, status: int) -> None:
    assert HTTP_STATUS_BY_API_ERROR[code] == status


def test_forwarded_for_ignored_when_proxy_not_trusted() -> None:
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.9")],
        "client": ("127.0.0.1", 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert resolve_client_identifier(request, trust_forwarded_for=False) == "127.0.0.1"
    key_direct = build_rate_limit_key(
        request,
        deployment_key="d",
        trust_forwarded_for=False,
    )
    scope["headers"] = [(b"x-forwarded-for", b"198.51.100.2")]
    request2 = Request(scope)
    key_spoof = build_rate_limit_key(request2, deployment_key="d", trust_forwarded_for=False)
    assert key_direct == key_spoof


def test_forwarded_for_used_when_proxy_trusted() -> None:
    scope = {
        "type": "http",
        "headers": [(b"x-forwarded-for", b"203.0.113.9, 198.51.100.1")],
        "client": ("127.0.0.1", 12345),
        "method": "GET",
        "path": "/",
        "query_string": b"",
        "server": ("test", 80),
        "scheme": "http",
    }
    request = Request(scope)
    assert resolve_client_identifier(request, trust_forwarded_for=True) == "203.0.113.9"


def test_readiness_distinguishes_configured_and_not_checked() -> None:
    from productiq.api.services.application_services import ApplicationServices

    services = ApplicationServices(
        serving_config=ServingConfig(),
        search_service=RecordingSearchService(),
    )
    response = build_readiness_response(services)
    by_name = {check.name: check.status for check in response.checks}
    assert by_name["search_serving"] is DependencyReadinessStatus.CONFIGURED
    assert by_name["search_bm25_index"] is DependencyReadinessStatus.NOT_CHECKED
    assert by_name["recommendation_serving"] is DependencyReadinessStatus.NOT_READY


def test_health_and_ready_responses_safe() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        health = client.get(PLANNED_ROUTE_HEALTH).text.lower()
        ready = client.get(PLANNED_ROUTE_READY).text.lower()
    for forbidden in ("password", "postgresql://", "traceback", "authorization"):
        assert forbidden not in health
        assert forbidden not in ready


def test_serving_config_public_fields_have_no_secrets() -> None:
    public = ServingConfig().public_fields()
    blob = json.dumps(public).lower()
    assert "password" not in blob
    assert "secret" not in blob
    assert "postgresql://" not in blob


def test_rate_limiter_bounded_memory() -> None:
    limiter = FixedWindowRateLimiter(requests_per_window=1, window_seconds=60, max_keys=2)
    for idx in range(5):
        limiter.allow(f"k{idx}")
    assert len(limiter._windows) <= 2


def test_create_app_import_without_external_infrastructure() -> None:
    from productiq.api.app import create_app as factory

    app = factory(search_service=RecordingSearchService())
    assert app.title == "ProductIQ API"


def test_dependency_isolation_search_vs_product() -> None:
    from productiq.exceptions.base import DatabaseError
    from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
    from productiq.serving.product_service import ProductionProductServingService

    app = create_app(
        search_service=RecordingSearchService(error=DatabaseError("db")),
        product_service=ProductionProductServingService(InMemoryProductCatalogReadProvider({})),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
        product = client.get("/api/v1/products/missing")
    assert search.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.SERVICE_UNAVAILABLE]
    assert product.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]


def test_application_composition_search_recommendation_product() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
    )
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
        rec = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "P1", "top_k": 1},
        )
    assert search.status_code in {200, HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]}
    assert rec.status_code in {200, HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]}
