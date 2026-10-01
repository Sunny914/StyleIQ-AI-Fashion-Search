"""Tests for Phase 13.2 FastAPI application foundation."""

from __future__ import annotations

import uuid

import pytest
from fastapi import Query
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.dependencies import get_health_service
from productiq.api.exceptions import ApiNotFoundError
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.middleware.request_id import REQUEST_ID_HEADER, normalize_request_id
from productiq.exceptions.base import ConfigurationError, RetrievalError
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorCode
from productiq.serving.health import HealthResponse, ReadinessResponse, ReadinessStatus
from productiq.serving.protocols import HealthServingService
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_READY,
    SERVING_API_ROUTE_PREFIX,
)


class _FakeHealthService:
    def health(self) -> HealthResponse:
        return HealthResponse(service="fake", api_version="v1")

    def ready(self) -> ReadinessResponse:
        return ReadinessResponse(status=ReadinessStatus.NOT_READY, checks=())


def test_create_app_without_infrastructure() -> None:
    app = create_app(serving_config=ServingConfig(service_name="test-svc", api_version="v1"))
    assert app.state.serving_config.service_name == "test-svc"
    assert app.state.search_service is None


def test_health_endpoint() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_HEALTH)
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "service": "productiq",
        "api_version": "v1",
    }


def test_readiness_endpoint_unconfigured_services() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_READY)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "not_ready"
    assert len(body["checks"]) == 3
    assert all(check["status"] == "not_ready" for check in body["checks"])


def test_api_version_prefix_in_openapi() -> None:
    app = create_app(serving_config=ServingConfig(api_version="v1"))
    with TestClient(app) as client:
        openapi = client.get(f"{SERVING_API_ROUTE_PREFIX}/openapi.json")
    assert openapi.status_code == 200
    info = openapi.json()["info"]
    assert info["title"] == "ProductIQ API"
    assert info["version"] == "v1"


def test_request_id_generated() -> None:
    app = create_app()
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_HEALTH)
    header = response.headers[REQUEST_ID_HEADER]
    uuid.UUID(header)


def test_request_id_propagation_from_client() -> None:
    app = create_app()
    supplied = "client-req-abc-123"
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_HEALTH, headers={REQUEST_ID_HEADER: supplied})
    assert response.headers[REQUEST_ID_HEADER] == supplied


def test_unsafe_request_id_is_replaced() -> None:
    assert normalize_request_id("bad id with spaces") != "bad id with spaces"
    generated = normalize_request_id("bad id with spaces")
    uuid.UUID(generated)


def test_validation_error_handling() -> None:
    app = create_app()

    @app.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/validate")
    def _validate(limit: int = Query(ge=1, le=5)) -> dict[str, int]:
        return {"limit": limit}

    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/validate", params={"limit": 99})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]
    payload = response.json()
    assert payload["error"]["code"] == "INVALID_REQUEST"
    assert "traceback" not in response.text.lower()


def test_productiq_error_handling() -> None:
    app = create_app()

    @app.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/retrieval-fail")
    def _fail() -> None:
        raise RetrievalError("pipeline contract failed")

    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/retrieval-fail")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INTERNAL_ERROR]
    assert response.json()["error"]["code"] == "INTERNAL_ERROR"


def test_not_found_error_handling() -> None:
    app = create_app()

    @app.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/not-found")
    def _missing() -> None:
        raise ApiNotFoundError("product missing")

    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/not-found")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]
    assert response.json()["error"]["code"] == "NOT_FOUND"


def test_configuration_error_status() -> None:
    app = create_app()

    @app.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/config")
    def _config() -> None:
        raise ConfigurationError("missing DATABASE_URL")

    with TestClient(app) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/config")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.CONFIGURATION_ERROR]
    assert response.json()["error"]["code"] == "CONFIGURATION_ERROR"


def test_unexpected_exception_handling() -> None:
    app = create_app()

    @app.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/boom")
    def _boom() -> None:
        raise RuntimeError("secret internals")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get(f"{SERVING_API_ROUTE_PREFIX}/_pytest/boom")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INTERNAL_ERROR]
    assert response.json()["error"]["message"] == "An unexpected error occurred"
    assert "secret" not in response.text


def test_dependency_override_health_service() -> None:
    app = create_app()
    app.dependency_overrides[get_health_service] = lambda: _FakeHealthService()
    with TestClient(app) as client:
        response = client.get(PLANNED_ROUTE_HEALTH)
    assert response.json()["service"] == "fake"
    app.dependency_overrides.clear()


def test_lifecycle_sets_running_flag() -> None:
    app = create_app()
    assert app.state.is_running is False
    with TestClient(app) as client:
        assert app.state.is_running is True
        client.get(PLANNED_ROUTE_HEALTH)
    assert app.state.is_running is False


def test_health_service_protocol_compatible() -> None:
    service: HealthServingService = _FakeHealthService()
    assert isinstance(service, HealthServingService)


@pytest.mark.parametrize(
    ("code", "status"),
    [
        (ApiErrorCode.INVALID_REQUEST, 400),
        (ApiErrorCode.NOT_FOUND, 404),
        (ApiErrorCode.CONFIGURATION_ERROR, 503),
        (ApiErrorCode.SERVICE_UNAVAILABLE, 503),
        (ApiErrorCode.INTERNAL_ERROR, 500),
        (ApiErrorCode.RATE_LIMITED, 429),
        (ApiErrorCode.OVERLOADED, 503),
    ],
)
def test_http_status_mapping(code: ApiErrorCode, status: int) -> None:
    assert HTTP_STATUS_BY_API_ERROR[code] == status
