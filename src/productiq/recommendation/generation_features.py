"""Candidate-generation feature projection (Phase 11.4)."""

from __future__ import annotations

from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
)
from productiq.recommendation.feature_schema import CandidateGenerationFeatureGroup


def extract_generation_features(candidate: RecommendationCandidate) -> CandidateGenerationFeatureGroup:
    """Project Phase 11.2 provenance and generation score without cross-source normalization."""
    source_set = set(candidate.sources)
    source_count = len(candidate.sources)
    return CandidateGenerationFeatureGroup(
        retrieved_by_vector=RecommendationCandidateSource.VECTOR in source_set,
        retrieved_by_attribute=RecommendationCandidateSource.ATTRIBUTE in source_set,
        retrieved_by_bm25=RecommendationCandidateSource.BM25 in source_set,
        retrieved_by_multiple_sources=source_count > 1,
        source_count=source_count,
        candidate_generation_score=candidate.candidate_generation_score,
    )


__all__ = ["extract_generation_features"]
