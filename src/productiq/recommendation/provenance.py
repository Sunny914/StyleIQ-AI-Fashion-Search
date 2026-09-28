"""Multi-source candidate provenance merge (Phase 11.2)."""

from __future__ import annotations

from dataclasses import dataclass, field

from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)

SOURCE_DISPLAY_ORDER: tuple[RecommendationCandidateSource, ...] = tuple(
    sorted(RecommendationCandidateSource, key=lambda item: item.value)
)

MERGE_SCORE_SOURCE_PRIORITY: tuple[RecommendationCandidateSource, ...] = (
    RecommendationCandidateSource.VECTOR,
    RecommendationCandidateSource.BM25,
    RecommendationCandidateSource.ATTRIBUTE,
    RecommendationCandidateSource.POPULARITY,
    RecommendationCandidateSource.BEHAVIORAL,
)


@dataclass
class _MutableMergedCandidate:
    product_id: str
    scores_by_source: dict[RecommendationCandidateSource, float | None] = field(default_factory=dict)

    def record(self, *, source: RecommendationCandidateSource, score: float | None) -> None:
        prior = self.scores_by_source.get(source)
        if prior is None and score is not None or prior is not None and score is not None and score > prior or source not in self.scores_by_source:
            self.scores_by_source[source] = score


def merged_generation_score(
    scores_by_source: dict[RecommendationCandidateSource, float | None],
) -> float | None:
    for source in MERGE_SCORE_SOURCE_PRIORITY:
        if source in scores_by_source:
            return scores_by_source[source]
    return None


def merge_recommendation_candidates(
    *candidate_groups: tuple[RecommendationCandidate, ...],
) -> tuple[RecommendationCandidate, ...]:
    """Union by ``product_id`` without summing or averaging cross-source scores."""
    merged: dict[str, _MutableMergedCandidate] = {}
    for group in candidate_groups:
        for row in group:
            bucket = merged.get(row.product_id)
            if bucket is None:
                bucket = _MutableMergedCandidate(product_id=row.product_id)
                merged[row.product_id] = bucket
            if len(row.sources) == 1:
                bucket.record(source=row.sources[0], score=row.candidate_generation_score)
            else:
                for source in row.sources:
                    bucket.record(source=source, score=None)
    built: list[RecommendationCandidate] = []
    for product_id in sorted(merged):
        bucket = merged[product_id]
        sources = tuple(source for source in SOURCE_DISPLAY_ORDER if source in bucket.scores_by_source)
        built.append(
            RecommendationCandidate(
                product_id=product_id,
                sources=sources,
                candidate_generation_score=merged_generation_score(bucket.scores_by_source),
            )
        )
    return tuple(built)


def single_source_candidate(
    *,
    product_id: str,
    source: RecommendationCandidateSource,
    candidate_generation_score: float | None,
) -> RecommendationCandidate:
    return RecommendationCandidate(
        product_id=product_id,
        sources=(source,),
        candidate_generation_score=candidate_generation_score,
    )


__all__ = [
    "MERGE_SCORE_SOURCE_PRIORITY",
    "SOURCE_DISPLAY_ORDER",
    "merge_recommendation_candidates",
    "merged_generation_score",
    "single_source_candidate",
]
