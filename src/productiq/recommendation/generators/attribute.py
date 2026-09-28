"""Structured attribute recommendation candidate generator (Phase 11.2)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
)
from productiq.recommendation.provenance import single_source_candidate
from productiq.recommendation.seed_product import RecommendationCatalogAccess
from productiq.representation.schema import ProductRepresentation

# ATTRIBUTE generation scores are not comparable to vector cosine or BM25 scores.
ATTRIBUTE_FIELD_WEIGHTS: dict[str, float] = {
    "brand_normalized": 3.0,
    "brand": 2.5,
    "category_gender": 2.0,
    "product_type": 1.5,
    "color": 1.0,
    "pattern": 1.0,
    "material": 1.0,
    "fit": 0.75,
    "sleeve": 0.75,
    "neckline": 0.75,
    "product_features": 0.5,
    "style_attributes": 0.5,
}


def _scalar_match(seed_value: str | None, candidate_value: str | None) -> bool:
    if seed_value is None or candidate_value is None:
        return False
    return seed_value.strip().casefold() == candidate_value.strip().casefold()


def _multivalue_overlap(seed_values: list[str] | None, candidate_values: list[str] | None) -> bool:
    if seed_values is None or candidate_values is None:
        return False
    seed_set = {value.casefold() for value in seed_values}
    candidate_set = {value.casefold() for value in candidate_values}
    return bool(seed_set & candidate_set)


def attribute_generation_score(
    seed_product: ProductRepresentation,
    candidate_product: ProductRepresentation,
) -> float:
    """Deterministic ATTRIBUTE score in ``[0, 1]`` from weighted shared structured fields."""
    if not _scalar_match(seed_product.category_gender, candidate_product.category_gender):
        return 0.0
    matched_weight = ATTRIBUTE_FIELD_WEIGHTS["category_gender"]
    total_weight = ATTRIBUTE_FIELD_WEIGHTS["category_gender"]

    scalar_fields = ("brand_normalized", "brand", "product_type")
    for field_name in scalar_fields:
        weight = ATTRIBUTE_FIELD_WEIGHTS[field_name]
        seed_value = getattr(seed_product, field_name)
        if seed_value is None:
            continue
        total_weight += weight
        if _scalar_match(seed_value, getattr(candidate_product, field_name)):
            matched_weight += weight

    multivalue_fields = (
        "color",
        "pattern",
        "material",
        "fit",
        "sleeve",
        "neckline",
        "product_features",
        "style_attributes",
    )
    for field_name in multivalue_fields:
        weight = ATTRIBUTE_FIELD_WEIGHTS[field_name]
        seed_values = getattr(seed_product, field_name)
        if seed_values is None:
            continue
        total_weight += weight
        if _multivalue_overlap(seed_values, getattr(candidate_product, field_name)):
            matched_weight += weight

    if total_weight <= 0.0:
        return 0.0
    return matched_weight / total_weight


@dataclass(frozen=True)
class AttributeRecommendationCandidateGenerator:
    """Deterministic content-based candidates from shared structured attributes."""

    catalog: RecommendationCatalogAccess

    def generate(
        self,
        request: RecommendationRequest,
        seed_product: ProductRepresentation,
    ) -> tuple[RecommendationCandidate, ...]:
        pool_top_k = request.config.candidate_generation.candidate_pool_top_k
        scored_rows: list[tuple[float, str]] = []
        for candidate_product in self.catalog.list_catalog_products():
            if candidate_product.product_id == seed_product.product_id:
                continue
            score = attribute_generation_score(seed_product, candidate_product)
            if score <= 0.0:
                continue
            scored_rows.append((score, candidate_product.product_id))
        scored_rows.sort(key=lambda row: (-row[0], row[1]))
        selected = scored_rows[:pool_top_k]
        return tuple(
            single_source_candidate(
                product_id=product_id,
                source=RecommendationCandidateSource.ATTRIBUTE,
                candidate_generation_score=score,
            )
            for score, product_id in selected
        )


__all__ = [
    "ATTRIBUTE_FIELD_WEIGHTS",
    "AttributeRecommendationCandidateGenerator",
    "attribute_generation_score",
]
