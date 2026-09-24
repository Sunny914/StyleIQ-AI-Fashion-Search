"""Database URL helpers and safe logging redaction."""

from __future__ import annotations

from sqlalchemy.engine import URL, make_url

from productiq.database.engine import normalize_database_url

REDACTED_PASSWORD = "***"


def redact_database_url(database_url: str) -> str:
    """Return a DATABASE_URL safe for logs (credentials redacted)."""
    normalized = normalize_database_url(database_url)
    url = make_url(normalized)
    redacted: URL = url.set(password=REDACTED_PASSWORD)
    return redacted.render_as_string(hide_password=True)


__all__ = ["REDACTED_PASSWORD", "redact_database_url"]
