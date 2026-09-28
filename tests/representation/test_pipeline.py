"""Tests for Phase 3.9 representation generation pipeline."""

from __future__ import annotations

import copy
import inspect

import pytest

from productiq.exceptions.base import ProductRepresentationError
from productiq.representation import build_lexical_text_from_canonical, build_product_text
from productiq.representation.builder import build_product_representation
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.pipeline import (
    ProductRepresentationBundle,
    ProductRepresentationPipeline,
    build_product_representation_bundle,
    product_representation_bundle_to_dict,
)
from productiq.representation.schema import ProductRepresentation
from tests.database.catalog_fixtures import make_product_record


def test_complete_canonical_record_produces_complete_bundle() -> None:
    record = make_product_record(
        material="cotton|linen",
        description="Lightweight summer shirt",
    )
    bundle = build_product_representation_bundle(record)
    assert isinstance(bundle, ProductRepresentationBundle)
    assert bundle.product.product_id == record["product_id"]
    assert bundle.text
    assert bundle.lexical
    assert bundle.semantic
    assert isinstance(bundle.filtering, FilteringRepresentation)


def test_product_field_matches_standalone_builder() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record)
    expected = build_product_representation(record)
    assert bundle.product.model_dump() == expected.model_dump()


def test_product_text_matches_standalone_builder() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record)
    assert bundle.text == build_product_text(bundle.product)


def test_lexical_includes_canonical_description() -> None:
    description = "Unique lexical description token xyz"
    record = make_product_record(description=description)
    bundle = build_product_representation_bundle(record)
    assert description in bundle.lexical
    assert bundle.lexical == build_lexical_text_from_canonical(bundle.product, record)


def test_semantic_includes_canonical_description() -> None:
    description = "Unique semantic description token abc"
    record = make_product_record(description=description)
    bundle = build_product_representation_bundle(record)
    assert f"Description: {description}" in bundle.semantic


def test_filtering_carries_commercial_and_provenance_metadata() -> None:
    record = make_product_record(
        source="myntra",
        color_raw="navy",
        color_is_coded=False,
        discount_price_inr=1200,
        original_price_inr=2400,
        price_anomaly=True,
    )
    bundle = build_product_representation_bundle(record)
    filtering = bundle.filtering
    assert filtering.source == "myntra"
    assert filtering.color_raw == "navy"
    assert filtering.color_is_coded is False
    assert filtering.discount_price_inr == 1200
    assert filtering.original_price_inr == 2400
    assert filtering.price_anomaly is True


def test_missing_optional_product_attributes_remain_none() -> None:
    record = make_product_record(
        material=None,
        style_attributes=None,
        sleeve=None,
        neckline=None,
    )
    bundle = build_product_representation_bundle(record)
    assert bundle.product.material is None
    assert bundle.product.style_attributes is None
    assert bundle.product.sleeve is None
    assert bundle.product.neckline is None


def test_multivalue_attributes_preserve_pipe_semantics() -> None:
    record = make_product_record(product_features="patch_pocket|pocket")
    bundle = build_product_representation_bundle(record)
    assert bundle.product.product_features == ["patch_pocket", "pocket"]
    assert bundle.filtering.product_features == ["patch_pocket", "pocket"]


def test_price_anomaly_preserved_not_repaired() -> None:
    record = make_product_record(price_anomaly=True, discount_price_inr=1, original_price_inr=9999)
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.price_anomaly is True
    assert bundle.filtering.discount_price_inr == 1


def test_coded_color_remains_coded() -> None:
    record = make_product_record(color_raw="#1A2B3C", color_is_coded=True, color_normalized=None)
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.color_is_coded is True
    assert bundle.filtering.color_raw == "#1A2B3C"
    assert bundle.product.color is None


def test_canonical_record_not_mutated() -> None:
    record = make_product_record()
    before = copy.deepcopy(record)
    build_product_representation_bundle(record)
    assert record == before


def test_repeated_generation_is_deterministic() -> None:
    record = make_product_record(description="Deterministic check")
    first = build_product_representation_bundle(record)
    second = build_product_representation_bundle(record)
    assert first.model_dump() == second.model_dump()
    assert product_representation_bundle_to_dict(first) == product_representation_bundle_to_dict(
        second
    )


def test_invalid_canonical_input_raises_product_representation_error() -> None:
    record = make_product_record(category_gender="Kids")
    with pytest.raises(ProductRepresentationError):
        build_product_representation_bundle(record)


def test_pipeline_class_delegates_to_bundle_builder() -> None:
    record = make_product_record()
    assert ProductRepresentationPipeline.build(record).model_dump() == build_product_representation_bundle(
        record
    ).model_dump()


def test_bundle_fields_use_concrete_types() -> None:
    bundle = build_product_representation_bundle(make_product_record())
    assert isinstance(bundle.product, ProductRepresentation)
    assert isinstance(bundle.text, str)
    assert isinstance(bundle.lexical, str)
    assert isinstance(bundle.semantic, str)
    assert isinstance(bundle.filtering, FilteringRepresentation)


def test_bundle_serializer_uses_existing_helpers() -> None:
    bundle = build_product_representation_bundle(make_product_record())
    data = product_representation_bundle_to_dict(bundle)
    assert set(data) == {"product", "text", "lexical", "semantic", "filtering"}
    assert data["product"]["product_id"] == bundle.product.product_id
    assert data["filtering"]["source"] == bundle.filtering.source


def test_pipeline_module_has_no_retrieval_or_inference_surface() -> None:
    from productiq.representation import pipeline as pipeline_module

    source = inspect.getsource(pipeline_module)
    forbidden = (
        "bm25",
        "embedding",
        "openai",
        "postgres",
        "sqlalchemy",
        "redis",
        "rank",
        "recommend",
        "llm",
    )
    lowered = source.lower()
    for token in forbidden:
        assert token not in lowered
