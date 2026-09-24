"""Tests for application settings."""

from pathlib import Path

import pytest

from productiq.config.settings import (
    AppEnvironment,
    LogLevel,
    Settings,
    get_settings,
)


def test_default_settings() -> None:
    settings = Settings(_env_file=None)

    assert settings.app_name == "ProductIQ"
    assert settings.app_env is AppEnvironment.DEVELOPMENT
    assert settings.log_level is LogLevel.INFO
    assert settings.database_url == "postgresql://productiq:productiq@localhost:5432/productiq"


def test_environment_variables_override_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "ProductIQ Test")
    monkeypatch.setenv("APP_ENV", "testing")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

    settings = Settings(_env_file=None)

    assert settings.app_name == "ProductIQ Test"
    assert settings.app_env is AppEnvironment.TESTING
    assert settings.log_level is LogLevel.DEBUG
    assert settings.database_url == "postgresql://test:test@localhost:5432/testdb"


def test_env_file_values_are_loaded(tmp_path: Path) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text(
        (
            "APP_NAME=ProductIQ From Env File\n"
            "APP_ENV=production\n"
            "LOG_LEVEL=WARNING\n"
            "DATABASE_URL=postgresql://local:local@localhost:5432/productiq"
        ),
        encoding="utf-8",
    )

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "ProductIQ From Env File"
    assert settings.app_env is AppEnvironment.PRODUCTION
    assert settings.log_level is LogLevel.WARNING
    assert settings.database_url == "postgresql://local:local@localhost:5432/productiq"


def test_environment_variables_override_env_file(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    env_file = tmp_path / ".env"
    env_file.write_text("APP_NAME=From Env File\n", encoding="utf-8")
    monkeypatch.setenv("APP_NAME", "From Environment")

    settings = Settings(_env_file=env_file)

    assert settings.app_name == "From Environment"


@pytest.mark.parametrize(
    ("field_name", "value"),
    [
        ("APP_ENV", "staging"),
        ("LOG_LEVEL", "TRACE"),
    ],
)
def test_invalid_configuration_is_rejected(
    field_name: str,
    value: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(field_name, value)

    with pytest.raises(ValueError):
        Settings(_env_file=None)


def test_settings_expose_typed_values(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("LOG_LEVEL", "ERROR")

    settings = Settings(_env_file=None)

    assert isinstance(settings.app_env, AppEnvironment)
    assert isinstance(settings.log_level, LogLevel)
    assert settings.app_env.value == "production"
    assert settings.log_level.value == "ERROR"


def test_get_settings_returns_cached_instance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_NAME", "Cached Settings")

    first = get_settings()
    second = get_settings()

    assert first is second
    assert first.app_name == "Cached Settings"
