"""Database URL resolution and validation (Phase 14A)."""

from __future__ import annotations

import re
from urllib.parse import quote_plus

from sqlalchemy.engine import make_url

_WINDOWS_ABSOLUTE_PATH = re.compile(r"^[A-Za-z]:[\\/]")


def reject_windows_absolute_path(value: str, *, field_name: str) -> str:
    """Reject drive-letter paths in configuration (portability)."""
    if _WINDOWS_ABSOLUTE_PATH.match(value.strip()):
        msg = f"{field_name} must not be a Windows absolute path"
        raise ValueError(msg)
    return value.strip()


def validate_database_url(url: str) -> str:
    """Ensure DATABASE_URL is a plausible SQLAlchemy URL."""
    candidate = url.strip()
    if not candidate:
        msg = "database_url must be non-empty"
        raise ValueError(msg)
    if len(candidate) > 2048:
        msg = "database_url exceeds maximum length"
        raise ValueError(msg)
    try:
        parsed = make_url(candidate)
    except Exception as exc:
        msg = "database_url is not a valid SQLAlchemy URL"
        raise ValueError(msg) from exc
    if parsed.drivername not in {"postgresql", "postgresql+psycopg"}:
        msg = "database_url must use a PostgreSQL driver (postgresql:// or postgresql+psycopg://)"
        raise ValueError(msg)
    return candidate


def build_database_url_from_components(
    *,
    host: str,
    port: int,
    name: str,
    user: str,
    password: str,
) -> str:
    """Build a PostgreSQL URL from discrete connection fields."""
    safe_user = quote_plus(user)
    safe_password = quote_plus(password)
    return f"postgresql://{safe_user}:{safe_password}@{host}:{port}/{name}"


def resolve_database_url(
    *,
    database_url: str | None,
    use_component_fields: bool,
    host: str,
    port: int,
    name: str,
    user: str,
    password: str | None,
    development_default_url: str,
) -> str:
    """Resolve the effective database URL from env-style inputs."""
    explicit = (database_url or "").strip()
    if use_component_fields:
        if not password:
            msg = "DATABASE_PASSWORD is required when PRODUCTIQ_DATABASE_USE_COMPONENT_FIELDS=1"
            raise ValueError(msg)
        built = build_database_url_from_components(
            host=host,
            port=port,
            name=name,
            user=user,
            password=password,
        )
        return validate_database_url(built)
    if explicit:
        return validate_database_url(explicit)
    return validate_database_url(development_default_url)


__all__ = [
    "build_database_url_from_components",
    "reject_windows_absolute_path",
    "resolve_database_url",
    "validate_database_url",
]
