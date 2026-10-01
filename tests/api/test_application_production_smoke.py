"""Opt-in smoke for integrated in-memory application composition (Phase 13.6)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from tests.api.test_application_integration import _integrated_services

APPLICATION_COMPOSITION_SMOKE_ENV = "PRODUCTIQ_APPLICATION_COMPOSITION_SMOKE"

pytestmark = pytest.mark.skipif(
    os.getenv(APPLICATION_COMPOSITION_SMOKE_ENV) != "1",
    reason=f"Set {APPLICATION_COMPOSITION_SMOKE_ENV}=1 to run application composition smoke.",
)


def test_application_composition_smoke() -> None:
    app = create_app(application_services=_integrated_services())
    with TestClient(app) as client:
        ready = client.get("/api/v1/ready")
        search = client.post("/api/v1/search", json={"query": "shoes", "top_k": 1})
        product = client.get("/api/v1/products/P1")
        rec = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "P1", "top_k": 1},
        )
    assert ready.json()["status"] == "ready"
    assert search.status_code == 200
    assert product.status_code == 200
    assert rec.status_code == 200
