"""Concurrency sweep benchmark settings (Phase 13.8.6)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator

DEFAULT_CONCURRENCY_LEVELS: tuple[int, ...] = (1, 2, 4, 8)


class ConcurrencySweepSettings(BaseModel):
    """Independent warmups per concurrency level; same workload across the sweep."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    warmups: int = Field(default=5, ge=0)
    iterations: int = Field(default=30, ge=1)
    concurrency_levels: tuple[int, ...] = Field(default=DEFAULT_CONCURRENCY_LEVELS)

    @field_validator("concurrency_levels")
    @classmethod
    def validate_concurrency_levels(cls, value: tuple[int, ...]) -> tuple[int, ...]:
        if not value:
            msg = "concurrency_levels must not be empty"
            raise ValueError(msg)
        if any(level < 1 for level in value):
            msg = "each concurrency level must be >= 1"
            raise ValueError(msg)
        return value


DEFAULT_CONCURRENCY_SWEEP_SETTINGS = ConcurrencySweepSettings()


__all__ = [
    "DEFAULT_CONCURRENCY_LEVELS",
    "DEFAULT_CONCURRENCY_SWEEP_SETTINGS",
    "ConcurrencySweepSettings",
]
