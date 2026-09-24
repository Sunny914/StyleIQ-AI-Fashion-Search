"""Database connectivity health checks."""

from __future__ import annotations

from sqlalchemy import Engine, text
from sqlalchemy.exc import SQLAlchemyError

from productiq.database.engine import get_engine
from productiq.exceptions import DatabaseError


def check_database_health(engine: Engine | None = None) -> None:
    """Verify database connectivity by executing ``SELECT 1``."""
    resolved_engine = engine or get_engine()

    try:
        with resolved_engine.connect() as connection:
            result = connection.execute(text("SELECT 1"))
            if result.scalar_one() != 1:
                msg = "Database health check returned an unexpected result."
                raise DatabaseError(msg)
    except DatabaseError:
        raise
    except SQLAlchemyError as exc:
        msg = "Database health check failed."
        raise DatabaseError(msg) from exc
