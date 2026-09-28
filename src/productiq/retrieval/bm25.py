"""BM25 lexical relevance scoring over Phase 4.4 inverted indexes (Phase 4.5)."""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.lexical import InvertedLexicalIndex, tokenize_lexical_text
from productiq.retrieval.query_for_retrieval import RetrievalQueryView, build_retrieval_query_view

DEFAULT_BM25_K1 = 1.5
DEFAULT_BM25_B = 0.75


class BM25Config(BaseModel):
    """Immutable BM25 hyperparameters (starting values for ProductIQ experiments)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    k1: float = Field(default=DEFAULT_BM25_K1, ge=0.0)
    b: float = Field(default=DEFAULT_BM25_B, ge=0.0, le=1.0)

    @field_validator("k1", "b")
    @classmethod
    def validate_finite_parameters(cls, value: float) -> float:
        if not math.isfinite(value):
            msg = "BM25 parameters must be finite numbers"
            raise ValueError(msg)
        return value


class BM25CorpusStatistics(BaseModel):
    """Corpus-level statistics derived from an inverted lexical index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_count: int = Field(ge=0)
    average_document_length: float = Field(ge=0.0)
    total_document_length: int = Field(ge=0)

    @classmethod
    def from_index(cls, index: InvertedLexicalIndex) -> BM25CorpusStatistics:
        document_count = index.total_document_count()
        total_document_length = sum(index.document_lengths.values())
        if document_count == 0:
            average_document_length = 0.0
        else:
            average_document_length = total_document_length / document_count
        return cls(
            document_count=document_count,
            average_document_length=average_document_length,
            total_document_length=total_document_length,
        )


class BM25ScoredCandidate(BaseModel):
    """One product ID with a finite BM25 relevance score."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    score: float

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
            msg = "BM25 score must be a finite number"
            raise ValueError(msg)
        return value


def bm25_idf(document_count: int, document_frequency: int) -> float:
    """BM25 inverse document frequency for a normalized query term."""
    if document_count < 0 or document_frequency < 0:
        msg = "document_count and document_frequency must be non-negative"
        raise LexicalRetrievalError(msg)
    numerator = document_count - document_frequency + 0.5
    denominator = document_frequency + 0.5
    return math.log1p(numerator / denominator)


def unique_lexical_query_terms(query_lexical_text: str) -> tuple[str, ...]:
    """Unique normalized query terms in first-seen order (duplicate tokens counted once)."""
    seen: set[str] = set()
    unique_terms: list[str] = []
    for term in tokenize_lexical_text(query_lexical_text):
        if term in seen:
            continue
        seen.add(term)
        unique_terms.append(term)
    return tuple(unique_terms)


def _length_normalization_factor(
    document_length: int,
    average_document_length: float,
    b: float,
) -> float:
    if average_document_length <= 0.0:
        return 1.0
    return 1.0 - b + b * (document_length / average_document_length)


class BM25Scorer:
    """Scores documents using an existing ``InvertedLexicalIndex`` (no corpus scans for TF)."""

    def __init__(
        self,
        index: InvertedLexicalIndex,
        config: BM25Config | None = None,
    ) -> None:
        self._index = index
        self._config = config or BM25Config()
        self._stats = BM25CorpusStatistics.from_index(index)

    @property
    def config(self) -> BM25Config:
        return self._config

    @property
    def corpus_statistics(self) -> BM25CorpusStatistics:
        return self._stats

    def idf(self, term: str) -> float:
        df = self._index.document_frequency(term)
        return bm25_idf(self._stats.document_count, df)

    def score_term(self, term: str, product_id: str) -> float:
        term_frequency = self._index.term_frequency(term, product_id)
        if term_frequency == 0:
            return 0.0
        if self._stats.document_count == 0:
            return 0.0

        idf_value = self.idf(term)
        document_length = self._index.document_length(product_id)
        normalization = _length_normalization_factor(
            document_length,
            self._stats.average_document_length,
            self._config.b,
        )
        k1 = self._config.k1
        numerator = term_frequency * (k1 + 1.0)
        denominator = term_frequency + k1 * normalization
        if denominator <= 0.0:
            return 0.0
        contribution = idf_value * (numerator / denominator)
        if not math.isfinite(contribution):
            return 0.0
        return contribution

    def score_document(self, query_terms: Sequence[str], product_id: str) -> float:
        if product_id not in self._index.document_lengths:
            return 0.0
        seen: set[str] = set()
        total = 0.0
        for raw_term in query_terms:
            term = raw_term.strip().casefold()
            if not term or term in seen:
                continue
            seen.add(term)
            total += self.score_term(term, product_id)
        if not math.isfinite(total):
            return 0.0
        return total

    def score_lexical_query(
        self,
        query_lexical_text: str,
        *,
        candidate_product_ids: Sequence[str] | None = None,
    ) -> tuple[BM25ScoredCandidate, ...]:
        query_terms = unique_lexical_query_terms(query_lexical_text)
        if candidate_product_ids is None:
            candidates = self._index.retrieve_candidate_product_ids(query_lexical_text)
        else:
            candidates = tuple(dict.fromkeys(candidate_product_ids))
        if not query_terms or not candidates:
            return ()
        scored = tuple(
            BM25ScoredCandidate(
                product_id=product_id,
                score=self.score_document(query_terms, product_id),
            )
            for product_id in candidates
        )
        return rank_bm25_scored_candidates(scored)


def rank_bm25_scored_candidates(
    candidates: Sequence[BM25ScoredCandidate],
) -> tuple[BM25ScoredCandidate, ...]:
    """Sort by BM25 score descending, then ``product_id`` ascending."""
    return tuple(sorted(candidates, key=lambda candidate: (-candidate.score, candidate.product_id)))


def apply_bm25_top_k(
    candidates: Sequence[BM25ScoredCandidate],
    top_k: int | None,
) -> tuple[BM25ScoredCandidate, ...]:
    ranked = rank_bm25_scored_candidates(candidates)
    if top_k is None:
        return ranked
    if top_k <= 0:
        msg = "top_k must be a positive integer"
        raise LexicalRetrievalError(msg)
    return ranked[:top_k]


def score_bm25_lexical_query(
    index: InvertedLexicalIndex,
    query_lexical_text: str,
    *,
    config: BM25Config | None = None,
    top_k: int | None = None,
    candidate_product_ids: Sequence[str] | None = None,
) -> tuple[BM25ScoredCandidate, ...]:
    """Score and rank lexical query matches using BM25."""
    scorer = BM25Scorer(index, config=config)
    scored = scorer.score_lexical_query(
        query_lexical_text,
        candidate_product_ids=candidate_product_ids,
    )
    return apply_bm25_top_k(scored, top_k)


def score_bm25_from_view(
    index: InvertedLexicalIndex,
    view: RetrievalQueryView,
    *,
    config: BM25Config | None = None,
    top_k: int | None = None,
) -> tuple[BM25ScoredCandidate, ...]:
    """BM25 over ``RetrievalQueryView.lexical_retrieval_text`` only."""
    return score_bm25_lexical_query(
        index,
        view.lexical_retrieval_text,
        config=config,
        top_k=top_k,
    )


def score_bm25_from_retrieval_request(
    index: InvertedLexicalIndex,
    request: RetrievalRequest,
    *,
    config: BM25Config | None = None,
) -> tuple[BM25ScoredCandidate, ...]:
    """BM25 scoring using Phase 4.2 ``RetrievalRequest.top_k``."""
    view = build_retrieval_query_view(request.query)
    return score_bm25_from_view(index, view, config=config, top_k=request.top_k)


def bm25_scored_candidates_to_dict(
    candidates: Sequence[BM25ScoredCandidate],
) -> list[dict[str, Any]]:
    """Serialize scored candidates for notebooks and debugging."""
    return [candidate.model_dump(mode="json") for candidate in candidates]


__all__ = [
    "DEFAULT_BM25_B",
    "DEFAULT_BM25_K1",
    "BM25Config",
    "BM25CorpusStatistics",
    "BM25ScoredCandidate",
    "BM25Scorer",
    "apply_bm25_top_k",
    "bm25_idf",
    "bm25_scored_candidates_to_dict",
    "rank_bm25_scored_candidates",
    "score_bm25_from_retrieval_request",
    "score_bm25_from_view",
    "score_bm25_lexical_query",
    "unique_lexical_query_terms",
]
