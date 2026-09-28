"""Production retrieval pipeline configuration (Phase 4.19)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductionRetrievalConfig(BaseModel):
    """Frozen configuration for candidate pool depth (independent of request top_k)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidate_pool_top_k: int = Field(
        default=50,
        gt=0,
        description="RRF retrieval depth before structured hard filtering.",
    )

    @model_validator(mode="after")
    def validate_pool_depth(self) -> ProductionRetrievalConfig:
        if self.candidate_pool_top_k < 1:
            msg = "candidate_pool_top_k must be positive"
            raise ValueError(msg)
        return self


def validate_pool_against_request(*, candidate_pool_top_k: int, requested_top_k: int) -> None:
    if candidate_pool_top_k < requested_top_k:
        msg = "candidate_pool_top_k must be greater than or equal to requested top_k"
        raise ValueError(msg)


__all__ = ["ProductionRetrievalConfig", "validate_pool_against_request"]
