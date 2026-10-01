"""Production safety foundation tests (Phase 13.10-A)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.api.lifespan import build_lifespan
from productiq.exceptions.base import CatalogLoadError, DatabaseError
from productiq.serving.catalog_read import InMemoryProductCatalogReadProvider
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorCode, safe_client_message
from productiq.serving.health import ReadinessStatus
from productiq.serving.product_service import ProductionProductServingService
from productiq.serving.production_safety.config_public import serving_config_public_dict
from productiq.serving.versioning import (
    PLANNED_ROUTE_HEALTH,
    PLANNED_ROUTE_READY,
    PLANNED_ROUTE_SEARCH,
)
from tests.api.fakes import (
    RecordingProductService,
    RecordingRecommendationService,
    RecordingSearchService,
)


def test_serving_config_rejects_invalid_api_version() -> None:
    with pytest.raises(ValidationError):
        ServingConfig(api_version="not-a-version")


def test_serving_config_rejects_invalid_service_name() -> None:
    with pytest.raises(ValidationError):
        ServingConfig(service_name="bad name with spaces")


def test_serving_config_rejects_api_max_top_k_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        ServingConfig(api_max_top_k=0)
    with pytest.raises(ValidationError):
        ServingConfig(api_max_top_k=1001)


def test_serving_config_public_fields_exclude_secrets() -> None:
    config = ServingConfig()
    public = serving_config_public_dict(config)
    assert set(public.keys()) >= {"api_version", "api_max_top_k", "service_name"}
    assert "password" not in str(public).lower()


def test_recommendation_top_k_respects_api_max_top_k(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_API_MAX_TOP_K", "10")
    app = create_app(recommendation_service=RecordingRecommendationService())
    with TestClient(app) as client:
        over = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "P1", "top_k": 11},
        )
    assert over.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_ready_reports_not_checked_for_external_search_dependencies() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        body = client.get(PLANNED_ROUTE_READY).json()
    assert body["status"] == ReadinessStatus.READY.value
    statuses = {check["name"]: check["status"] for check in body["checks"]}
    assert statuses["search_serving"] == "configured"
    assert statuses["search_bm25_index"] == "not_checked"
    assert statuses["recommendation_serving"] == "not_ready"


def test_ready_response_does_not_leak_secrets() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        text = client.get(PLANNED_ROUTE_READY).text.lower()
    for forbidden in ("password", "postgresql://", "authorization", "traceback"):
        assert forbidden not in text


def test_health_is_liveness_only() -> None:
    app = create_app()
    with TestClient(app) as client:
        body = client.get(PLANNED_ROUTE_HEALTH).json()
    assert body["status"] == "ok"
    assert "checks" not in body


def test_search_dependency_failure_isolated_from_product() -> None:
    catalog = InMemoryProductCatalogReadProvider({})
    product = ProductionProductServingService(catalog)
    app = create_app(
        search_service=RecordingSearchService(error=DatabaseError("db unreachable")),
        product_service=product,
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "hat", "top_k": 1})
        product_resp = client.get("/api/v1/products/missing")
    assert search.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.SERVICE_UNAVAILABLE]
    assert product_resp.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.NOT_FOUND]
    assert "postgresql" not in search.text.lower()


def test_product_catalog_failure_does_not_break_search() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        product_service=RecordingProductService(error=CatalogLoadError("catalog offline")),
    )
    with TestClient(app, raise_server_exceptions=False) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "hat", "top_k": 1})
        product_resp = client.get("/api/v1/products/P1")
    assert search.status_code == 200
    assert product_resp.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.SERVICE_UNAVAILABLE]


def test_safe_client_message_redacts_credentials() -> None:
    message = safe_client_message(
        CatalogLoadError("failed postgresql://user:secret@db.example.com:5432/prod"),
    )
    assert "secret" not in message
    assert "postgresql://" not in message


def test_unhandled_exception_does_not_leak_internals() -> None:
    app = create_app(search_service=RecordingSearchService())

    @app.get("/api/v1/_test_boom")
    def _boom() -> None:
        raise RuntimeError("Traceback (most recent call last): C:\\secret\\path")

    with TestClient(app, raise_server_exceptions=False) as client:
        response = client.get("/api/v1/_test_boom")
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INTERNAL_ERROR]
    assert "traceback" not in response.text.lower()
    assert "secret" not in response.text.lower()


def test_lifespan_does_not_set_running_before_startup() -> None:
    app = create_app(search_service=RecordingSearchService())
    assert app.state.is_running is False


def test_create_app_import_without_external_services() -> None:
    from productiq.api.app import create_app as factory

    app = factory(search_service=RecordingSearchService())
    assert app.title == "ProductIQ API"


def test_build_lifespan_is_importable() -> None:
    assert build_lifespan is not None


PRODUCTION_SAFETY_SMOKE_ENV = "PRODUCTIQ_PRODUCTION_SAFETY_SMOKE"


@pytest.mark.skipif(
    os.getenv(PRODUCTION_SAFETY_SMOKE_ENV) != "1",
    reason=f"Set {PRODUCTION_SAFETY_SMOKE_ENV}=1 for opt-in production safety smoke.",
)
def test_production_safety_smoke_opt_in() -> None:
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        health = client.get(PLANNED_ROUTE_HEALTH)
        ready = client.get(PLANNED_ROUTE_READY)
    assert health.status_code == 200
    assert ready.status_code == 200
