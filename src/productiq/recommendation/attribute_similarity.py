"""Deterministic structured attribute similarity helpers (Phase 11.3)."""

from __future__ import annotations

from productiq.recommendation.similarity_schema import (
    MultiValueAttributeSimilarity,
    ScalarAttributeSimilarity,
    StructuredProductSimilarity,
)
from productiq.representation.schema import ProductRepresentation


def scalar_attribute_similarity(
    seed_value: str | None,
    candidate_value: str | None,
) -> float | None:
    if seed_value is None or candidate_value is None:
        return None
    left = seed_value.strip().casefold()
    right = candidate_value.strip().casefold()
    if not left or not right:
        return None
    return 1.0 if left == right else 0.0


def _normalized_multivalue_set(values: list[str] | None) -> set[str] | None:
    if values is None:
        return None
    return {value.casefold() for value in values}


def jaccard_similarity(
    seed_values: list[str] | None,
    candidate_values: list[str] | None,
) -> float | None:
    seed_set = _normalized_multivalue_set(seed_values)
    candidate_set = _normalized_multivalue_set(candidate_values)
    if seed_set is None or candidate_set is None:
        return None
    if not seed_set and not candidate_set:
        return None
    union = seed_set | candidate_set
    if not union:
        return None
    intersection = seed_set & candidate_set
    return len(intersection) / len(union)


def compute_scalar_attribute_similarity(
    seed_product: ProductRepresentation,
    candidate_product: ProductRepresentation,
) -> ScalarAttributeSimilarity:
    return ScalarAttributeSimilarity(
        brand=scalar_attribute_similarity(seed_product.brand, candidate_product.brand),
        brand_normalized=scalar_attribute_similarity(
            seed_product.brand_normalized,
            candidate_product.brand_normalized,
        ),
        category_gender=scalar_attribute_similarity(
            seed_product.category_gender,
            candidate_product.category_gender,
        ),
        product_type=scalar_attribute_similarity(
            seed_product.product_type,
            candidate_product.product_type,
        ),
    )


def compute_multivalue_attribute_similarity(
    seed_product: ProductRepresentation,
    candidate_product: ProductRepresentation,
) -> MultiValueAttributeSimilarity:
    return MultiValueAttributeSimilarity(
        color=jaccard_similarity(seed_product.color, candidate_product.color),
        pattern=jaccard_similarity(seed_product.pattern, candidate_product.pattern),
        material=jaccard_similarity(seed_product.material, candidate_product.material),
        fit=jaccard_similarity(seed_product.fit, candidate_product.fit),
        sleeve=jaccard_similarity(seed_product.sleeve, candidate_product.sleeve),
        neckline=jaccard_similarity(seed_product.neckline, candidate_product.neckline),
        product_features=jaccard_similarity(
            seed_product.product_features,
            candidate_product.product_features,
        ),
        style_attributes=jaccard_similarity(
            seed_product.style_attributes,
            candidate_product.style_attributes,
        ),
    )


def compute_structured_product_similarity(
    seed_product: ProductRepresentation,
    candidate_product: ProductRepresentation,
) -> StructuredProductSimilarity:
    return StructuredProductSimilarity(
        scalars=compute_scalar_attribute_similarity(seed_product, candidate_product),
        multivalue=compute_multivalue_attribute_similarity(seed_product, candidate_product),
    )


__all__ = [
    "compute_multivalue_attribute_similarity",
    "compute_scalar_attribute_similarity",
    "compute_structured_product_similarity",
    "jaccard_similarity",
    "scalar_attribute_similarity",
]
