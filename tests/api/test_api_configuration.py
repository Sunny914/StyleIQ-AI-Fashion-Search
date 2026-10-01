"""ServingConfig propagation into HTTP validation (Phase 13.7)."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorCode
from productiq.serving.versioning import PLANNED_ROUTE_HEALTH, PLANNED_ROUTE_SEARCH
from tests.api.fakes import RecordingSearchService


def test_health_reflects_serving_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_SERVICE_NAME", "api-test-svc")
    monkeypatch.setenv("PRODUCTIQ_API_VERSION", "v9")
    app = create_app(serving_config=ServingConfig())
    with TestClient(app) as client:
        body = client.get(PLANNED_ROUTE_HEALTH).json()
    assert body["service"] == "api-test-svc"
    assert body["api_version"] == "v9"


def test_api_max_top_k_env_rejects_above_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_API_MAX_TOP_K", "25")
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        over = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 26})
        at_max = client.post(PLANNED_ROUTE_SEARCH, json={"query": "shoes", "top_k": 25})
    assert over.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]
    assert at_max.status_code == 200


def test_openapi_info_uses_serving_config_api_version() -> None:
    app = create_app(serving_config=ServingConfig(api_version="v1"))
    with TestClient(app) as client:
        version = client.get("/api/v1/openapi.json").json()["info"]["version"]
    assert version == "v1"
