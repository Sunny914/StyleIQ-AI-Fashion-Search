"""Tests for database URL configuration and redaction."""

import pytest

from productiq.config import redact_database_url
from productiq.config.settings import Settings


def test_database_url_loaded_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://catalog_user:secret-pass@db.internal:5433/productiq_catalog",
    )
    settings = Settings(_env_file=None)

    assert "catalog_user" in settings.database_url
    assert "secret-pass" in settings.database_url


def test_redact_database_url_hides_password() -> None:
    database_url = "postgresql://catalog_user:secret-pass@db.internal:5433/productiq_catalog"

    redacted = redact_database_url(database_url)

    assert "secret-pass" not in redacted
    assert "catalog_user" in redacted
    assert "productiq_catalog" in redacted
    assert "***" in redacted


def test_settings_expose_redacted_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://user:topsecret@localhost:5432/productiq",
    )

    assert "topsecret" not in settings.redacted_database_url
    assert settings.redacted_database_url == redact_database_url(settings.database_url)


def test_redact_database_url_normalizes_psycopg_driver_prefix() -> None:
    database_url = "postgresql://user:secret@localhost:5432/productiq"

    redacted = redact_database_url(database_url)

    assert "secret" not in redacted
    assert "postgresql+psycopg://" in redacted
