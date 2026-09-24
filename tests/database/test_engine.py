"""Unit tests for database engine configuration."""

from productiq.config.settings import Settings
from productiq.database.engine import create_engine_from_settings, normalize_database_url


def test_normalize_database_url_uses_psycopg_driver() -> None:
    database_url = "postgresql://productiq:productiq@localhost:5432/productiq"

    assert (
        normalize_database_url(database_url)
        == "postgresql+psycopg://productiq:productiq@localhost:5432/productiq"
    )


def test_create_engine_from_settings_uses_settings_database_url() -> None:
    settings = Settings(
        _env_file=None,
        database_url="postgresql://tester:secret@db.example:5432/productiq_test",
    )

    engine = create_engine_from_settings(settings)
    try:
        assert engine.url.drivername == "postgresql+psycopg"
        assert engine.url.username == "tester"
        assert engine.url.password == "secret"
        assert engine.url.host == "db.example"
        assert engine.url.port == 5432
        assert engine.url.database == "productiq_test"
    finally:
        engine.dispose()
