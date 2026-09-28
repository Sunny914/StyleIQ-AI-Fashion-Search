"""Query-group feature normalization (Phase 10.3)."""

from __future__ import annotations

from collections.abc import Sequence

from productiq.ranking.feature_schema import RankingFeatures
from productiq.ranking.normalization_schema import (
    CONSTANT_FEATURE_NORMALIZED_VALUE,
    NORMALIZATION_SCHEMA_VERSION,
    NormalizedCatalogFeatureGroup,
    NormalizedMatchingFeatureGroup,
    NormalizedRankingFeatures,
    NormalizedRetrievalFeatureGroup,
)


def _finite_values(values: Sequence[float | None]) -> list[float]:
    return [value for value in values if value is not None]


def minmax_normalize_scalar(
    value: float | None,
    *,
    group_values: Sequence[float | None],
) -> float | None:
    if value is None:
        return None
    present = _finite_values(group_values)
    if not present:
        return None
    minimum = min(present)
    maximum = max(present)
    if maximum == minimum:
        return CONSTANT_FEATURE_NORMALIZED_VALUE
    return (value - minimum) / (maximum - minimum)


def rank_to_reciprocal_strength(rank: int | None) -> float | None:
    if rank is None:
        return None
    return 1.0 / float(rank)


def _bool_to_model_float(value: bool | None) -> float | None:
    if value is None:
        return None
    return 1.0 if value else 0.0


def normalize_matching_group(
    raw: RankingFeatures,
    *,
    group: Sequence[RankingFeatures],
) -> NormalizedMatchingFeatureGroup:
    counts = [float(row.matching.matched_attribute_count) for row in group]
    return NormalizedMatchingFeatureGroup(
        brand_match=_bool_to_model_float(raw.matching.brand_match),
        color_match=_bool_to_model_float(raw.matching.color_match),
        product_type_match=_bool_to_model_float(raw.matching.product_type_match),
        category_gender_match=_bool_to_model_float(raw.matching.category_gender_match),
        material_match=_bool_to_model_float(raw.matching.material_match),
        matched_attribute_count=minmax_normalize_scalar(
            float(raw.matching.matched_attribute_count),
            group_values=counts,
        ),
        attribute_overlap=raw.matching.attribute_overlap,
        constraint_match=_bool_to_model_float(raw.matching.constraint_match),
    )


def normalize_retrieval_group(
    raw: RankingFeatures,
    *,
    group: Sequence[RankingFeatures],
) -> NormalizedRetrievalFeatureGroup:
    bm25_scores = [row.retrieval.bm25_score for row in group]
    vector_scores = [row.retrieval.vector_similarity for row in group]
    rrf_scores = [row.retrieval.rrf_score for row in group]
    bm25_rank_strengths = [
        rank_to_reciprocal_strength(row.retrieval.bm25_rank) for row in group
    ]
    vector_rank_strengths = [
        rank_to_reciprocal_strength(row.retrieval.vector_rank) for row in group
    ]
    return NormalizedRetrievalFeatureGroup(
        bm25_score=minmax_normalize_scalar(raw.retrieval.bm25_score, group_values=bm25_scores),
        bm25_rank=minmax_normalize_scalar(
            rank_to_reciprocal_strength(raw.retrieval.bm25_rank),
            group_values=bm25_rank_strengths,
        ),
        vector_similarity=minmax_normalize_scalar(
            raw.retrieval.vector_similarity,
            group_values=vector_scores,
        ),
        vector_rank=minmax_normalize_scalar(
            rank_to_reciprocal_strength(raw.retrieval.vector_rank),
            group_values=vector_rank_strengths,
        ),
        rrf_score=minmax_normalize_scalar(raw.retrieval.rrf_score, group_values=rrf_scores),
        retrieved_by_bm25=_bool_to_model_float(raw.retrieval.retrieved_by_bm25),
        retrieved_by_vector=_bool_to_model_float(raw.retrieval.retrieved_by_vector),
        retrieved_by_both=_bool_to_model_float(raw.retrieval.retrieved_by_both),
    )


def normalize_catalog_group(
    raw: RankingFeatures,
    *,
    group: Sequence[RankingFeatures],
) -> NormalizedCatalogFeatureGroup:
    discount_values = [
        float(row.catalog.discount_price_inr) if row.catalog.discount_price_inr is not None else None
        for row in group
    ]
    original_values = [
        float(row.catalog.original_price_inr) if row.catalog.original_price_inr is not None else None
        for row in group
    ]
    amount_values = [
        float(row.catalog.discount_amount_inr) if row.catalog.discount_amount_inr is not None else None
        for row in group
    ]
    discount_raw = (
        float(raw.catalog.discount_price_inr) if raw.catalog.discount_price_inr is not None else None
    )
    original_raw = (
        float(raw.catalog.original_price_inr) if raw.catalog.original_price_inr is not None else None
    )
    amount_raw = (
        float(raw.catalog.discount_amount_inr) if raw.catalog.discount_amount_inr is not None else None
    )
    return NormalizedCatalogFeatureGroup(
        discount_price_inr=minmax_normalize_scalar(discount_raw, group_values=discount_values),
        original_price_inr=minmax_normalize_scalar(original_raw, group_values=original_values),
        discount_amount_inr=minmax_normalize_scalar(amount_raw, group_values=amount_values),
    )


def normalize_single_features(
    features: RankingFeatures,
    *,
    query_group: Sequence[RankingFeatures],
) -> NormalizedRankingFeatures:
    group = tuple(query_group)
    return NormalizedRankingFeatures(
        product_id=features.product_id,
        feature_schema_version=features.feature_schema_version,
        normalization_schema_version=NORMALIZATION_SCHEMA_VERSION,
        raw=features,
        retrieval=normalize_retrieval_group(features, group=group),
        matching=normalize_matching_group(features, group=group),
        catalog=normalize_catalog_group(features, group=group),
    )


def normalize_feature_rows(
    features_for_query: Sequence[RankingFeatures],
) -> tuple[NormalizedRankingFeatures, ...]:
    """Normalize within one query's candidate group; preserves order and does not mutate input."""
    group = tuple(features_for_query)
    return tuple(normalize_single_features(row, query_group=group) for row in group)


def normalize_features_for_query(
    features: Sequence[RankingFeatures],
) -> tuple[NormalizedRankingFeatures, ...]:
    """Alias for query-group batch normalization."""
    return normalize_feature_rows(features)


__all__ = [
    "minmax_normalize_scalar",
    "normalize_catalog_group",
    "normalize_feature_rows",
    "normalize_features_for_query",
    "normalize_matching_group",
    "normalize_retrieval_group",
    "normalize_single_features",
    "rank_to_reciprocal_strength",
]
