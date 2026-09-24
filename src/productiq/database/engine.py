"""SQLAlchemy engine creation for ProductIQ."""

from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from productiq.config.settings import Settings, get_settings


def normalize_database_url(database_url: str) -> str:
    """Ensure the configured URL uses the psycopg driver."""
    if database_url.startswith("postgresql://"):
        return database_url.replace("postgresql://", "postgresql+psycopg://", 1)
    return database_url


def create_engine_from_settings(settings: Settings | None = None) -> Engine:
    """Create a SQLAlchemy engine from application settings."""
    resolved_settings = settings or get_settings()
    database_url = normalize_database_url(resolved_settings.database_url)
    return create_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_engine() -> Engine:
    """Return the cached application database engine."""
    return create_engine_from_settings()


def reset_database_state() -> None:
    """Reset cached database resources. Intended for tests."""
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
