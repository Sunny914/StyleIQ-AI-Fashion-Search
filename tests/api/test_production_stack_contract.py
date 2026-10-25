"""Phase 15C production-stack wiring contracts (no Docker, no model download)."""

from __future__ import annotations

import pytest

from productiq.api.app import create_app
from productiq.config.settings import Settings
from productiq.database.load_runtime_catalog import classify_catalog_mode


def test_create_app_does_not_enable_production_serving_by_default() -> None:
    settings = Settings(_env_file=None, enable_production_serving=False)
    assert settings.enable_production_serving is False
    app = create_app(app_settings=settings)
    assert app.state.search_service is None
    assert app.state.recommendation_service is None
    assert app.state.product_service is None
    assert getattr(app.state, "production_serving_runtime", None) is None


def test_default_create_app_does_not_open_a_database_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("database engine must not be created for the default app")

    monkeypatch.setattr("productiq.database.engine.create_engine_from_settings", _boom)
    settings = Settings(_env_file=None, enable_production_serving=False)
    app = create_app(app_settings=settings)
    assert app.state.search_service is None


def test_classify_catalog_mode_labels_fixture_and_full() -> None:
    assert classify_catalog_mode(0) == "empty"
    assert classify_catalog_mode(3, fixture_id_count=3) == "fixture"
    assert classify_catalog_mode(367_172, fixture_id_count=0) == "full"
    assert classify_catalog_mode(10, fixture_id_count=0) == "partial"


def test_production_serving_fails_fast_on_unreachable_database() -> None:
    from sqlalchemy.exc import SQLAlchemyError

    settings = Settings(
        _env_file=None,
        database_url_override="postgresql://productiq:productiq@127.0.0.1:1/productiq?connect_timeout=1",
        enable_production_serving=True,
    )
    with pytest.raises(SQLAlchemyError):
        create_app(app_settings=settings)


def test_load_runtime_catalog_module_is_explicit_operator_entry() -> None:
    from productiq.database.load_runtime_catalog import load_runtime_catalog

    assert callable(load_runtime_catalog)
