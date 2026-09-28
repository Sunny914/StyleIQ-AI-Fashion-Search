"""Tests for Phase 3.11 representation dataset generation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from data.export import PROCESSED_COLUMN_ORDER, ProcessedDatasetWriter
from productiq.exceptions.base import RepresentationDatasetError
from productiq.representation.dataset import (
    _move_aside_if_exists,
    _publish_prepared_artifacts,
    bundle_to_dataset_row,
    generate_representation_dataset,
    load_representation_dataset_manifest,
    validate_representation_dataset,
)
from productiq.representation.dataset_schema import REPRESENTATION_DATASET_COLUMN_ORDER
from productiq.representation.pipeline import build_product_representation_bundle
from tests.database.catalog_fixtures import make_product_record, make_product_records


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


def test_generate_dataset_from_fixture(tmp_path: Path) -> None:
    records = make_product_records(3)
    records[1]["material"] = "cotton|linen"
    records[2]["description"] = None
    source = tmp_path / "product_catalog.parquet"
    output = tmp_path / "product_representations.parquet"
    _write_canonical_parquet(records, source)

    result = generate_representation_dataset(
        source,
        output,
        batch_size=2,
        validate_canonical_input=True,
        expected_source_row_count=3,
    )

    assert output.is_file()
    assert result.report.output_row_count == 3
    validation = validate_representation_dataset(output, expected_row_count=3)
    assert validation.product_id_unique
    assert validation.column_count == len(REPRESENTATION_DATASET_COLUMN_ORDER)
    assert list(pd.read_parquet(output).columns) == list(REPRESENTATION_DATASET_COLUMN_ORDER)


def test_expected_representation_values_materialized(tmp_path: Path) -> None:
    record = make_product_record(
        product_id="999",
        material="cotton|linen",
        description="Soft shirt",
    )
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    _write_canonical_parquet([record], source)

    generate_representation_dataset(source, output, validate_canonical_input=False)
    row = pd.read_parquet(output).iloc[0]
    bundle = build_product_representation_bundle(record)

    assert row["product_id"] == "999"
    assert row["material"] == "cotton|linen"
    assert row["product_text"] == bundle.text
    assert row["lexical_text"] == bundle.lexical
    assert row["semantic_text"] == bundle.semantic
    assert row["source"] == record["source"]


def test_missing_optional_fields_do_not_use_placeholders(tmp_path: Path) -> None:
    record = make_product_record(
        material=None,
        style_attributes=None,
        description=None,
        sleeve=None,
    )
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    _write_canonical_parquet([record], source)
    generate_representation_dataset(source, output, validate_canonical_input=False)

    row = pd.read_parquet(output).iloc[0]
    assert pd.isna(row["material"])
    assert pd.isna(row["style_attributes"])
    assert pd.isna(row["sleeve"])


def test_deterministic_generation(tmp_path: Path) -> None:
    records = make_product_records(2)
    source = tmp_path / "catalog.parquet"
    _write_canonical_parquet(records, source)
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"

    generate_representation_dataset(source, first_path, validate_canonical_input=False)
    generate_representation_dataset(source, second_path, validate_canonical_input=False)

    first = pd.read_parquet(first_path)
    second = pd.read_parquet(second_path)
    pd.testing.assert_frame_equal(first, second)


def test_idempotent_regeneration_replaces_dataset(tmp_path: Path) -> None:
    records = make_product_records(2)
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    _write_canonical_parquet(records, source)

    generate_representation_dataset(source, output, validate_canonical_input=False)
    generate_representation_dataset(source, output, validate_canonical_input=False)

    frame = pd.read_parquet(output)
    assert len(frame) == 2
    assert frame["product_id"].is_unique


def test_batch_size_one_matches_default_batch(tmp_path: Path) -> None:
    records = make_product_records(3)
    source = tmp_path / "catalog.parquet"
    _write_canonical_parquet(records, source)
    batched = tmp_path / "batched.parquet"
    single = tmp_path / "single.parquet"

    generate_representation_dataset(source, batched, batch_size=1, validate_canonical_input=False)
    generate_representation_dataset(source, single, batch_size=3, validate_canonical_input=False)

    pd.testing.assert_frame_equal(pd.read_parquet(batched), pd.read_parquet(single))


def test_manifest_written_with_checksum(tmp_path: Path) -> None:
    records = make_product_records(1)
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    manifest = tmp_path / "representations.manifest.json"
    _write_canonical_parquet(records, source)

    result = generate_representation_dataset(
        source,
        output,
        manifest_path=manifest,
        validate_canonical_input=False,
    )

    payload = load_representation_dataset_manifest(manifest)
    assert payload["row_count"] == 1
    assert payload["checksum"] == result.report.checksum
    assert payload["schema_version"] == "1.0.0"
    assert payload["source_row_count"] == 1


def test_failed_generation_does_not_publish_output(tmp_path: Path) -> None:
    records = make_product_records(2)
    source = tmp_path / "catalog.parquet"
    output = tmp_path / "representations.parquet"
    _write_canonical_parquet(records, source)
    original = build_product_representation_bundle
    call_count = 0

    def flaky_build(record: dict[str, object]):
        nonlocal call_count
        call_count += 1
        if call_count == 2:
            raise RepresentationDatasetError("boom")
        return original(record)

    with (
        patch(
            "productiq.representation.dataset.build_product_representation_bundle",
            side_effect=flaky_build,
        ),
        pytest.raises(RepresentationDatasetError),
    ):
        generate_representation_dataset(source, output, validate_canonical_input=False)

    assert not output.exists()


def test_publish_restores_parquet_when_manifest_backup_fails(tmp_path: Path) -> None:
    final_parquet = tmp_path / "representations.parquet"
    final_manifest = tmp_path / "representations.manifest.json"
    parquet_bytes = b"published-parquet-bytes"
    manifest_bytes = b'{"published": true}\n'
    final_parquet.write_bytes(parquet_bytes)
    final_manifest.write_bytes(manifest_bytes)

    temp_parquet = tmp_path / "temp.parquet"
    temp_manifest = tmp_path / "temp.manifest.json"
    temp_parquet.write_bytes(b"new-parquet")
    temp_manifest.write_bytes(b'{"new": true}\n')

    original_move = _move_aside_if_exists
    move_calls = 0

    def flaky_move_aside(path: Path) -> Path | None:
        nonlocal move_calls
        move_calls += 1
        if move_calls == 2:
            raise OSError("manifest backup failed")
        return original_move(path)

    with (
        patch(
            "productiq.representation.dataset._move_aside_if_exists",
            side_effect=flaky_move_aside,
        ),
        pytest.raises(OSError, match="manifest backup failed"),
    ):
        _publish_prepared_artifacts(
            temp_parquet_path=temp_parquet,
            temp_manifest_path=temp_manifest,
            final_parquet_path=final_parquet,
            final_manifest_path=final_manifest,
        )

    assert final_parquet.read_bytes() == parquet_bytes
    assert final_manifest.read_bytes() == manifest_bytes
    assert temp_parquet.exists()
    assert temp_manifest.exists()


def test_bundle_row_serialization_multivalue() -> None:
    record = make_product_record(product_features="patch_pocket|pocket")
    bundle = build_product_representation_bundle(record)
    row = bundle_to_dataset_row(bundle)
    assert row["product_features"] == "patch_pocket|pocket"
