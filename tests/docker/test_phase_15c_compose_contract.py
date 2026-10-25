"""Phase 15C Compose serving-integration contracts (no Docker required)."""

from __future__ import annotations

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_compose_mounts_processed_artifacts_read_only() -> None:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "/artifacts/processed:ro" in text
    assert "/app/resources/embedding:ro" in text
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "resources/processed" in dockerignore
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "COPY resources/embedding" in dockerfile


def test_compose_has_explicit_catalog_load_profile() -> None:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "catalog-load:" in text
    load_block = text.split("catalog-load:")[1]
    assert 'profiles: ["load"]' in load_block
    assert "productiq.database.load_runtime_catalog" in load_block
    assert "dockerfile: Dockerfile" in load_block
    assert "PRODUCTIQ_ENABLE_PRODUCTION_SERVING" in text


def test_api_image_healthcheck_allows_model_warmup() -> None:
    dockerfile = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "start-period=180s" in dockerfile
    compose = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "127.0.0.1" not in compose
    assert "HF_HOME" in compose


def test_compose_still_does_not_publish_postgres_host_port() -> None:
    text = (REPO_ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    postgres_block = text.split("productiq-api:")[0]
    assert "5432:5432" not in postgres_block


def test_phase_15c_loader_and_audit_scripts_exist() -> None:
    assert (REPO_ROOT / "src/productiq/database/load_runtime_catalog.py").is_file()
    assert (REPO_ROOT / "src/productiq/api/services/production_stack.py").is_file()
    assert (REPO_ROOT / "scripts/run_phase_15c_serving_audit.py").is_file()


def test_phase_15c_audit_builder_does_not_pass_unrun_checks() -> None:
    from productiq.config.phase_15c_serving_audit import build_phase_15c_audit_document

    document = build_phase_15c_audit_document(
        compose_config_ok=None,
        image_build_ok=None,
        fixture_load_ok=None,
        schema_ok=None,
        search_http_ok=None,
        product_http_ok=None,
        recommendation_http_ok=None,
        ready_ok=None,
        full_catalog_loaded=None,
        full_catalog_row_count=None,
        pytest_passed=0,
        pytest_failed=0,
        pytest_skipped=0,
        pytest_ok=None,
        ruff_ok=None,
        mypy_ok=None,
        catalog_mode=None,
    )
    assert document["checks"]["full_catalog_load"] == "NOT_RUN"
    assert document["checks"]["http_search"] == "NOT_RUN"
    assert document["checks"]["fixture_load"] == "NOT_RUN"
    assert document["phase_15c_status"] == "INCOMPLETE"
