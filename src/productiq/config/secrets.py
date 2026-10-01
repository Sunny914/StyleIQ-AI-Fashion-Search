"""Secret classification for configuration (Phase 14A)."""

from __future__ import annotations

from typing import Any

# Environment variable names that must never appear in public diagnostics.
SECRET_ENV_ALIASES: frozenset[str] = frozenset(
    {
        "DATABASE_URL",
        "DATABASE_PASSWORD",
        "PRODUCTIQ_DATABASE_PASSWORD",
        "PRODUCTIQ_RATE_LIMIT_DEPLOYMENT_KEY",
    },
)

# Settings field names treated as sensitive (values excluded from public dicts).
SECRET_SETTINGS_FIELDS: frozenset[str] = frozenset(
    {
        "database_url",
        "database_password",
    },
)


def settings_public_dict(settings: Any) -> dict[str, str | int | bool | list[str]]:
    """Return non-secret settings safe for logs and readiness metadata."""
    from productiq.config.settings import Settings

    if not isinstance(settings, Settings):
        msg = "settings must be a Settings instance"
        raise TypeError(msg)
    return {
        "app_name": settings.app_name,
        "app_env": settings.app_env.value,
        "log_level": settings.log_level.value,
        "database_url": settings.redacted_database_url,
        "database_host": settings.database_host,
        "database_port": settings.database_port,
        "database_name": settings.database_name,
        "database_user": settings.database_user,
        "database_use_component_fields": settings.database_use_component_fields,
        "processed_catalog_path": str(settings.processed_catalog_path),
        "bm25_artifact_path": str(settings.bm25_artifact_path),
        "embeddings_artifact_path": str(settings.embeddings_artifact_path),
        "model_artifacts_dir": str(settings.model_artifacts_dir),
        "cors_allowed_origins": list(settings.cors_allowed_origins),
        "cors_allow_credentials": settings.cors_allow_credentials,
    }


__all__ = [
    "SECRET_ENV_ALIASES",
    "SECRET_SETTINGS_FIELDS",
    "settings_public_dict",
]
