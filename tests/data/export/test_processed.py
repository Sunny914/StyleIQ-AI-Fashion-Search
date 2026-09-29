"""Tests for processed ProductIQ dataset export."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from pathlib import Path

import pandas as pd
import pytest

from data.attributes import ProductAttributeExtractor
from data.catalog.schema import CANONICAL_COLUMN_ORDER
from data.export import (
    AJIO_PROCESSED_ROW_COUNT,
    PROCESSED_COLUMN_COUNT,
    PROCESSED_COLUMN_ORDER,
    PROCESSED_DATASET_SCHEMA_VERSION,
    ProcessedDatasetWriter,
)
from productiq.exceptions import DataExportError, ProductIQError


def make_canonical_row(**overrides: object) -> dict[str, object]:
    row: dict[str, object] = {
        "product_id": "123456789001",
        "product_url": "https://example.com/a",
        "brand": "puma",
        "brand_normalized": "puma",
        "description": "Striped Slim Fit Shirt with Patch Pocket",
        "image_url": "https://example.com/img",
        "category_gender": "Men",
        "color_raw": "blue",
        "color_normalized": "blue",
        "color_is_coded": False,
        "discount_price_inr": 559,
        "original_price_inr": 999,
        "price_anomaly": False,
        "source": "ajio",
    }
    row.update(overrides)
    return row


def make_canonical_dataframe(rows: list[dict[str, object]] | None = None) -> pd.DataFrame:
    if rows is None:
        rows = [{}]
    dataframe = pd.DataFrame([make_canonical_row(**row) for row in rows])
    for column in ("discount_price_inr", "original_price_inr"):
        dataframe[column] = dataframe[column].astype("Int64")
    for column in ("color_is_coded", "price_anomaly"):
        dataframe[column] = dataframe[column].astype("boolean")
    for column in CANONICAL_COLUMN_ORDER:
        if column not in ("discount_price_inr", "original_price_inr", "color_is_coded", "price_anomaly"):
            dataframe[column] = dataframe[column].astype("string")
    return dataframe


@pytest.fixture
def writer() -> ProcessedDatasetWriter:
    return ProcessedDatasetWriter()


@pytest.fixture
def processed_dataframe() -> pd.DataFrame:
    canonical = make_canonical_dataframe()
    return ProductAttributeExtractor().extract(canonical).dataframe


def test_valid_dataframe_writes_successfully(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)

    assert result.report.validation_passed
    assert output_path.is_file()


def test_output_file_exists(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    assert output_path.exists()


def test_output_is_readable_as_parquet(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert len(loaded) == len(processed_dataframe)


def test_row_count_is_preserved(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)

    assert result.report.input_row_count == len(processed_dataframe)
    assert result.report.output_row_count == len(processed_dataframe)


def test_column_count_is_preserved(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)

    assert result.report.column_count == PROCESSED_COLUMN_COUNT


def test_column_order_is_preserved(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert list(loaded.columns) == list(PROCESSED_COLUMN_ORDER)


def test_product_id_remains_unique(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert loaded["product_id"].is_unique


def test_source_remains_ajio(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert loaded["source"].eq("ajio").all()


def test_key_values_survive_round_trip(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    for column in CANONICAL_COLUMN_ORDER:
        pd.testing.assert_series_equal(
            loaded[column],
            processed_dataframe[column],
            check_names=True,
        )


def test_attribute_values_survive_round_trip(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert loaded.iloc[0]["product_type"] == "shirt"
    assert loaded.iloc[0]["fit"] == "slim_fit"


def test_nullable_price_fields_survive_round_trip(
    writer: ProcessedDatasetWriter,
    tmp_path: Path,
) -> None:
    dataframe = ProductAttributeExtractor().extract(
        make_canonical_dataframe([{"discount_price_inr": pd.NA, "original_price_inr": pd.NA}])
    ).dataframe
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert pd.isna(loaded.iloc[0]["discount_price_inr"])
    assert pd.isna(loaded.iloc[0]["original_price_inr"])


def test_boolean_fields_survive_round_trip(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    assert bool(loaded.iloc[0]["color_is_coded"]) is False
    assert bool(loaded.iloc[0]["price_anomaly"]) is False


def test_invalid_input_type_fails(writer: ProcessedDatasetWriter, tmp_path: Path) -> None:
    with pytest.raises(DataExportError, match="pandas DataFrame"):
        writer.write(["invalid"], tmp_path / "product_catalog.parquet")  # type: ignore[arg-type]


def test_missing_columns_fail(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    invalid = processed_dataframe.drop(columns=["product_type"])
    with pytest.raises(DataExportError, match="missing="):
        writer.write(invalid, tmp_path / "product_catalog.parquet")


def test_unexpected_columns_fail(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    invalid = processed_dataframe.copy()
    invalid["extra"] = "value"
    with pytest.raises(DataExportError, match="unexpected="):
        writer.write(invalid, tmp_path / "product_catalog.parquet")


def test_duplicate_product_id_fails(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    invalid = pd.concat([processed_dataframe, processed_dataframe], ignore_index=True)
    with pytest.raises(DataExportError, match="product_id must be unique"):
        writer.write(invalid, tmp_path / "product_catalog.parquet")


def test_invalid_source_fails(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    invalid = processed_dataframe.copy()
    invalid["source"] = "other"
    with pytest.raises(DataExportError, match='source must be "ajio"'):
        writer.write(invalid, tmp_path / "product_catalog.parquet")


def test_row_count_contract_violation_fails(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    with pytest.raises(DataExportError, match="row count contract violation"):
        writer.write(
            processed_dataframe,
            tmp_path / "product_catalog.parquet",
            expected_row_count=AJIO_PROCESSED_ROW_COUNT,
        )


def test_checksum_is_generated(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    result = writer.write(processed_dataframe, tmp_path / "product_catalog.parquet")

    assert len(result.report.checksum) == 64


def test_checksum_matches_output_file_bytes(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)

    assert result.report.checksum == writer.checksum_file(output_path)


def test_manifest_is_valid_json(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)

    payload = json.loads(result.manifest_path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)


def test_manifest_metadata_matches_generated_artifact(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(processed_dataframe, output_path)
    payload = writer.load_manifest(result.manifest_path)

    assert payload["dataset_name"] == "product_catalog"
    assert payload["schema_version"] == PROCESSED_DATASET_SCHEMA_VERSION
    assert payload["source"] == "ajio"
    assert payload["format"] == "parquet"
    assert payload["output_filename"] == output_path.name
    assert payload["row_count"] == len(processed_dataframe)
    assert payload["column_count"] == PROCESSED_COLUMN_COUNT
    assert payload["columns"] == list(PROCESSED_COLUMN_ORDER)
    assert payload["checksum_algorithm"] == "sha256"
    assert payload["checksum"] == writer.checksum_file(output_path)
    assert payload["pipeline_phase"] == "2.9"


def test_rerun_produces_semantically_identical_dataset(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    first_path = tmp_path / "first.parquet"
    second_path = tmp_path / "second.parquet"
    writer.write(processed_dataframe, first_path)
    writer.write(processed_dataframe, second_path)

    first = pd.read_parquet(first_path)
    second = pd.read_parquet(second_path)
    pd.testing.assert_frame_equal(first, second, check_dtype=False)


def test_failed_writes_do_not_corrupt_final_artifact(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    manifest_path = tmp_path / "product_catalog.manifest.json"
    writer.write(processed_dataframe, output_path, manifest_path=manifest_path)
    original_checksum = writer.checksum_file(output_path)
    original_manifest = manifest_path.read_text(encoding="utf-8")

    invalid = processed_dataframe.copy()
    invalid["source"] = "broken"
    with pytest.raises(DataExportError):
        writer.write(invalid, output_path, manifest_path=manifest_path)

    assert writer.checksum_file(output_path) == original_checksum
    assert manifest_path.read_text(encoding="utf-8") == original_manifest


def test_successful_write_produces_valid_parquet_and_manifest_pair(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    manifest_path = tmp_path / "product_catalog.manifest.json"
    result = writer.write(processed_dataframe, output_path, manifest_path=manifest_path)

    assert output_path.is_file()
    assert manifest_path.is_file()
    assert result.report.validation_passed
    assert writer.validate(output_path).validation_passed


def test_manifest_preparation_failure_does_not_leave_temporary_files(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"

    def fail_manifest_validation(path: Path, *, expected_checksum: str | None = None) -> dict[str, object]:
        msg = "forced manifest validation failure"
        raise DataExportError(msg)

    monkeypatch.setattr(writer, "_validate_manifest_file", fail_manifest_validation)

    with pytest.raises(DataExportError, match="forced manifest validation failure"):
        writer.write(processed_dataframe, output_path)

    leftovers = list(tmp_path.glob("*.tmp")) + list(tmp_path.glob("*.publish-backup"))
    assert leftovers == []


def test_manifest_publication_failure_preserves_existing_artifacts(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    manifest_path = tmp_path / "product_catalog.manifest.json"
    writer.write(processed_dataframe, output_path, manifest_path=manifest_path)
    original_parquet_checksum = writer.checksum_file(output_path)
    original_manifest = manifest_path.read_text(encoding="utf-8")

    updated = processed_dataframe.copy()
    updated.loc[0, "description"] = "Updated Description For Publication Test"

    original_replace = os.replace
    failure_allowed = True

    def flaky_replace(source: str | Path, destination: str | Path) -> None:
        nonlocal failure_allowed
        source_path = Path(source)
        destination_path = Path(destination)
        if (
            failure_allowed
            and destination_path == manifest_path
            and source_path.suffix == ".tmp"
        ):
            failure_allowed = False
            msg = "forced manifest publication failure"
            raise OSError(msg)
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", flaky_replace)

    with pytest.raises(OSError, match="forced manifest publication failure"):
        writer.write(updated, output_path, manifest_path=manifest_path)

    assert writer.checksum_file(output_path) == original_parquet_checksum
    assert manifest_path.read_text(encoding="utf-8") == original_manifest
    leftovers = list(tmp_path.glob("*.tmp")) + list(tmp_path.glob("*.publish-backup"))
    assert leftovers == []


def test_publication_uses_atomic_replace_for_both_artifacts(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    manifest_path = tmp_path / "product_catalog.manifest.json"
    replace_calls: list[tuple[Path, Path]] = []
    original_replace = os.replace

    def track_replace(source: str | Path, destination: str | Path) -> None:
        replace_calls.append((Path(source), Path(destination)))
        original_replace(source, destination)

    monkeypatch.setattr(os, "replace", track_replace)
    writer.write(processed_dataframe, output_path, manifest_path=manifest_path)

    published = [
        (source, destination)
        for source, destination in replace_calls
        if destination in {output_path, manifest_path}
    ]
    assert len(published) == 2
    assert published[0][1] == output_path
    assert published[1][1] == manifest_path


def test_readback_validation_accepts_valid_canonical_string_dtypes(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    output_path = tmp_path / "product_catalog.parquet"
    writer.write(processed_dataframe, output_path)

    loaded = pd.read_parquet(output_path)
    ProcessedDatasetWriter._validate_readback_dtypes(loaded)


def test_readback_validation_rejects_invalid_canonical_string_dtype(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
) -> None:
    invalid = processed_dataframe.copy()
    invalid["product_id"] = invalid["product_id"].astype("int64")

    with pytest.raises(DataExportError, match="product_id must not be numeric"):
        ProcessedDatasetWriter._validate_readback_dtypes(invalid)


def test_wrong_column_order_fails(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    shuffled = processed_dataframe[list(reversed(processed_dataframe.columns))]
    with pytest.raises(DataExportError, match="deterministic ProductIQ column order"):
        writer.write(shuffled, tmp_path / "product_catalog.parquet")


def test_data_export_error_inherits_from_productiq_error() -> None:
    error = DataExportError("export failed")

    assert isinstance(error, ProductIQError)


def test_input_dataframe_is_not_mutated(
    writer: ProcessedDatasetWriter,
    processed_dataframe: pd.DataFrame,
    tmp_path: Path,
) -> None:
    before = deepcopy(processed_dataframe)
    writer.write(processed_dataframe, tmp_path / "product_catalog.parquet")

    pd.testing.assert_frame_equal(processed_dataframe, before)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
AJIO_DATASET_PATH = PROJECT_ROOT / "resources" / "raw" / "Ajio Fashion Clothing.csv"


@pytest.mark.skipif(not AJIO_DATASET_PATH.is_file(), reason="AJIO raw dataset is unavailable")
def test_full_pipeline_processed_dataset_integration(tmp_path: Path) -> None:
    from data.catalog import AjioCanonicalProductBuilder
    from data.deduplication import AjioDataDeduplicator
    from data.ingestion import AjioDataLoader
    from data.preprocessing import AjioDataCleaner, AjioDataNormalizer
    from data.validation import AjioDataValidator

    raw_df = AjioDataLoader().load(AJIO_DATASET_PATH)
    AjioDataValidator().validate(raw_df)
    cleaned_df = AjioDataCleaner().clean(raw_df).dataframe
    normalized_df = AjioDataNormalizer().normalize(cleaned_df).dataframe
    prepared_df = AjioDataDeduplicator().deduplicate(normalized_df).dataframe
    canonical_df = AjioCanonicalProductBuilder().build(prepared_df).dataframe
    enriched_df = ProductAttributeExtractor().extract(canonical_df).dataframe

    writer = ProcessedDatasetWriter()
    output_path = tmp_path / "product_catalog.parquet"
    result = writer.write(
        enriched_df,
        output_path,
        expected_row_count=AJIO_PROCESSED_ROW_COUNT,
    )

    assert result.report.output_row_count == AJIO_PROCESSED_ROW_COUNT
    assert result.report.column_count == PROCESSED_COLUMN_COUNT
    assert writer.validate(output_path, expected_row_count=AJIO_PROCESSED_ROW_COUNT).validation_passed
