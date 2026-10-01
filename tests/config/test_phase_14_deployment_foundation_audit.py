"""Phase 14C deployment foundation audit tests."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from productiq.api.app import create_app
from productiq.config.deployment_manifest import build_deployment_manifest
from productiq.config.environment import AppEnvironment
from productiq.config.phase_14_deployment_foundation_audit import (
    AUDIT_CHECK_KEYS,
    compare_deployment_manifest_on_disk,
    default_check_statuses,
)
from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.secrets import settings_public_dict
from productiq.config.settings import Settings
from productiq.database.engine import create_engine_from_settings
from productiq.serving.versioning import PLANNED_ROUTE_HEALTH, PLANNED_ROUTE_READY
from tests.api.fakes import (
    RecordingProductService,
    RecordingRecommendationService,
    RecordingSearchService,
)


def test_single_configuration_system_entrypoints() -> None:
    settings = Settings(_env_file=None)
    deployment = __import__(
        "productiq.config.deployment",
        fromlist=["load_deployment_configuration"],
    ).load_deployment_configuration(settings=settings)
    assert deployment.settings is settings
    assert deployment.runtime_artifact_paths().processed_catalog == settings.processed_catalog_path


def test_manifest_contract_sections_match_builder() -> None:
    manifest_path = Path("resources/deployment/productiq_deployment_manifest.json")
    result = compare_deployment_manifest_on_disk(manifest_path=manifest_path)
    assert result["consistent"], result["mismatches"]


def test_runtime_paths_match_settings_fields() -> None:
    settings = Settings(
        _env_file=None,
        processed_catalog_path="data/catalog.parquet",
        embeddings_artifact_path="data/embeddings.parquet",
    )
    paths = resolve_runtime_artifact_paths(settings)
    assert paths.processed_catalog == Path("data/catalog.parquet")
    assert paths.embeddings == Path("data/embeddings.parquet")


def test_settings_public_dict_redacts_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url_override="postgresql://user:secret@db.example.com:5432/productiq",
    )
    public = settings_public_dict(settings)
    assert "secret" not in json.dumps(public).lower()


def test_create_app_does_not_create_database_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "productiq.database.engine.create_engine",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("no engine at create_app")),
    )
    app = create_app(
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
        app_settings=Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION),
    )
    assert app.state.runtime_artifact_paths is not None


def test_health_and_ready_responses_safe() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        app_settings=Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION),
    )
    with TestClient(app) as client:
        health = client.get(PLANNED_ROUTE_HEALTH).json()
        ready = client.get(PLANNED_ROUTE_READY).json()
    assert "password" not in json.dumps(health).lower()
    assert "password" not in json.dumps(ready).lower()
    assert ready["status"] in {"ready", "not_ready"}


def test_api_routes_regression_with_fakes() -> None:
    app = create_app(
        search_service=RecordingSearchService(),
        recommendation_service=RecordingRecommendationService(),
        product_service=RecordingProductService(),
        app_settings=Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION),
    )
    with TestClient(app) as client:
        search = client.post("/api/v1/search", json={"query": "shoes", "top_k": 1})
        rec = client.post(
            "/api/v1/recommendations",
            json={"seed_product_id": "P1", "top_k": 1},
        )
        product = client.get("/api/v1/products/P1")
    assert search.status_code == 200
    assert rec.status_code == 200
    assert product.status_code == 200


def test_docker_prerequisites_documented_in_manifest() -> None:
    manifest = build_deployment_manifest(settings=Settings(_env_file=None))
    assert manifest["application"]["api_entrypoint"] == "productiq.api.app:create_app"
    assert manifest["health"]["liveness"] == "/health"
    assert manifest["database"]["pgvector_extension"] == "vector"
    assert "DATABASE_URL" in json.dumps(manifest["configuration"])


def test_default_check_statuses_cover_audit_keys() -> None:
    statuses = default_check_statuses()
    assert set(statuses) == set(AUDIT_CHECK_KEYS)


def test_create_engine_from_settings_is_explicit_not_import_time() -> None:
    """Engine factory exists; import of create_app must not invoke it (see other test)."""
    assert callable(create_engine_from_settings)
