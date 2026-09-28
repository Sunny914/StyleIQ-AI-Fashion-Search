"""Recommendation candidate generator package (Phase 11.2)."""

from productiq.recommendation.generators.attribute import AttributeRecommendationCandidateGenerator
from productiq.recommendation.generators.bm25 import BM25RecommendationCandidateGenerator
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.generators.vector import VectorRecommendationCandidateGenerator

__all__ = [
    "AttributeRecommendationCandidateGenerator",
    "BM25RecommendationCandidateGenerator",
    "RecommendationCandidateGenerator",
    "VectorRecommendationCandidateGenerator",
]
