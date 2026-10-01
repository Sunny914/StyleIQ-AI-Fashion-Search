"""CORS configuration helpers (Phase 14A)."""

from __future__ import annotations

from urllib.parse import urlparse


def parse_cors_origins(raw: str | list[str] | None) -> list[str]:
    """Parse comma-separated or list CORS origins."""
    if raw is None:
        return []
    if isinstance(raw, list):
        items = raw
    else:
        items = [part.strip() for part in raw.split(",")]
    return [item for item in items if item]


def validate_cors_origin(origin: str) -> str:
    """Validate a single allowed origin (scheme + host required)."""
    candidate = origin.strip()
    if not candidate:
        msg = "cors origin must be non-empty"
        raise ValueError(msg)
    if candidate == "*":
        return candidate
    parsed = urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        msg = f"cors origin must be http(s) URL with host: {origin!r}"
        raise ValueError(msg)
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        msg = f"cors origin must not include path, query, or fragment: {origin!r}"
        raise ValueError(msg)
    return candidate.rstrip("/") if parsed.path == "/" else candidate


def validate_cors_configuration(*, origins: list[str], allow_credentials: bool) -> list[str]:
    """Validate origin list and credential rules."""
    validated = [validate_cors_origin(origin) for origin in origins]
    if allow_credentials and "*" in validated:
        msg = "cors_allow_credentials cannot be used with wildcard origin"
        raise ValueError(msg)
    if allow_credentials and not validated:
        msg = "cors_allow_credentials requires at least one allowed origin"
        raise ValueError(msg)
    return validated


def default_cors_origins_for_environment(app_env: str) -> list[str]:
    """Development-friendly defaults for local Next.js; empty for other deploy targets."""
    if app_env == "development":
        return ["http://localhost:3000", "http://127.0.0.1:3000"]
    return []


__all__ = [
    "default_cors_origins_for_environment",
    "parse_cors_origins",
    "validate_cors_configuration",
    "validate_cors_origin",
]
