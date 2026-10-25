"""Opt-in Phase 15C HTTP integration against live PostgreSQL/pgvector.

Set PRODUCTIQ_PHASE_15C_INTEGRATION=1 and a reachable DATABASE_URL.
Uses the labeled compose-demo fixture and a deterministic encoder double — not BGE, not 367k rows.
"""

from __future__ import annotations

import os

import numpy as np
import pytest
from fastapi.testclient import TestClient
from numpy.typing import NDArray

from productiq.api.app import create_app
from productiq.api.services.production_stack import build_production_application_services
from productiq.config.settings import Settings
from productiq.database.engine import create_engine_from_settings
from productiq.database.load_runtime_catalog import load_runtime_catalog
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.semantic import SemanticVector
from productiq.serving.config import ServingConfig

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.getenv("PRODUCTIQ_PHASE_15C_INTEGRATION") != "1",
        reason="Set PRODUCTIQ_PHASE_15C_INTEGRATION=1 to run Phase 15C HTTP integration.",
    ),
]


class _FixtureEncoder:
    embedding_dimension = PRODUCTIQ_EMBEDDING_DIMENSION
    model_id = "productiq-fixture-encoder"
    model_revision = "test"
    library_version = "test"
    device = "cpu"

    def encode_documents(self, texts: list[str]) -> NDArray[np.float32]:
        matrix = np.zeros((len(texts), PRODUCTIQ_EMBEDDING_DIMENSION), dtype=np.float32)
        for index, text in enumerate(texts):
            matrix[index] = self._vector_for_text(text)
        return matrix

    def encode_query(self, query_text: str) -> SemanticVector:
        values = tuple(float(value) for value in self._vector_for_text(query_text))
        return SemanticVector(values=values)

    def _vector_for_text(self, text: str) -> NDArray[np.float32]:
        vector = np.zeros(PRODUCTIQ_EMBEDDING_DIMENSION, dtype=np.float32)
        lowered = text.lower()
        if "shoe" in lowered or "nike" in lowered or "running" in lowered:
            vector[0] = 1.0
        elif "dress" in lowered or "floral" in lowered or "zara" in lowered:
            vector[1] = 1.0
        else:
            vector[2] = 1.0
        return vector


def _client() -> tuple[TestClient, Settings]:
    settings = Settings(_env_file=None)
    engine = create_engine_from_settings(settings)
    try:
        load_runtime_catalog(engine, mode="fixture")
        services, runtime = build_production_application_services(
            settings=settings,
            serving_config=ServingConfig(),
            encoder=_FixtureEncoder(),
            engine=engine,
        )
    except Exception:
        engine.dispose()
        raise
    app = create_app(app_settings=settings, application_services=services)
    app.state.production_serving_runtime = runtime
    return TestClient(app), settings


def test_product_detail_success_and_not_found() -> None:
    client, _settings = _client()
    with client:
        ok = client.get("/api/v1/products/compose-demo-001")
        missing = client.get("/api/v1/products/does-not-exist")
    assert ok.status_code == 200
    assert ok.json()["product_id"] == "compose-demo-001"
    assert missing.status_code == 404
    assert "not found" in missing.json()["error"]["message"].lower()


def test_lexical_and_semantic_search_return_fixture_products() -> None:
    client, _settings = _client()
    with client:
        lexical = client.post("/api/v1/search", json={"query": "navy cotton shirt", "top_k": 3})
        semantic = client.post("/api/v1/search", json={"query": "nike running shoes", "top_k": 3})
        filtered = client.post(
            "/api/v1/search",
            json={"query": "nike running shoes", "top_k": 3, "filters": {"category_gender": "Women"}},
        )
    assert lexical.status_code == 200
    assert semantic.status_code == 200
    lexical_ids = [item["product_id"] for item in lexical.json()["results"]]
    semantic_ids = [item["product_id"] for item in semantic.json()["results"]]
    assert "compose-demo-003" in lexical_ids
    assert semantic_ids
    assert semantic_ids[0] == "compose-demo-001"
    assert filtered.status_code == 200
    filtered_ids = [item["product_id"] for item in filtered.json()["results"]]
    assert "compose-demo-001" not in filtered_ids


def test_repeatable_fixture_load_validates_schema() -> None:
    settings = Settings(_env_file=None)
    engine = create_engine_from_settings(settings)
    try:
        first = load_runtime_catalog(engine, mode="fixture")
        second = load_runtime_catalog(engine, mode="fixture")
    finally:
        engine.dispose()
    assert first["schema"]["vector_extension_installed"] is True
    assert first["schema"]["embedding_type_is_vector"] is True
    assert first["schema"]["hnsw_cosine_opclass"] is True
    assert second["catalog_status"]["mode"] == "fixture"
    assert second["catalog_status"]["product_count"] == 3
    assert second["catalog_status"]["embedding_count"] == 3


def test_recommendations_exclude_seed() -> None:
    client, _settings = _client()
    with client:
        response = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "compose-demo-001", "top_k": 5},
        )
        ready = client.get("/api/v1/ready")
    assert response.status_code == 200
    ids = [item["product_id"] for item in response.json()["recommendations"]]
    assert "compose-demo-001" not in ids
    assert ready.status_code == 200
    assert ready.json()["status"] == "ready"
    catalog = next(check for check in ready.json()["checks"] if check["name"] == "catalog_data")
    assert catalog["status"] == "configured"
    assert "fixture" in (catalog.get("message") or "")
