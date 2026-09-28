"""Reciprocal Rank Fusion configuration (Phase 4.16)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_RRF_RANK_CONSTANT = 60


class RRFConfig(BaseModel):
    """Immutable RRF hyperparameters."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    rank_constant: int = Field(
        default=DEFAULT_RRF_RANK_CONSTANT,
        gt=0,
        description="RRF smoothing constant k in 1 / (k + rank).",
    )


__all__ = ["DEFAULT_RRF_RANK_CONSTANT", "RRFConfig"]
