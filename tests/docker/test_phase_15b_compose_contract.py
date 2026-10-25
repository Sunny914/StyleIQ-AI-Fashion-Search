"""Phase 15B Docker Compose + PostgreSQL/pgvector contract tests (no Docker required)."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.yml"


@pytest.fixture
def compose_text() -> str:
    assert COMPOSE_PATH.is_file(), "docker-compose.yml must exist for Phase 15B"
    return COMPOSE_PATH.read_text(encoding="utf-8")


def test_compose_defines_postgres_and_api_services(compose_text: str) -> None:
    assert re.search(r"^\s*postgres:\s*$", compose_text, re.MULTILINE)
    assert re.search(r"^\s*productiq-api:\s*$", compose_text, re.MULTILINE)


def test_compose_postgres_uses_pgvector_image(compose_text: str) -> None:
    assert "pgvector/pgvector" in compose_text


def test_compose_postgres_healthcheck_uses_pg_isready(compose_text: str) -> None:
    assert "pg_isready" in compose_text
    assert "healthcheck:" in compose_text


def test_compose_api_depends_on_postgres_health(compose_text: str) -> None:
    assert "depends_on:" in compose_text
    assert "service_healthy" in compose_text


def test_compose_database_url_uses_postgres_service_name(compose_text: str) -> None:
    assert "DATABASE_URL" in compose_text
    assert "${DATABASE_URL" in compose_text
    env_example = (REPO_ROOT / ".env.example").read_text(encoding="utf-8")
    assert "@postgres:" in env_example
    assert "localhost" not in compose_text
    assert "127.0.0.1" not in compose_text


def test_compose_does_not_publish_postgres_port_by_default(compose_text: str) -> None:
    postgres_block = compose_text.split("productiq-api:")[0]
    assert "5432:5432" not in postgres_block


def test_compose_api_builds_from_existing_dockerfile(compose_text: str) -> None:
    assert "dockerfile: Dockerfile" in compose_text or "dockerfile: Dockerfile" in compose_text.replace(" ", "")
    assert "context: ." in compose_text


def test_compose_api_exposes_port_8000(compose_text: str) -> None:
    assert "8000" in compose_text


def test_compose_no_windows_paths(compose_text: str) -> None:
    lowered = compose_text.lower()
    assert "e:\\\\" not in lowered
    assert "c:\\\\users" not in lowered


def test_compose_secrets_from_environment_not_literals(compose_text: str) -> None:
    assert "${POSTGRES_PASSWORD" in compose_text or "${DATABASE_URL" in compose_text
    assert "password123" not in compose_text


def test_bootstrap_module_exists() -> None:
    path = REPO_ROOT / "src/productiq/database/bootstrap_compose.py"
    assert path.is_file()
    text = path.read_text(encoding="utf-8")
    assert "bootstrap_productiq_database" in text
    assert "ensure_pgvector_extension" in text
    assert "create_product_embedding_hnsw_index" in text


def test_phase_15b_audit_script_exists() -> None:
    assert (REPO_ROOT / "scripts/run_phase_15b_database_audit.py").is_file()


def test_dockerignore_still_excludes_large_artifacts() -> None:
    content = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "resources/processed" in content


def test_lazy_settings_resolution_without_database_connection() -> None:
    from productiq.config.settings import Settings

    settings = Settings(_env_file=None, database_url_override="postgresql://u:p@postgres:5432/productiq")
    assert "postgres" in settings.database_url
    assert settings.database_port == 5432


def test_postgres_runtime_contract_constants() -> None:
    from productiq.config.database_runtime import postgres_runtime_contract

    contract = postgres_runtime_contract()
    assert contract.pgvector_extension == "vector"
    assert contract.embedding_dimension == 384
    assert contract.hnsw_index_name == "ix_products_embedding_hnsw_cosine"
    assert contract.pgvector_operator_class == "vector_cosine_ops"
