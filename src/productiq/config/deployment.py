"""Deployment configuration facade (Phase 14A).

Hierarchy:

``Settings`` (APP_ENV, database, artifacts, CORS)
    +
``ServingConfig`` (HTTP limits, resilience, service metadata)
    →
``create_app`` (FastAPI + middleware)
"""

from __future__ import annotations

from dataclasses import dataclass

from productiq.config.environment import AppEnvironment
from productiq.config.runtime_artifacts import RuntimeArtifactPaths, resolve_runtime_artifact_paths
from productiq.config.runtime_validation import public_artifact_paths
from productiq.config.secrets import settings_public_dict
from productiq.config.settings import Settings, get_settings
from productiq.serving.config import ServingConfig


@dataclass(frozen=True, slots=True)
class DeploymentConfiguration:
    """Read-only view of deployment-related settings for diagnostics."""

    settings: Settings
    serving: ServingConfig

    @property
    def environment(self) -> AppEnvironment:
        return self.settings.app_env

    def public_dict(self) -> dict[str, object]:
        return {
            "environment": self.settings.app_env.value,
            "application": settings_public_dict(self.settings),
            "serving": self.serving.public_fields(),
            "runtime_artifacts": public_artifact_paths(self.runtime_artifact_paths()),
        }

    def runtime_artifact_paths(self) -> RuntimeArtifactPaths:
        return resolve_runtime_artifact_paths(self.settings)


def load_deployment_configuration(
    *,
    settings: Settings | None = None,
    serving_config: ServingConfig | None = None,
) -> DeploymentConfiguration:
    """Load Settings and ServingConfig from environment unless overridden."""
    resolved_settings = settings or get_settings()
    resolved_serving = serving_config or ServingConfig()
    return DeploymentConfiguration(
        settings=resolved_settings,
        serving=resolved_serving,
    )


__all__ = [
    "DeploymentConfiguration",
    "load_deployment_configuration",
]
