"""Integration tests requiring a configured PostgreSQL instance."""

from __future__ import annotations

import importlib.metadata
import os

import pytest
from sqlalchemy import text
from sqlalchemy.engine import Engine, make_url

from productiq.config.settings import Settings
from productiq.database.engine import normalize_database_url
from productiq.database.health import check_database_health
from productiq.database.pgvector import (
    check_pgvector_extension,
    is_pgvector_extension_enabled,
    is_pgvector_python_available,
    require_pgvector_python_support,
)
from productiq.database.session import create_session_factory, session_scope

INTEGRATION_ENV_VAR = "PRODUCTIQ_RUN_INTEGRATION_TESTS"
INTEGRATION_SKIP_REASON = (
    f"Set {INTEGRATION_ENV_VAR}=1 to run PostgreSQL integration tests."
)


def _db_integration_enabled() -> bool:
    return os.getenv(INTEGRATION_ENV_VAR) == "1"


pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(not _db_integration_enabled(), reason=INTEGRATION_SKIP_REASON),
]


def test_live_settings_load_configured_database(
    integration_settings: Settings,
    integration_engine: Engine,
) -> None:
    url = make_url(normalize_database_url(integration_settings.database_url))

    assert url.host == "localhost"
    assert url.port == 5432
    assert url.database == "productIQ"
    assert url.username == "postgres"
    assert url.password is not None
    assert integration_engine.url.database == "productIQ"


def test_live_engine_connects(integration_engine: Engine) -> None:
    assert integration_engine.url.drivername == "postgresql+psycopg"
    assert integration_engine.url.database == "productIQ"


def test_live_database_health_check(integration_engine: Engine) -> None:
    check_database_health(integration_engine)


def test_live_session_executes_read_query(integration_engine: Engine) -> None:
    factory = create_session_factory(integration_engine)
    session = factory()
    try:
        database_name = session.execute(text("SELECT current_database()")).scalar_one()
        assert database_name == "productIQ"
        session.rollback()
    finally:
        session.close()


def test_live_session_scope_rolls_back_on_error(integration_engine: Engine) -> None:
    factory = create_session_factory(integration_engine)

    with pytest.raises(RuntimeError, match="rollback test"), session_scope(factory):
        raise RuntimeError("rollback test")


def test_live_postgresql_metadata(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        pg_version = connection.execute(text("SELECT version()")).scalar_one()
        current_user = connection.execute(text("SELECT current_user")).scalar_one()
        current_database = connection.execute(text("SELECT current_database()")).scalar_one()

    assert str(pg_version).startswith("PostgreSQL")
    assert current_user == "postgres"
    assert current_database == "productIQ"


def test_live_python_pgvector_support() -> None:
    assert is_pgvector_python_available() is True
    require_pgvector_python_support()
    assert importlib.metadata.version("pgvector") == "0.5.0"


def test_live_pgvector_extension_enabled(integration_engine: Engine) -> None:
    assert is_pgvector_extension_enabled(integration_engine) is True
    check_pgvector_extension(integration_engine)


def test_live_pgvector_extension_version(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        extension_version = connection.execute(
            text("SELECT extversion FROM pg_extension WHERE extname = 'vector'")
        ).scalar_one()

    assert extension_version is not None
    assert str(extension_version) != ""


def test_live_vector_type_query_uses_rollback(integration_engine: Engine) -> None:
    with integration_engine.connect() as connection:
        transaction = connection.begin()
        try:
            vector_text = connection.execute(
                text("SELECT '[1,2,3]'::vector::text")
            ).scalar_one()
            assert vector_text == "[1,2,3]"
        finally:
            transaction.rollback()
