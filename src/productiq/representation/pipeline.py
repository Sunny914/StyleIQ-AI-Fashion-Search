"""Orchestration for product-side representation generation (Phase 3.9)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from pydantic import BaseModel, ConfigDict

from productiq.representation.builder import build_product_representation
from productiq.representation.filtering import (
    FilteringRepresentation,
    build_filtering_representation_from_canonical,
    filtering_representation_to_dict,
)
from productiq.representation.lexical import build_lexical_text_from_canonical
from productiq.representation.schema import ProductRepresentation
from productiq.representation.semantic import build_semantic_text_from_canonical
from productiq.representation.serializers import representation_to_dict
from productiq.representation.text import build_product_text

PRODUCT_REPRESENTATION_BUNDLE_FIELD_ORDER: tuple[str, ...] = (
    "product",
    "text",
    "lexical",
    "semantic",
    "filtering",
)


class ProductRepresentationBundle(BaseModel):
    """Typed grouping of all product-side representations for one canonical record."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product: ProductRepresentation
    text: str
    lexical: str
    semantic: str
    filtering: FilteringRepresentation


def build_product_representation_bundle(
    record: Mapping[str, Any],
) -> ProductRepresentationBundle:
    """Build all product-side representations from one Phase 2 canonical catalog record."""
    product = build_product_representation(record)
    return ProductRepresentationBundle(
        product=product,
        text=build_product_text(product),
        lexical=build_lexical_text_from_canonical(product, record),
        semantic=build_semantic_text_from_canonical(product, record),
        filtering=build_filtering_representation_from_canonical(record),
    )


def product_representation_bundle_to_dict(
    bundle: ProductRepresentationBundle,
) -> dict[str, Any]:
    """Deterministic JSON-compatible bundle view using existing representation serializers."""
    payload = {
        "product": representation_to_dict(bundle.product),
        "text": bundle.text,
        "lexical": bundle.lexical,
        "semantic": bundle.semantic,
        "filtering": filtering_representation_to_dict(bundle.filtering),
    }
    return {key: payload[key] for key in PRODUCT_REPRESENTATION_BUNDLE_FIELD_ORDER}


class ProductRepresentationPipeline:
    """Stateless orchestrator; delegates construction to existing representation builders."""

    @staticmethod
    def build(record: Mapping[str, Any]) -> ProductRepresentationBundle:
        return build_product_representation_bundle(record)


__all__ = [
    "PRODUCT_REPRESENTATION_BUNDLE_FIELD_ORDER",
    "ProductRepresentationBundle",
    "ProductRepresentationPipeline",
    "build_product_representation_bundle",
    "product_representation_bundle_to_dict",
]
