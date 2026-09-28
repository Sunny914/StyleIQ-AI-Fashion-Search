"""Search and retrieval contract (Phase 4.2)."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Any, Protocol, Self, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator, model_validator

from productiq.representation.query_contract import QueryRepresentation


class RetrievalMethod(StrEnum):
    """Provenance label for a retrieval mechanism (scores are not comparable across values)."""

    BM25 = "bm25"
    VECTOR = "vector"
    HYBRID = "hybrid"


class RetrievalRequest(BaseModel):
    """Request to a retrieval engine: understood query plus candidate limit."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query: QueryRepresentation
    top_k: int = Field(gt=0, description="Number of candidates requested from retrieval (not final UI count).")


class RetrievalCandidate(BaseModel):
    """One product ID returned by a retrieval engine with native score and provenance."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    score: float = Field(
        description=(
            "Native retrieval score for single-method candidates (BM25 or vector). "
            "For Phase 4.15 hybrid union with both native scores and no fusion, this is 0.0. "
            "For Phase 4.16 RRF fused candidates, this equals fusion_score."
        )
    )
    method: RetrievalMethod
    retrieval_methods: tuple[RetrievalMethod, ...] | None = Field(
        default=None,
        description="Provenance for hybrid union candidates; omitted for single-method retrievers.",
    )
    bm25_score: float | None = Field(
        default=None,
        description="Native BM25 score when lexical retrieval contributed this candidate.",
    )
    vector_score: float | None = Field(
        default=None,
        description="Native cosine similarity when semantic retrieval contributed this candidate.",
    )
    fusion_score: float | None = Field(
        default=None,
        description="RRF fusion score when candidate fusion (Phase 4.16) is applied.",
    )
    bm25_rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank in the BM25 retrieval list when present.",
    )
    vector_rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank in the semantic retrieval list when present.",
    )
    metadata: dict[str, Any] | None = Field(
        default=None,
        description="Retrieval execution metadata only; not product catalog attributes.",
    )

    @field_validator("product_id")
    @classmethod
    def validate_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("score")
    @classmethod
    def validate_finite_score(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "score must be a finite number"
            raise ValueError(msg)
        return value

    @field_validator("bm25_score", "vector_score", "fusion_score")
    @classmethod
    def validate_finite_optional_native_score(cls, value: float | None) -> float | None:
        if value is None:
            return None
        if not math.isfinite(value):
            msg = "native retrieval score must be a finite number"
            raise ValueError(msg)
        return value

    @model_validator(mode="after")
    def validate_native_score_consistency(self) -> Self:
        if self.fusion_score is not None:
            if self.score != self.fusion_score:
                msg = "RRF fused candidate score must equal fusion_score"
                raise ValueError(msg)
            return self
        methods = self.resolved_retrieval_methods()
        has_bm25 = self.bm25_score is not None
        has_vector = self.vector_score is not None
        if RetrievalMethod.BM25 in methods and not has_bm25 and self.method is RetrievalMethod.HYBRID:
            msg = "hybrid candidate with BM25 provenance requires bm25_score"
            raise ValueError(msg)
        if RetrievalMethod.VECTOR in methods and not has_vector and self.method is RetrievalMethod.HYBRID:
            msg = "hybrid candidate with VECTOR provenance requires vector_score"
            raise ValueError(msg)
        if self.method is RetrievalMethod.HYBRID:
            if has_bm25 and has_vector:
                if self.score != 0.0:
                    msg = "dual-native hybrid candidates must use score=0.0 (not a fused score)"
                    raise ValueError(msg)
            elif has_bm25 and self.score != self.bm25_score:
                msg = "hybrid BM25-only candidate score must equal bm25_score"
                raise ValueError(msg)
            elif has_vector and self.score != self.vector_score:
                msg = "hybrid VECTOR-only candidate score must equal vector_score"
                raise ValueError(msg)
        return self

    def resolved_retrieval_methods(self) -> tuple[RetrievalMethod, ...]:
        """Return provenance methods, inferring from ``method`` for single-method retrievers."""
        if self.retrieval_methods is not None:
            return self.retrieval_methods
        if self.method is RetrievalMethod.BM25:
            return (RetrievalMethod.BM25,)
        if self.method is RetrievalMethod.VECTOR:
            return (RetrievalMethod.VECTOR,)
        return (RetrievalMethod.HYBRID,)


class RetrievalResponseMetadata(BaseModel):
    """Retrieval-call provenance (execution context, not product attributes)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    requested_top_k: int = Field(gt=0)
    lexical_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="BM25 candidate count before hybrid union (execution statistic).",
    )
    semantic_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="Semantic candidate count before hybrid union (execution statistic).",
    )
    unique_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="Unique product IDs in the hybrid candidate pool.",
    )
    overlap_count: int | None = Field(
        default=None,
        ge=0,
        description="Products returned by both BM25 and semantic retrieval.",
    )
    rrf_rank_constant: int | None = Field(
        default=None,
        gt=0,
        description="RRF smoothing constant k when candidate fusion is applied.",
    )
    hybrid_pool_count: int | None = Field(
        default=None,
        ge=0,
        description="Unique candidates in the pre-fusion pool.",
    )
    fused_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="Number of fused candidates returned after RRF ranking.",
    )
    candidate_pool_top_k: int | None = Field(
        default=None,
        gt=0,
        description="RRF retrieval depth requested before structured filtering (Phase 4.19).",
    )
    filtered_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="Candidates remaining after structured hard filtering.",
    )
    returned_candidate_count: int | None = Field(
        default=None,
        ge=0,
        description="Candidates returned after final top_k trim.",
    )
    production_pipeline_version: str | None = Field(
        default=None,
        min_length=1,
        description="Production retrieval orchestration version label when applicable.",
    )


class RetrievalResponse(BaseModel):
    """Ordered retrieval candidates; not final ranked search results."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    candidates: tuple[RetrievalCandidate, ...] = ()
    metadata: RetrievalResponseMetadata | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def candidate_count(self) -> int:
        return len(self.candidates)


@runtime_checkable
class Retriever(Protocol):
    """Minimal interface for BM25, vector, hybrid, and other retrieval engines."""

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse: ...


def retrieval_request_to_dict(request: RetrievalRequest) -> dict[str, Any]:
    """Serialize a retrieval request to a JSON-compatible dict."""
    return request.model_dump(mode="json")


def retrieval_response_to_dict(response: RetrievalResponse) -> dict[str, Any]:
    """Serialize a retrieval response to a JSON-compatible dict."""
    return response.model_dump(mode="json")


__all__ = [
    "RetrievalCandidate",
    "RetrievalMethod",
    "RetrievalRequest",
    "RetrievalResponse",
    "RetrievalResponseMetadata",
    "Retriever",
    "retrieval_request_to_dict",
    "retrieval_response_to_dict",
]
