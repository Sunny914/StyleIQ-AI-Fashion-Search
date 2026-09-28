"""Similarity feature propagation (Phase 11.4)."""

from __future__ import annotations

from productiq.recommendation.feature_schema import SimilarityFeatureGroup
from productiq.recommendation.similarity_schema import ContentSimilarity


def extract_similarity_features(similarity: ContentSimilarity) -> SimilarityFeatureGroup:
    """Copy Phase 11.3 component similarities (no fusion or recomputation)."""
    return SimilarityFeatureGroup(
        semantic_similarity=similarity.semantic_similarity,
        lexical_similarity=similarity.lexical_similarity,
    )


__all__ = ["extract_similarity_features"]
