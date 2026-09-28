"""Query–product matching features aligned with filtering semantics (Phase 10.2)."""

from __future__ import annotations

from productiq.ranking.feature_schema import MatchingFeatureGroup
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints, QueryRepresentation
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)


def _scalar_matches(product_value: str | None, constraint_value: str) -> bool:
    if product_value is None:
        return False
    return product_value == constraint_value


def _multivalue_matches(
    product_values: list[str] | None,
    constraint_values: list[str],
) -> bool:
    if product_values is None:
        return False
    product_set = set(product_values)
    return all(value in product_set for value in constraint_values)


def _optional_bool_match(
    *,
    constraint_value: str | list[str] | None,
    product_scalar: str | None = None,
    product_values: list[str] | None = None,
) -> bool | None:
    if constraint_value is None:
        return None
    if isinstance(constraint_value, list):
        return _multivalue_matches(product_values, constraint_value)
    return _scalar_matches(product_scalar, constraint_value)


def _brand_match(constraints: QueryFilterConstraints, product: ProductRepresentation) -> bool | None:
    if constraints.brand_normalized is not None:
        return _scalar_matches(product.brand_normalized, constraints.brand_normalized)
    if constraints.brand is not None:
        return _scalar_matches(product.brand, constraints.brand)
    return None


def _count_specified_matching_facets(constraints: QueryFilterConstraints) -> int:
    count = 0
    if constraints.brand_normalized is not None or constraints.brand is not None:
        count += 1
    for field_name in (
        "category_gender",
        "product_type",
        "color",
        "material",
    ):
        if getattr(constraints, field_name) is not None:
            count += 1
    return count


def _price_constraints_active(constraints: QueryFilterConstraints) -> bool:
    return (
        constraints.min_discount_price_inr is not None
        or constraints.max_discount_price_inr is not None
    )


def compute_constraint_match(
    *,
    constraints: QueryFilterConstraints | None,
    product: ProductRepresentation,
    filtering: FilteringRepresentation | None,
) -> bool | None:
    if constraints is None or not constraints_are_active(constraints):
        return None
    if filtering is not None:
        return filtering_satisfies_query_constraints(filtering, constraints)
    if _price_constraints_active(constraints):
        return None
    return filtering_satisfies_query_constraints(
        _filtering_stub_from_product(product),
        constraints,
    )


def _filtering_stub_from_product(product: ProductRepresentation) -> FilteringRepresentation:
    """Minimal filtering view for facet-only constraint checks (prices set to neutral sentinels)."""
    return FilteringRepresentation(
        product_id=product.product_id,
        source="ranking_feature_stub",
        brand=product.brand,
        brand_normalized=product.brand_normalized,
        category_gender=product.category_gender,
        product_type=product.product_type,
        color_raw="stub",
        color_is_coded=False,
        color=product.color,
        pattern=product.pattern,
        material=product.material,
        fit=product.fit,
        sleeve=product.sleeve,
        neckline=product.neckline,
        product_features=product.product_features,
        style_attributes=product.style_attributes,
        discount_price_inr=0,
        original_price_inr=0,
        price_anomaly=False,
    )


def extract_matching_features(
    query: QueryRepresentation,
    product: ProductRepresentation,
    *,
    filtering: FilteringRepresentation | None = None,
) -> MatchingFeatureGroup:
    constraints = query.constraints
    if constraints is None:
        return MatchingFeatureGroup(
            matched_attribute_count=0,
            attribute_overlap=None,
            constraint_match=None,
        )

    brand_match = _brand_match(constraints, product)
    color_match = _optional_bool_match(
        constraint_value=constraints.color,
        product_values=product.color,
    )
    product_type_match = _optional_bool_match(
        constraint_value=constraints.product_type,
        product_scalar=product.product_type,
    )
    category_gender_match = _optional_bool_match(
        constraint_value=constraints.category_gender,
        product_scalar=product.category_gender,
    )
    material_match = _optional_bool_match(
        constraint_value=constraints.material,
        product_values=product.material,
    )

    facet_matches: list[bool] = []
    for value in (
        brand_match,
        category_gender_match,
        product_type_match,
        color_match,
        material_match,
    ):
        if value is not None:
            facet_matches.append(value)

    matched_count = sum(1 for value in facet_matches if value)
    specified = _count_specified_matching_facets(constraints)
    overlap = (matched_count / specified) if specified > 0 else None

    return MatchingFeatureGroup(
        brand_match=brand_match,
        color_match=color_match,
        product_type_match=product_type_match,
        category_gender_match=category_gender_match,
        material_match=material_match,
        matched_attribute_count=matched_count,
        attribute_overlap=overlap,
        constraint_match=compute_constraint_match(
            constraints=constraints,
            product=product,
            filtering=filtering,
        ),
    )


__all__ = ["compute_constraint_match", "extract_matching_features"]
