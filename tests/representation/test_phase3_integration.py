"""Phase 3.12 cross-layer integration tests for the representation foundation."""

from __future__ import annotations

import copy
import os
from pathlib import Path
from typing import Any

import pandas as pd
import pytest

from data.export import PROCESSED_COLUMN_ORDER, ProcessedDatasetWriter
from productiq.representation.builder import build_product_representation
from productiq.representation.dataset import (
    bundle_to_dataset_row,
    generate_representation_dataset,
    load_representation_dataset_manifest,
    validate_representation_dataset,
)
from productiq.representation.dataset_schema import (
    REPRESENTATION_DATASET_COLUMN_ORDER,
    REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS,
)
from productiq.representation.filtering import build_filtering_representation_from_canonical
from productiq.representation.lexical import build_lexical_text_from_canonical
from productiq.representation.pipeline import build_product_representation_bundle
from productiq.representation.semantic import build_semantic_text_from_canonical
from productiq.representation.text import build_product_text
from tests.database.catalog_fixtures import make_product_record


def _records_to_processed_dataframe(records: list[dict[str, object]]) -> pd.DataFrame:
    dataframe = pd.DataFrame(records)
    for column in ("discount_price_inr", "original_price_inr"):
        dataframe[column] = dataframe[column].astype("Int64")
    for column in ("color_is_coded", "price_anomaly"):
        dataframe[column] = dataframe[column].astype("boolean")
    for column in PROCESSED_COLUMN_ORDER:
        if column not in ("discount_price_inr", "original_price_inr", "color_is_coded", "price_anomaly"):
            dataframe[column] = dataframe[column].astype("string")
    return dataframe.loc[:, list(PROCESSED_COLUMN_ORDER)]


def _write_canonical_parquet(records: list[dict[str, object]], path: Path) -> None:
    ProcessedDatasetWriter().write(_records_to_processed_dataframe(records), path)


def _series_to_logical_row(series: pd.Series) -> dict[str, Any]:
    row: dict[str, Any] = {}
    for column in REPRESENTATION_DATASET_COLUMN_ORDER:
        value = series[column]
        if pd.isna(value):
            row[column] = None
        elif column in ("discount_price_inr", "original_price_inr"):
            row[column] = int(value)
        elif column in ("color_is_coded", "price_anomaly"):
            row[column] = bool(value)
        else:
            row[column] = str(value)
    return row


def _assert_bundle_matches_builders(record: dict[str, Any]) -> None:
    bundle = build_product_representation_bundle(record)
    product = build_product_representation(record)
    assert bundle.product.model_dump() == product.model_dump()
    assert bundle.text == build_product_text(product)
    assert bundle.lexical == build_lexical_text_from_canonical(product, record)
    assert bundle.semantic == build_semantic_text_from_canonical(product, record)
    assert bundle.filtering.model_dump() == build_filtering_representation_from_canonical(record).model_dump()
    assert bundle.product.product_id == bundle.filtering.product_id
    assert bundle.product.brand == bundle.filtering.brand
    assert bundle.product.category_gender == bundle.filtering.category_gender
    assert bundle.product.product_type == bundle.filtering.product_type
    assert bundle.product.color == bundle.filtering.color
    assert bundle.product.material == bundle.filtering.material


def test_cross_layer_pipeline_coherence() -> None:
    record = make_product_record(
        material="cotton|linen",
        product_features="patch_pocket|pocket",
        description="Summer linen shirt",
    )
    _assert_bundle_matches_builders(record)


def test_canonical_record_not_mutated_through_pipeline() -> None:
    record = make_product_record(description="Keep me")
    before = copy.deepcopy(record)
    build_product_representation_bundle(record)
    assert record == before


def test_dataset_row_matches_bundle_materialization(tmp_path: Path) -> None:
    records = [
        make_product_record(product_id="111", material="cotton|linen", description="A"),
        make_product_record(
            product_id="222",
            product_type=None,
            material=None,
            description=None,
        ),
    ]
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    _write_canonical_parquet(records, source)
    generate_representation_dataset(source, output, validate_canonical_input=False)

    frame = pd.read_parquet(output)
    for record in records:
        expected = bundle_to_dataset_row(build_product_representation_bundle(record))
        actual = _series_to_logical_row(frame.loc[frame["product_id"] == record["product_id"]].iloc[0])
        assert actual == expected


def test_edge_case_rich_product() -> None:
    record = make_product_record(
        material="cotton|linen",
        pattern="striped",
        fit="slim_fit",
        sleeve="full",
        neckline="collared",
        product_features="patch_pocket|pocket",
        style_attributes="mid_rise",
        description="Rich attribute shirt",
    )
    _assert_bundle_matches_builders(record)


def test_edge_case_sparse_product() -> None:
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
    bundle = build_product_representation_bundle(record)
    assert bundle.product.material is None
    assert bundle.product.pattern is None
    _assert_bundle_matches_builders(record)


def test_edge_case_multivalue_fields() -> None:
    record = make_product_record(
        material="cotton|polyester",
        product_features="a|b|c",
    )
    bundle = build_product_representation_bundle(record)
    assert bundle.product.material == ["cotton", "polyester"]
    assert bundle.filtering.material == ["cotton", "polyester"]
    for column in REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS:
        if getattr(bundle.product, column) is not None:
            assert getattr(bundle.filtering, column) == getattr(bundle.product, column)


def test_edge_case_coded_color() -> None:
    record = make_product_record(
        color_raw="#AABBCC",
        color_is_coded=True,
        color_normalized=None,
    )
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.color_is_coded is True
    assert bundle.filtering.color_raw == "#AABBCC"
    assert bundle.product.color is None


def test_edge_case_price_anomaly() -> None:
    record = make_product_record(
        discount_price_inr=2500,
        original_price_inr=1200,
        price_anomaly=True,
    )
    bundle = build_product_representation_bundle(record)
    assert bundle.filtering.price_anomaly is True
    assert bundle.filtering.discount_price_inr == 2500
    assert bundle.filtering.original_price_inr == 1200


def test_edge_case_missing_description() -> None:
    record = make_product_record(description=None)
    bundle = build_product_representation_bundle(record)
    assert bundle.lexical
    assert bundle.semantic
    assert "Description:" not in bundle.semantic


def test_edge_case_whitespace_description_normalized() -> None:
    record = make_product_record(description="  Soft   cotton   shirt  ")
    first = build_product_representation_bundle(record)
    second = build_product_representation_bundle(record)
    assert first.lexical == second.lexical
    assert first.semantic == second.semantic
    assert "Soft cotton shirt" in first.lexical


def test_integration_determinism() -> None:
    record = make_product_record(description="Deterministic integration")
    first = build_product_representation_bundle(record)
    second = build_product_representation_bundle(record)
    assert first.model_dump() == second.model_dump()


def test_production_artifact_matches_pipeline_sample() -> None:
    artifact_path = Path(__file__).resolve().parents[2].joinpath(
        "resources", "processed", "product_representations.parquet"
    )
    if not artifact_path.is_file():
        pytest.skip("full representation dataset artifact not generated")
    root = Path(__file__).resolve().parents[2]
    catalog_path = root / "resources" / "processed" / "product_catalog.parquet"
    artifact_path = root / "resources" / "processed" / "product_representations.parquet"
    sample = pd.read_parquet(catalog_path).head(3).to_dict(orient="records")
    frame = pd.read_parquet(artifact_path)
    for record in sample:
        product_id = str(record["product_id"])
        expected = bundle_to_dataset_row(build_product_representation_bundle(record))
        actual = _series_to_logical_row(frame.loc[frame["product_id"] == product_id].iloc[0])
        assert actual == expected


@pytest.mark.skipif(
    os.environ.get("PRODUCTIQ_GENERATE_FULL_DATASET") != "1",
    reason="set PRODUCTIQ_GENERATE_FULL_DATASET=1 to materialize full catalog artifact",
)
def test_generate_full_catalog_representation_artifact() -> None:
    root = Path(__file__).resolve().parents[2]
    source = root / "resources" / "processed" / "product_catalog.parquet"
    output = root / "resources" / "processed" / "product_representations.parquet"
    manifest = root / "resources" / "processed" / "product_representations.manifest.json"
    if not source.is_file():
        pytest.skip("canonical product_catalog.parquet not available")

    expected_rows = 367_172
    result = generate_representation_dataset(
        source,
        output,
        manifest_path=manifest,
        batch_size=10_000,
        validate_canonical_input=True,
        expected_source_row_count=expected_rows,
    )
    validation = validate_representation_dataset(output, expected_row_count=expected_rows)
    assert validation.product_id_unique
    assert result.report.output_row_count == expected_rows
    assert result.report.column_count == len(REPRESENTATION_DATASET_COLUMN_ORDER)
    payload = load_representation_dataset_manifest(manifest)
    assert payload["row_count"] == expected_rows
    assert payload["checksum"] == result.report.checksum
