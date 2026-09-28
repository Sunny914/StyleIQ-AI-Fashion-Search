"""Ranking layer configuration (Phase 10.1)."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

DEFAULT_RANKING_VERSION = "10.1.0"
DEFAULT_TIE_BREAK_KEY: Literal["product_id"] = "product_id"


class RankingConfig(BaseModel):
    """Frozen ranking behavior metadata (no feature weights in Phase 10.1)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranking_version: str = Field(
        default=DEFAULT_RANKING_VERSION,
        min_length=1,
        description="Ranking contract / orchestration version label.",
    )
    tie_break_key: Literal["product_id"] = Field(
        default=DEFAULT_TIE_BREAK_KEY,
        description="Stable secondary key when ranking scores tie (deterministic ordering).",
    )


__all__ = [
    "DEFAULT_RANKING_VERSION",
    "DEFAULT_TIE_BREAK_KEY",
    "RankingConfig",
]
