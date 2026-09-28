"""Ranking layer contracts (Phase 10.1)."""

from __future__ import annotations

import math
from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from productiq.ranking.config import RankingConfig
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.contracts import RetrievalCandidate


class RankingCandidate(BaseModel):
    """One product entering ranking with full retrieval provenance preserved."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    retrieval: RetrievalCandidate

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_product_id_matches_retrieval(self) -> Self:
        if self.product_id != self.retrieval.product_id:
            msg = "RankingCandidate.product_id must match retrieval.product_id"
            raise ValueError(msg)
        return self


class RankingRequest(BaseModel):
    """Ranking operation inputs: query context, explicit candidates, and top_k."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: QueryRepresentation
    candidates: tuple[RankingCandidate, ...] = ()
    top_k: int = Field(gt=0, description="Maximum ranked products to return.")
    config: RankingConfig = Field(default_factory=RankingConfig)

    @model_validator(mode="after")
    def validate_unique_candidate_identity(self) -> Self:
        product_ids = [candidate.product_id for candidate in self.candidates]
        if len(product_ids) != len(set(product_ids)):
            msg = "ranking candidates must have unique product_id values"
            raise ValueError(msg)
        return self


class RankedCandidate(BaseModel):
    """One product after ranking with score, rank, and preserved retrieval context."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    rank: int = Field(ge=1, description="1-based position in the ranked output order.")
    ranking_score: float = Field(description="Finite relevance score from the ranker (Phase 10.3+).")
    candidate: RankingCandidate

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("ranking_score")
    @classmethod
    def validate_finite_ranking_score(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "ranking_score must be a finite number"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_identity_consistency(self) -> Self:
        if self.product_id != self.candidate.product_id:
            msg = "RankedCandidate.product_id must match candidate.product_id"
            raise ValueError(msg)
        if self.product_id != self.candidate.retrieval.product_id:
            msg = "RankedCandidate must preserve retrieval product_id"
            raise ValueError(msg)
        return self


class RankingResponse(BaseModel):
    """Complete ranking result with auditable metadata."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ranked_candidates: tuple[RankedCandidate, ...] = ()
    requested_top_k: int = Field(gt=0)
    config: RankingConfig = Field(default_factory=RankingConfig)

    @computed_field  # type: ignore[prop-decorator]
    @property
    def returned_candidate_count(self) -> int:
        return len(self.ranked_candidates)

    @model_validator(mode="after")
    def validate_ranking_output(self) -> Self:
        if self.returned_candidate_count > self.requested_top_k:
            msg = "returned_candidate_count must not exceed requested_top_k"
            raise ValueError(msg)
        ranks = [row.rank for row in self.ranked_candidates]
        if ranks != sorted(ranks):
            msg = "ranked_candidates must be ordered by ascending rank"
            raise ValueError(msg)
        if ranks and ranks[0] != 1:
            msg = "ranked output must start at rank 1 when non-empty"
            raise ValueError(msg)
        for index, expected_rank in enumerate(ranks, start=1):
            if expected_rank != index:
                msg = "ranked_candidates must use contiguous 1-based ranks"
                raise ValueError(msg)
        product_ids = [row.product_id for row in self.ranked_candidates]
        if len(product_ids) != len(set(product_ids)):
            msg = "ranked output must not duplicate product_id values"
            raise ValueError(msg)
        return self


def ranking_request_to_dict(request: RankingRequest) -> dict[str, Any]:
    """Serialize a ranking request to a JSON-compatible dict."""
    return request.model_dump(mode="json")


def ranking_response_to_dict(response: RankingResponse) -> dict[str, Any]:
    """Serialize a ranking response to a JSON-compatible dict."""
    return response.model_dump(mode="json")


__all__ = [
    "RankedCandidate",
    "RankingCandidate",
    "RankingRequest",
    "RankingResponse",
    "ranking_request_to_dict",
    "ranking_response_to_dict",
]
