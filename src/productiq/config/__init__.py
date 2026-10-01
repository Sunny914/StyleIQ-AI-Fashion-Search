"""Configuration package for ProductIQ."""

from productiq.config.database import REDACTED_PASSWORD, redact_database_url
from productiq.config.environment import AppEnvironment, validate_app_environment
from productiq.config.secrets import (
    SECRET_ENV_ALIASES,
    SECRET_SETTINGS_FIELDS,
    settings_public_dict,
)
from productiq.config.settings import LogLevel, Settings, get_settings

# Deployment/manifest compose Settings + ServingConfig; load lazily so importing
# primitives (e.g. environment) does not pull productiq.serving.config.

__all__ = [
    "REDACTED_PASSWORD",
    "SECRET_ENV_ALIASES",
    "SECRET_SETTINGS_FIELDS",
    "AppEnvironment",
    "DeploymentConfiguration",
    "LogLevel",
    "Settings",
    "build_deployment_manifest",
    "get_settings",
    "load_deployment_configuration",
    "redact_database_url",
    "settings_public_dict",
    "validate_app_environment",
]


def __getattr__(name: str) -> object:
    if name in {"DeploymentConfiguration", "load_deployment_configuration"}:
        from productiq.config.deployment import (
            DeploymentConfiguration,
            load_deployment_configuration,
        )

        return {
            "DeploymentConfiguration": DeploymentConfiguration,
            "load_deployment_configuration": load_deployment_configuration,
        }[name]
    if name == "build_deployment_manifest":
        from productiq.config.deployment_manifest import build_deployment_manifest

        return build_deployment_manifest
    msg = f"module {__name__!r} has no attribute {name!r}"
    raise AttributeError(msg)


def __dir__() -> list[str]:
    return sorted(set(__all__))
