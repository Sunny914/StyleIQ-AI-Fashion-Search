"""SQLAlchemy session factory and lifecycle helpers."""

from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from productiq.database.engine import get_engine


def create_session_factory(engine: Engine | None = None) -> sessionmaker[Session]:
    """Create a session factory bound to the given engine."""
    resolved_engine = engine or get_engine()
    return sessionmaker(
        bind=resolved_engine,
        autoflush=False,
        autocommit=False,
        expire_on_commit=False,
    )


@lru_cache
def get_session_factory() -> sessionmaker[Session]:
    """Return the cached application session factory."""
    return create_session_factory()


@contextmanager
def session_scope(session_factory: sessionmaker[Session] | None = None) -> Generator[Session]:
    """Provide a transactional scope that commits, rolls back, and closes reliably."""
    factory = session_factory or get_session_factory()
    session = factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def reset_session_factory() -> None:
    """Reset cached session factory. Intended for tests."""
    get_session_factory.cache_clear()
