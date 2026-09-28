"""Ranked search integration contracts (Phase 10.5)."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from productiq.ranking.contracts import RankingResponse
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalResponse,
    RetrievalResponseMetadata,
)


class RankedSearchTimingsMs(BaseModel):
    """Lightweight latency breakdown for the integrated path (smoke observability)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieval_ms: float | None = Field(default=None, ge=0.0)
    feature_extraction_ms: float | None = Field(default=None, ge=0.0)
    normalization_ms: float | None = Field(default=None, ge=0.0)
    ranking_ms: float | None = Field(default=None, ge=0.0)
    total_ms: float | None = Field(default=None, ge=0.0)


class RankedSearchResponse(BaseModel):
    """Final ranked search output with retrieval execution metadata preserved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranking: RankingResponse
    retrieval_metadata: RetrievalResponseMetadata
    ranking_pipeline_version: str = Field(min_length=1)
    ranking_applied: bool
    candidate_count_before_filter: int | None = Field(default=None, ge=0)
    candidate_count_after_filter: int = Field(ge=0)
    candidate_count_entering_ranking: int = Field(ge=0)
    feature_schema_version: str | None = Field(default=None, min_length=1)
    normalization_schema_version: str | None = Field(default=None, min_length=1)
    timings_ms: RankedSearchTimingsMs | None = None

    def to_retrieval_response(self) -> RetrievalResponse:
        """Project ranked output into retrieval candidate order (ranked top-k)."""
        candidates: tuple[RetrievalCandidate, ...] = tuple(
            row.candidate.retrieval for row in self.ranking.ranked_candidates
        )
        metadata = self.retrieval_metadata.model_copy(
            update={"returned_candidate_count": len(candidates)},
        )
        return RetrievalResponse(candidates=candidates, metadata=metadata)


class RankedSearchEvaluationBundle(BaseModel):
    """Ranked-search output with filtered-pool product IDs for evaluation (Phase 10.6)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranked_search: RankedSearchResponse
    filtered_pool_product_ids: tuple[str, ...]
    rrf_ordered_product_ids: tuple[str, ...] = Field(
        description="RRF order after hard filtering (pre-baseline-ranking).",
    )


__all__ = [
    "RankedSearchEvaluationBundle",
    "RankedSearchResponse",
    "RankedSearchTimingsMs",
]
