"""Public serving configuration view (Phase 13.10-A)."""

from __future__ import annotations

from productiq.serving.config import ServingConfig


def serving_config_public_dict(config: ServingConfig) -> dict[str, str | int]:
    """Bounded, non-secret fields safe for diagnostics and readiness metadata."""
    return config.public_fields()


__all__ = ["serving_config_public_dict"]
