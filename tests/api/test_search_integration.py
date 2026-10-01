"""Opt-in live search API smoke (Phase 13.3)."""

from __future__ import annotations

import os

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.api.services.search_wiring import create_search_serving_service_from_pipeline
from productiq.serving.versioning import PLANNED_ROUTE_SEARCH
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON
from tests.retrieval.integration.conftest import (
    LiveProductionRetrievalContext,
    production_retrieval_pytestmark,
)

SEARCH_API_SMOKE_ENV_VAR = "PRODUCTIQ_SEARCH_API_SMOKE"
SEARCH_API_SMOKE_SKIP_REASON = (
    f"Set {SEARCH_API_SMOKE_ENV_VAR}=1 with production retrieval integration enabled."
)

pytest_plugins = ["tests.retrieval.integration.conftest"]

pytestmark = [
    *production_retrieval_pytestmark,
    pytest.mark.skipif(
        os.getenv(SEARCH_API_SMOKE_ENV_VAR) != "1",
        reason=SEARCH_API_SMOKE_SKIP_REASON,
    ),
]


def test_live_search_api_smoke(live_production_retrieval: LiveProductionRetrievalContext) -> None:
    if os.getenv(INTEGRATION_ENV_VAR) != "1":
        pytest.skip(INTEGRATION_SKIP_REASON)
    service = create_search_serving_service_from_pipeline(live_production_retrieval.pipeline)
    app = create_app(search_service=service)
    with TestClient(app) as client:
        response = client.post(
            PLANNED_ROUTE_SEARCH,
            json={"query": "Nike running shoes", "top_k": 5},
        )
    assert response.status_code == 200
    body = response.json()
    assert body["returned_count"] <= 5
    assert body["request_id"]
