"""Benchmark run metadata helpers (Phase 13.8.2)."""

from __future__ import annotations

import platform
import sys

from productiq.serving.config import ServingConfig
from productiq.serving.performance.schema import (
    ServingConfigurationMetadata,
    ServingEnvironmentMetadata,
)


def build_environment_metadata(*, hostname: str | None = None) -> ServingEnvironmentMetadata:
    return ServingEnvironmentMetadata(
        python_version=sys.version.split()[0],
        platform=platform.platform(),
        productiq_version="0.1.0",
        hostname=hostname,
    )


def build_serving_configuration_metadata(
    *,
    serving_config: ServingConfig | None = None,
    artifact_identifiers: dict[str, str] | None = None,
) -> ServingConfigurationMetadata:
    config = serving_config or ServingConfig()
    return ServingConfigurationMetadata(
        api_version=config.api_version,
        api_max_top_k=config.api_max_top_k,
        service_name=config.service_name,
        artifact_identifiers=artifact_identifiers or {},
    )


__all__ = ["build_environment_metadata", "build_serving_configuration_metadata"]
