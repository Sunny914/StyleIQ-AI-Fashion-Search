"""Resilience and traffic protection tests (Phase 13.10-B)."""

from __future__ import annotations

import os
import threading
from dataclasses import dataclass

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.http_status import HTTP_STATUS_BY_API_ERROR
from productiq.config.environment import AppEnvironment
from productiq.config.settings import Settings
from productiq.observability.runtime.sink import InMemoryObservabilityCollector
from productiq.serving.config import ServingConfig
from productiq.serving.errors import ApiErrorCode
from productiq.serving.resilience.concurrency import ConcurrencyGate
from productiq.serving.resilience.rate_limit import FixedWindowRateLimiter
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH
from tests.api.fakes import RecordingRecommendationService, RecordingSearchService


def _rate_limited_app(*, limit: int = 2, window: int = 60) -> object:
    config = ServingConfig(
        rate_limit_enabled=True,
        rate_limit_requests_per_window=limit,
        rate_limit_window_seconds=window,
        rate_limit_max_keys=100,
    )
    return create_app(serving_config=config, search_service=RecordingSearchService())


def test_rate_limit_allows_under_threshold() -> None:
    app = _rate_limited_app(limit=5)
    with TestClient(app) as client:
        for _ in range(5):
            response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "hat", "top_k": 1})
            assert response.status_code == 200


def test_rate_limit_rejects_with_429_and_retry_after() -> None:
    app = _rate_limited_app(limit=1)
    with TestClient(app) as client:
        first = client.post(PLANNED_ROUTE_SEARCH, json={"query": "hat", "top_k": 1})
        second = client.post(PLANNED_ROUTE_SEARCH, json={"query": "coat", "top_k": 1})
    assert first.status_code == 200
    assert second.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.RATE_LIMITED]
    assert second.json()["error"]["code"] == ApiErrorCode.RATE_LIMITED.value
    assert "Retry-After" in second.headers
    assert int(second.headers["Retry-After"]) >= 1


def test_fixed_window_resets_after_window(monkeypatch: pytest.MonkeyPatch) -> None:
    limiter = FixedWindowRateLimiter(requests_per_window=1, window_seconds=10, max_keys=10)
    now = {"t": 1000}

    def fake_time() -> int:
        return now["t"]

    monkeypatch.setattr("productiq.serving.resilience.rate_limit.time.time", lambda: fake_time())
    key = "k1"
    assert limiter.allow(key).allowed
    assert not limiter.allow(key).allowed
    now["t"] = 1010
    assert limiter.allow(key).allowed


def test_rate_limiter_concurrent_decisions() -> None:
    limiter = FixedWindowRateLimiter(requests_per_window=50, window_seconds=60, max_keys=100)
    allowed = 0
    lock = threading.Lock()

    def worker() -> None:
        nonlocal allowed
        for _ in range(40):
            if limiter.allow("shared-key").allowed:
                with lock:
                    allowed += 1

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert allowed == 50


def test_rate_limiter_bounded_keys() -> None:
    limiter = FixedWindowRateLimiter(requests_per_window=1, window_seconds=60, max_keys=2)
    limiter.allow("a")
    limiter.allow("b")
    limiter.allow("c")
    assert len(limiter._windows) <= 2


def test_concurrency_gate_rejects_when_full() -> None:
    config = ServingConfig(search_concurrency_limit=1, recommendation_concurrency_limit=0)
    app = create_app(serving_config=config, search_service=RecordingSearchService())
    gate = app.state.application_resilience.search_concurrency
    assert isinstance(gate, ConcurrencyGate)
    assert gate.try_acquire()
    assert not gate.try_acquire()
    gate.release()
    assert gate.try_acquire()
    gate.release()


def test_concurrency_overload_returns_503() -> None:
    config = ServingConfig(search_concurrency_limit=1)
    app = create_app(serving_config=config, search_service=RecordingSearchService())
    gate = app.state.application_resilience.search_concurrency
    assert isinstance(gate, ConcurrencyGate)
    gate.try_acquire()
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.OVERLOADED]
    gate.release()


def test_body_size_limit_invalid_request() -> None:
    config = ServingConfig(api_max_body_bytes=1024)
    app = create_app(serving_config=config, search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            content=b'{"query": "x", "top_k": 1}',
            headers={"Content-Type": "application/json", "Content-Length": "5000"},
        )
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_query_length_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_API_MAX_QUERY_LENGTH", "5")
    app = create_app(search_service=RecordingSearchService())
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "too-long-query", "top_k": 1})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.INVALID_REQUEST]


def test_request_timeout_mapping(monkeypatch: pytest.MonkeyPatch) -> None:
    import time

    @dataclass
    class SlowSearchService(RecordingSearchService):
        def search(self, request, *, request_id: str):  # type: ignore[no-untyped-def]
            time.sleep(0.05)
            return super().search(request, request_id=request_id)

    config = ServingConfig(serving_request_timeout_seconds=0.01)
    app = create_app(
        serving_config=config,
        search_service=SlowSearchService(),
        app_settings=Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION),
    )

    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
    assert response.status_code == HTTP_STATUS_BY_API_ERROR[ApiErrorCode.SERVICE_UNAVAILABLE]


def test_rate_limit_emits_observability_without_sensitive_labels() -> None:
    app = _rate_limited_app(limit=1)
    collector = app.state.observability_sink
    assert isinstance(collector, InMemoryObservabilityCollector)
    with TestClient(app) as client:
        client.post(PLANNED_ROUTE_SEARCH, json={"query": "a", "top_k": 1})
        client.post(PLANNED_ROUTE_SEARCH, json={"query": "b", "top_k": 1})
    _, metrics, _ = collector.snapshot()
    assert metrics
    assert all("request_id" not in metric.labels for metric in metrics)
    assert all("client_ip" not in metric.labels for metric in metrics)


def test_search_failure_does_not_block_recommendation_route() -> None:
    config = ServingConfig(rate_limit_enabled=True, rate_limit_requests_per_window=100)
    app = create_app(
        serving_config=config,
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
    )
    with TestClient(app) as client:
        search = client.post(PLANNED_ROUTE_SEARCH, json={"query": "x", "top_k": 1})
        rec = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "P1", "top_k": 1},
        )
    assert search.status_code == 200
    assert rec.status_code == 200


def test_application_composition_with_resilience_middleware() -> None:
    app = create_app(search_service=RecordingSearchService())
    assert hasattr(app.state, "application_resilience")
    with TestClient(app) as client:
        health = client.get("/api/v1/health")
        ready = client.get("/api/v1/ready")
    assert health.status_code == 200
    assert ready.status_code == 200


RESILIENCE_SMOKE_ENV = "PRODUCTIQ_RESILIENCE_SMOKE"


@pytest.mark.skipif(
    os.getenv(RESILIENCE_SMOKE_ENV) != "1",
    reason=f"Set {RESILIENCE_SMOKE_ENV}=1 for opt-in resilience smoke.",
)
def test_resilience_smoke_opt_in() -> None:
    app = _rate_limited_app(limit=10)
    with TestClient(app) as client:
        response = client.post(PLANNED_ROUTE_SEARCH, json={"query": "smoke", "top_k": 1})
    assert response.status_code == 200
