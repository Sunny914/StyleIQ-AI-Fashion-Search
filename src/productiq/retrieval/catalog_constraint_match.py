"""Deterministic hard-constraint evaluation against FilteringRepresentation (Phase 4.19)."""

from __future__ import annotations

from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints


def constraints_are_active(constraints: QueryFilterConstraints | None) -> bool:
    if constraints is None:
        return False
    return any(value is not None for value in constraints.model_dump().values())


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


def filtering_satisfies_query_constraints(
    filtering: FilteringRepresentation,
    constraints: QueryFilterConstraints,
) -> bool:
    """Return True when catalog filtering metadata satisfies all set hard constraints."""
    if constraints.brand is not None and not _scalar_matches(filtering.brand, constraints.brand):
        return False
    if constraints.brand_normalized is not None and not _scalar_matches(
        filtering.brand_normalized, constraints.brand_normalized
    ):
        return False
    if constraints.category_gender is not None and not _scalar_matches(
        filtering.category_gender, constraints.category_gender
    ):
        return False
    if constraints.product_type is not None and not _scalar_matches(
        filtering.product_type, constraints.product_type
    ):
        return False
    if constraints.color is not None and not _multivalue_matches(filtering.color, constraints.color):
        return False
    if constraints.pattern is not None and not _multivalue_matches(
        filtering.pattern, constraints.pattern
    ):
        return False
    if constraints.material is not None and not _multivalue_matches(
        filtering.material, constraints.material
    ):
        return False
    if constraints.fit is not None and not _multivalue_matches(filtering.fit, constraints.fit):
        return False
    if constraints.sleeve is not None and not _multivalue_matches(
        filtering.sleeve, constraints.sleeve
    ):
        return False
    if constraints.neckline is not None and not _multivalue_matches(
        filtering.neckline, constraints.neckline
    ):
        return False
    if constraints.product_features is not None and not _multivalue_matches(
        filtering.product_features, constraints.product_features
    ):
        return False
    if constraints.style_attributes is not None and not _multivalue_matches(
        filtering.style_attributes, constraints.style_attributes
    ):
        return False
    if (
        constraints.min_discount_price_inr is not None
        and filtering.discount_price_inr < constraints.min_discount_price_inr
    ):
        return False
    return (
        constraints.max_discount_price_inr is None
        or filtering.discount_price_inr <= constraints.max_discount_price_inr
    )

__all__ = [
    "constraints_are_active",
    "filtering_satisfies_query_constraints",
]
