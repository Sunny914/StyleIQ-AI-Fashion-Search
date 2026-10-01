"""Deployment environment labels (Phase 14A)."""

from __future__ import annotations

from enum import StrEnum


class AppEnvironment(StrEnum):
    """Supported deployment environments.

    ``testing`` is retained for pytest/CI isolation; it is not a deploy target.
    """

    DEVELOPMENT = "development"
    PRODUCTION_LIKE = "production-like"
    PRODUCTION = "production"
    TESTING = "testing"


def validate_app_environment(value: str) -> AppEnvironment:
    """Parse and validate an environment label."""
    candidate = value.strip().lower()
    try:
        return AppEnvironment(candidate)
    except ValueError as exc:
        msg = (
            "app_env must be one of: development, production-like, production, testing"
        )
        raise ValueError(msg) from exc


__all__ = ["AppEnvironment", "validate_app_environment"]
