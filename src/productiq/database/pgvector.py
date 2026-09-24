"""PostgreSQL pgvector extension support."""

from __future__ import annotations

import importlib.util

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.engine import get_engine
from productiq.exceptions import DatabaseError, PgvectorExtensionError

PGVECTOR_EXTENSION_NAME = "vector"
PGVECTOR_EXTENSION_CHECK_SQL = text(
    """
    SELECT EXISTS (
        SELECT 1
        FROM pg_extension
        WHERE extname = :extension_name
    )
    """
)
PGVECTOR_EXTENSION_CREATE_SQL = text("CREATE EXTENSION IF NOT EXISTS vector")


def is_pgvector_python_available() -> bool:
    """Return whether the Python pgvector package is installed."""
    return importlib.util.find_spec("pgvector.sqlalchemy") is not None


def require_pgvector_python_support() -> None:
    """Raise when the Python pgvector package is unavailable."""
    if is_pgvector_python_available():
        return

    msg = (
        "The pgvector Python package is not installed. "
        "Install the pgvector dependency to enable vector type support."
    )
    raise PgvectorExtensionError(msg)


def is_pgvector_extension_enabled(engine: Engine | None = None) -> bool:
    """Return whether the PostgreSQL pgvector extension is enabled."""
    require_pgvector_python_support()
    resolved_engine = engine or get_engine()

    try:
        with resolved_engine.connect() as connection:
            result = connection.execute(
                PGVECTOR_EXTENSION_CHECK_SQL,
                {"extension_name": PGVECTOR_EXTENSION_NAME},
            )
            return bool(result.scalar_one())
    except SQLAlchemyError as exc:
        msg = "Failed to verify pgvector extension availability."
        raise DatabaseError(msg) from exc


def check_pgvector_extension(engine: Engine | None = None) -> None:
    """Verify that the PostgreSQL pgvector extension is enabled."""
    if not is_pgvector_extension_enabled(engine):
        msg = (
            "The PostgreSQL pgvector extension is not enabled in the connected database. "
            "Enable it with CREATE EXTENSION vector or call ensure_pgvector_extension()."
        )
        raise PgvectorExtensionError(msg)


def ensure_pgvector_extension(engine: Engine | None = None) -> None:
    """Explicitly enable the PostgreSQL pgvector extension in the connected database."""
    require_pgvector_python_support()
    resolved_engine = engine or get_engine()

    try:
        with resolved_engine.begin() as connection:
            connection.execute(PGVECTOR_EXTENSION_CREATE_SQL)
    except SQLAlchemyError as exc:
        msg = "Failed to enable the PostgreSQL pgvector extension."
        raise PgvectorExtensionError(msg) from exc

    check_pgvector_extension(resolved_engine)
