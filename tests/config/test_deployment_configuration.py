"""Phase 14A deployment configuration tests."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.config import (
    AppEnvironment,
    load_deployment_configuration,
    settings_public_dict,
)
from productiq.config.cors import validate_cors_origin
from productiq.config.database_config import build_database_url_from_components
from productiq.config.deployment import DeploymentConfiguration
from productiq.config.settings import Settings
from productiq.serving.config import ServingConfig


def test_valid_environments() -> None:
    for value in ("development", "production-like", "production", "testing"):
        settings = Settings(_env_file=None, app_env=value)
        assert settings.app_env.value == value


def test_invalid_environment_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "staging")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_settings_defaults_without_env_file() -> None:
    settings = Settings(_env_file=None)
    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.database_url == "postgresql://productiq:productiq@localhost:5432/productiq"
    assert settings.processed_catalog_path == Path("resources/processed/product_catalog.parquet")


def test_environment_variable_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production-like")
    monkeypatch.setenv("PRODUCTIQ_PROCESSED_CATALOG_PATH", "data/catalog.parquet")
    settings = Settings(_env_file=None)
    assert settings.app_env is AppEnvironment.PRODUCTION_LIKE
    assert settings.processed_catalog_path == Path("data/catalog.parquet")


def test_database_url_from_components(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_DATABASE_USE_COMPONENT_FIELDS", "1")
    monkeypatch.setenv("DATABASE_PASSWORD", "s3cret")
    monkeypatch.setenv("PRODUCTIQ_DATABASE_HOST", "db.example.com")
    monkeypatch.setenv("PRODUCTIQ_DATABASE_PORT", "5433")
    monkeypatch.setenv("PRODUCTIQ_DATABASE_NAME", "catalog")
    monkeypatch.setenv("PRODUCTIQ_DATABASE_USER", "app")
    settings = Settings(_env_file=None)
    assert "db.example.com:5433" in settings.database_url
    assert "app" in settings.database_url


def test_database_components_require_password(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_DATABASE_USE_COMPONENT_FIELDS", "1")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_artifact_path_rejects_windows_drive() -> None:
    with pytest.raises(ValueError):
        Settings(_env_file=None, processed_catalog_path="E:/data/catalog.parquet")


def test_cors_development_defaults() -> None:
    settings = Settings(_env_file=None, app_env=AppEnvironment.DEVELOPMENT)
    assert "http://localhost:3000" in settings.cors_allowed_origins


def test_cors_production_requires_explicit_origins() -> None:
    settings = Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION)
    assert settings.cors_allowed_origins == []


def test_cors_custom_origins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "PRODUCTIQ_CORS_ALLOWED_ORIGINS",
        "https://app.example.com,https://staging.example.com",
    )
    settings = Settings(_env_file=None, app_env=AppEnvironment.PRODUCTION)
    assert settings.cors_allowed_origins == [
        "https://app.example.com",
        "https://staging.example.com",
    ]


def test_cors_wildcard_with_credentials_rejected() -> None:
    with pytest.raises(ValueError):
        Settings(
            _env_file=None,
            cors_allowed_origins_input="*",
            cors_allow_credentials=True,
        )


def test_cors_invalid_origin_syntax() -> None:
    with pytest.raises(ValueError):
        validate_cors_origin("not-a-url")


def test_secret_boundary_public_dict() -> None:
    settings = Settings(
        _env_file=None,
        database_url_override="postgresql://user:topsecret@localhost:5432/productiq",
    )
    public = settings_public_dict(settings)
    assert "topsecret" not in str(public).lower()
    assert "password" not in public
    assert "***" in public["database_url"]


def test_serving_config_deployment_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production-like")
    config = ServingConfig()
    assert config.deployment_environment is AppEnvironment.PRODUCTION_LIKE
    assert config.public_fields()["deployment_environment"] == "production-like"


def test_invalid_serving_numeric_limit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRODUCTIQ_API_MAX_TOP_K", "0")
    with pytest.raises(ValidationError):
        ServingConfig()


def test_invalid_database_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "not-a-database-url")
    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_load_deployment_configuration() -> None:
    deployment = load_deployment_configuration(
        settings=Settings(_env_file=None),
        serving_config=ServingConfig(_env_file=None),
    )
    assert isinstance(deployment, DeploymentConfiguration)
    public = deployment.public_dict()
    assert public["environment"] == "development"
    assert "serving" in public


def test_build_database_url_helper() -> None:
    url = build_database_url_from_components(
        host="localhost",
        port=5432,
        name="productiq",
        user="productiq",
        password="local",
    )
    assert url.startswith("postgresql://")


def test_serving_and_app_import_without_config_package_cycle() -> None:
    """Import order used at Uvicorn startup must not cycle config ↔ serving."""
    script = (
        "from productiq.config.environment import AppEnvironment\n"
        "from productiq.serving.config import ServingConfig\n"
        "from productiq.api.app import create_app\n"
        "assert AppEnvironment.PRODUCTION.value == 'production'\n"
        "assert ServingConfig is not None\n"
        "assert callable(create_app)\n"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout
