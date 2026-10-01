"""Opt-in product API smoke against local processed catalog (Phase 13.5)."""

from __future__ import annotations

import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.product_wiring import (
    create_product_serving_service_from_processed_parquet,
)
from productiq.serving.versioning import SERVING_API_ROUTE_PREFIX

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_CATALOG_PATH = PROJECT_ROOT / "resources" / "processed" / "product_catalog.parquet"
PRODUCT_API_SMOKE_ENV = "PRODUCTIQ_PRODUCT_API_SMOKE"

pytestmark = pytest.mark.skipif(
    os.getenv(PRODUCT_API_SMOKE_ENV) != "1" or not PROCESSED_CATALOG_PATH.is_file(),
    reason=f"Set {PRODUCT_API_SMOKE_ENV}=1 and ensure processed catalog parquet exists.",
)


def test_product_api_smoke_against_processed_catalog() -> None:
    service = create_product_serving_service_from_processed_parquet(PROCESSED_CATALOG_PATH)
    app = create_app(product_service=service)
    with TestClient(app) as client:
        openapi = client.get(f"{SERVING_API_ROUTE_PREFIX}/openapi.json")
        assert "/api/v1/products/{product_id}" in openapi.json()["paths"]
