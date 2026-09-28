"""Recommendation feature extraction (Phase 11.4)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from productiq.exceptions.base import RecommendationError
from productiq.recommendation.catalog_context_features import extract_catalog_context_features
from productiq.recommendation.contracts import RecommendationCandidate
from productiq.recommendation.feature_schema import RecommendationFeatures
from productiq.recommendation.generation_features import extract_generation_features
from productiq.recommendation.product_context import RecommendationProductContext
from productiq.recommendation.similarity_features import extract_similarity_features
from productiq.recommendation.similarity_schema import ContentSimilarity
from productiq.recommendation.structured_match_features import extract_structured_match_features
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation


def _validate_alignment(
    *,
    candidate: RecommendationCandidate,
    similarity: ContentSimilarity,
    context: RecommendationProductContext,
) -> None:
    if candidate.product_id != similarity.product_id:
        msg = (
            f"candidate.product_id {candidate.product_id!r} does not match "
            f"similarity.product_id {similarity.product_id!r}"
        )
        raise RecommendationError(msg)
    if candidate.product_id != context.product_id:
        msg = (
            f"candidate.product_id {candidate.product_id!r} does not match "
            f"context.product_id {context.product_id!r}"
        )
        raise RecommendationError(msg)


def extract_features(
    *,
    seed_product: ProductRepresentation,
    candidate: RecommendationCandidate,
    similarity: ContentSimilarity,
    context: RecommendationProductContext,
    seed_filtering: FilteringRepresentation | None = None,
) -> RecommendationFeatures:
    """Extract recommendation features for one aligned candidate (deterministic, no ranking)."""
    del seed_product
    _validate_alignment(candidate=candidate, similarity=similarity, context=context)
    return RecommendationFeatures(
        product_id=candidate.product_id,
        generation=extract_generation_features(candidate),
        similarity=extract_similarity_features(similarity),
        structured=extract_structured_match_features(similarity),
        catalog=extract_catalog_context_features(
            context.filtering,
            seed_filtering=seed_filtering,
        ),
    )


def extract_features_for_candidates(
    *,
    seed_product: ProductRepresentation,
    candidates: Sequence[RecommendationCandidate],
    similarities_by_product_id: Mapping[str, ContentSimilarity],
    context_by_product_id: Mapping[str, RecommendationProductContext],
    seed_filtering: FilteringRepresentation | None = None,
) -> tuple[RecommendationFeatures, ...]:
    """Extract features for each candidate, preserving candidate order."""
    seen_ids: set[str] = set()
    for candidate in candidates:
        if candidate.product_id in seen_ids:
            msg = f"duplicate candidate product_id {candidate.product_id!r} in batch"
            raise RecommendationError(msg)
        seen_ids.add(candidate.product_id)

    features: list[RecommendationFeatures] = []
    for candidate in candidates:
        product_id = candidate.product_id
        similarity = similarities_by_product_id.get(product_id)
        if similarity is None:
            msg = f"missing ContentSimilarity for product_id {product_id!r}"
            raise RecommendationError(msg)
        context = context_by_product_id.get(product_id)
        if context is None:
            msg = f"missing RecommendationProductContext for product_id {product_id!r}"
            raise RecommendationError(msg)
        features.append(
            extract_features(
                seed_product=seed_product,
                candidate=candidate,
                similarity=similarity,
                context=context,
                seed_filtering=seed_filtering,
            )
        )
    return tuple(features)


__all__ = ["extract_features", "extract_features_for_candidates"]
