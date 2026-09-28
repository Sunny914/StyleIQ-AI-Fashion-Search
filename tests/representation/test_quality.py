"""Tests for Phase 3.10 representation quality validation."""

from __future__ import annotations

import inspect

from productiq.representation.pipeline import build_product_representation_bundle
from productiq.representation.quality import (
    summarize_representation_quality_reports,
    validate_canonical_record_representation_quality,
    validate_canonical_records_representation_quality,
    validate_product_representation_bundle,
)
from productiq.representation.schema import ProductRepresentation
from tests.database.catalog_fixtures import make_product_record


def test_valid_complete_bundle_passes() -> None:
    record = make_product_record(material="cotton", description="Summer shirt")
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    assert report.issue_count == 0


def test_minimal_valid_bundle_passes() -> None:
    record = make_product_record(
        brand=None,
        brand_normalized=None,
        product_type=None,
        pattern=None,
        material=None,
        fit=None,
        sleeve=None,
        neckline=None,
        product_features=None,
        style_attributes=None,
        description=None,
    )
    report = validate_canonical_record_representation_quality(record)
    assert report.valid


def test_empty_text_detected() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record).model_copy(update={"text": ""})
    report = validate_product_representation_bundle(bundle, record=record)
    assert not report.valid
    assert any(issue.code == "empty_representation_text" for issue in report.issues)


def test_whitespace_only_text_detected() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record).model_copy(update={"lexical": "   "})
    report = validate_product_representation_bundle(bundle, record=record)
    assert not report.valid
    assert any(issue.field == "lexical" for issue in report.issues)


def test_missing_optional_fields_not_reported() -> None:
    record = make_product_record(material=None, style_attributes=None)
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    assert report.preservation_issue_count == 0


def test_multivalue_none_semantics_accepted() -> None:
    record = make_product_record(material=None, pattern=None)
    bundle = build_product_representation_bundle(record)
    assert bundle.product.material is None
    report = validate_product_representation_bundle(bundle, record=record)
    assert report.valid


def test_empty_multivalue_token_detected() -> None:
    record = make_product_record()
    product = ProductRepresentation.model_construct(
        product_id=record["product_id"],
        category_gender="Men",
        color=[""],
    )
    bundle = build_product_representation_bundle(record).model_copy(update={"product": product})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "empty_multivalue_token" for issue in report.issues)


def test_product_filtering_multivalue_consistency() -> None:
    record = make_product_record(material="cotton|linen")
    filtering = build_product_representation_bundle(record).filtering.model_copy(
        update={"material": ["cotton"]}
    )
    bundle = build_product_representation_bundle(record).model_copy(update={"filtering": filtering})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "multivalue_facet_mismatch" for issue in report.issues)


def test_brand_consistency_and_preservation() -> None:
    record = make_product_record(brand="nike", brand_normalized="nike")
    bundle = build_product_representation_bundle(record).model_copy(
        update={"text": "Category: Men."}
    )
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "brand_not_preserved" for issue in report.issues)


def test_category_consistency() -> None:
    record = make_product_record(category_gender="Men")
    bundle = build_product_representation_bundle(record)
    assert "Men" in bundle.text
    report = validate_product_representation_bundle(bundle, record=record)
    assert report.valid


def test_product_type_preservation() -> None:
    record = make_product_record(product_type="shirt")
    bundle = build_product_representation_bundle(record).model_copy(update={"lexical": "Men"})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "product_type_not_preserved" for issue in report.issues)


def test_color_consistency() -> None:
    record = make_product_record(color_normalized="navy_blue")
    bundle = build_product_representation_bundle(record)
    assert bundle.product.color == bundle.filtering.color
    report = validate_product_representation_bundle(bundle, record=record)
    assert report.valid


def test_coded_color_preserved_not_decoded() -> None:
    record = make_product_record(
        color_raw="#AABBCC",
        color_is_coded=True,
        color_normalized=None,
    )
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.color_is_coded is True
    assert bundle.product.color is None


def test_description_in_lexical_when_present() -> None:
    record = make_product_record(description="Unique desc token 123")
    bundle = build_product_representation_bundle(record).model_copy(update={"lexical": "Men"})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "description_missing_lexical" for issue in report.issues)


def test_description_in_semantic_when_present() -> None:
    record = make_product_record(description="Unique desc token 456")
    bundle = build_product_representation_bundle(record).model_copy(update={"semantic": "Category: Men."})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "description_missing_semantic" for issue in report.issues)


def test_missing_description_accepted() -> None:
    record = make_product_record(description=None)
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    assert report.description_issue_count == 0


def test_prices_consistent_with_canonical() -> None:
    record = make_product_record(discount_price_inr=500, original_price_inr=999)
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    assert report.price_issue_count == 0


def test_price_anomaly_preserved() -> None:
    record = make_product_record(
        discount_price_inr=2000,
        original_price_inr=1000,
        price_anomaly=True,
    )
    report = validate_canonical_record_representation_quality(record)
    assert report.valid
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.price_anomaly is True


def test_product_id_not_required_in_lexical_semantic() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record)
    assert record["product_id"] not in bundle.lexical
    report = validate_product_representation_bundle(bundle, record=record)
    assert report.valid


def test_source_not_required_in_lexical_semantic() -> None:
    record = make_product_record(source="ajio")
    bundle = build_product_representation_bundle(record)
    report = validate_product_representation_bundle(bundle, record=record)
    assert report.valid


def test_deterministic_validation() -> None:
    record = make_product_record(description="Stable")
    first = validate_canonical_record_representation_quality(record)
    second = validate_canonical_record_representation_quality(record)
    assert first.model_dump() == second.model_dump()


def test_repeated_pipeline_generation_deterministic() -> None:
    record = make_product_record()
    first = build_product_representation_bundle(record)
    second = build_product_representation_bundle(record)
    assert first.model_dump() == second.model_dump()
    assert validate_product_representation_bundle(first, record=record).valid


def test_degenerate_duplicate_labels() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record).model_copy(
        update={"semantic": "Brand: Puma. Brand: Puma."}
    )
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "duplicate_field_labels" for issue in report.issues)


def test_dataset_level_coverage_summary() -> None:
    records = [
        make_product_record(product_type="shirt", description="A"),
        make_product_record(product_type=None, description=None, material="cotton"),
    ]
    catalog = validate_canonical_records_representation_quality(records)
    assert catalog.total_records == 2
    assert catalog.valid_records == 2
    assert 0.0 <= catalog.field_coverage["product_type"] <= 1.0
    assert catalog.field_coverage["product_type"] == 0.5
    assert catalog.representation_coverage["text"] == 1.0


def test_catalog_batch_matches_summarize_semantics() -> None:
    records = [
        make_product_record(product_type="shirt", description="A"),
        make_product_record(product_type=None, material="cotton"),
    ]
    catalog = validate_canonical_records_representation_quality(records)
    reports: list = []
    bundles: list = []
    for record in records:
        bundle = build_product_representation_bundle(record)
        bundles.append(bundle)
        reports.append(validate_product_representation_bundle(bundle, record=record))
    expected = summarize_representation_quality_reports(reports, bundles=bundles)
    assert catalog.model_dump() == expected.model_dump()


def test_catalog_batch_accepts_record_iterator() -> None:
    def record_stream():
        yield make_product_record(product_id="111")
        yield make_product_record(product_id="222")

    catalog = validate_canonical_records_representation_quality(record_stream())
    assert catalog.total_records == 2
    assert catalog.valid_records == 2


def test_catalog_batch_does_not_retain_all_bundles_in_implementation() -> None:
    import productiq.representation.quality as quality_module

    source = inspect.getsource(quality_module.validate_canonical_records_representation_quality)
    assert "reports = []" not in source
    assert "bundles = []" not in source
    assert "reports.append" not in source
    assert "bundles.append" not in source


def test_quality_module_has_no_retrieval_dependencies() -> None:
    from productiq.representation import quality as quality_module

    source = inspect.getsource(quality_module).lower()
    for token in ("bm25", "embedding", "openai", "postgres", "sqlalchemy", "rank", "recommend", "llm", "ndcg", "mrr"):
        assert token not in source


def test_orchestration_mismatch_detected() -> None:
    record = make_product_record()
    bundle = build_product_representation_bundle(record).model_copy(update={"text": "not matching"})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "text_builder_mismatch" for issue in report.issues)


def test_filtering_scalar_mismatch_detected() -> None:
    record = make_product_record(category_gender="Men")
    filtering = build_product_representation_bundle(record).filtering.model_copy(
        update={"category_gender": "Women"}
    )
    bundle = build_product_representation_bundle(record).model_copy(update={"filtering": filtering})
    report = validate_product_representation_bundle(bundle, record=record)
    assert any(issue.code == "scalar_facet_mismatch" for issue in report.issues)
