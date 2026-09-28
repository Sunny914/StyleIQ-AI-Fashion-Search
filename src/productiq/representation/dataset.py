"""Materialize Phase 3 product representations into a processed Parquet dataset (Phase 3.11)."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]

from data.export import ProcessedDatasetWriter
from data.export.schema import PROCESSED_COLUMN_ORDER
from productiq.exceptions.base import RepresentationDatasetError
from productiq.representation.dataset_schema import (
    CHECKSUM_ALGORITHM,
    FILTERING_METADATA_COLUMNS,
    LEXICAL_TEXT_COLUMN,
    PRODUCT_TEXT_COLUMN,
    REPRESENTATION_DATASET_COLUMN_COUNT,
    REPRESENTATION_DATASET_COLUMN_ORDER,
    REPRESENTATION_DATASET_FORMAT,
    REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS,
    REPRESENTATION_DATASET_NAME,
    REPRESENTATION_DATASET_SCHEMA_VERSION,
    REPRESENTATION_MANIFEST_FILENAME,
    REPRESENTATION_PIPELINE_PHASE,
    SEMANTIC_TEXT_COLUMN,
    SOURCE_CATALOG_DATASET_NAME,
    SOURCE_CATALOG_PARQUET_FILENAME,
    TEXT_COLUMNS,
)
from productiq.representation.filtering import filtering_representation_to_dict
from productiq.representation.ontology import MULTI_VALUE_DELIMITER
from productiq.representation.pipeline import (
    ProductRepresentationBundle,
    build_product_representation_bundle,
)
from productiq.representation.serializers import REPRESENTATION_FIELD_ORDER, representation_to_dict

PARQUET_ENGINE: Literal["pyarrow"] = "pyarrow"
DEFAULT_REPRESENTATION_DATASET_BATCH_SIZE = 10_000


@dataclass(frozen=True)
class RepresentationDatasetWriteReport:
    """Summary of a representation dataset generation run."""

    source_path: Path
    output_path: Path
    manifest_path: Path
    source_row_count: int
    output_row_count: int
    column_count: int
    batch_size: int
    schema_version: str
    checksum: str
    validation_passed: bool

    def summary(self) -> str:
        return "\n".join(
            [
                f"Source: {self.source_path.name}",
                f"Output: {self.output_path.name}",
                f"Source rows: {self.source_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Columns: {self.column_count}",
                f"Batch size: {self.batch_size}",
                f"Schema version: {self.schema_version}",
                f"Checksum ({CHECKSUM_ALGORITHM}): {self.checksum}",
                f"Validation passed: {self.validation_passed}",
            ]
        )


@dataclass(frozen=True)
class RepresentationDatasetWriteResult:
    parquet_path: Path
    manifest_path: Path
    report: RepresentationDatasetWriteReport


@dataclass(frozen=True)
class RepresentationDatasetValidationReport:
    row_count: int
    column_count: int
    product_id_unique: bool
    validation_passed: bool

    def summary(self) -> str:
        return "\n".join(
            [
                f"Rows: {self.row_count}",
                f"Columns: {self.column_count}",
                f"product_id unique: {self.product_id_unique}",
                f"Validation passed: {self.validation_passed}",
            ]
        )


def _encode_multivalue_storage(value: list[str] | None) -> str | None:
    if value is None:
        return None
    return MULTI_VALUE_DELIMITER.join(value)


def bundle_to_dataset_row(bundle: ProductRepresentationBundle) -> dict[str, Any]:
    """Flatten one bundle into a deterministic dataset row dict."""
    product_data = representation_to_dict(bundle.product)
    filtering_data = filtering_representation_to_dict(bundle.filtering)
    row: dict[str, Any] = {}
    for key in REPRESENTATION_FIELD_ORDER:
        value = product_data[key]
        if key in REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS:
            row[key] = _encode_multivalue_storage(value)
        else:
            row[key] = value
    row[PRODUCT_TEXT_COLUMN] = bundle.text
    row[LEXICAL_TEXT_COLUMN] = bundle.lexical
    row[SEMANTIC_TEXT_COLUMN] = bundle.semantic
    for key in FILTERING_METADATA_COLUMNS:
        row[key] = filtering_data[key]
    return row


def _parquet_batch_to_records(batch: pa.RecordBatch) -> list[dict[str, Any]]:
    chunk = batch.to_pandas()
    chunk = chunk.loc[:, list(PROCESSED_COLUMN_ORDER)]
    records: list[dict[str, Any]] = []
    for row in chunk.to_dict(orient="records"):
        cleaned: dict[str, Any] = {}
        for key, value in row.items():
            cleaned[str(key)] = None if value is pd.NA or pd.isna(value) else value
        records.append(cleaned)
    return records


def _rows_to_dataframe(rows: list[dict[str, Any]]) -> pd.DataFrame:
    if not rows:
        msg = "Representation dataset batch must not be empty"
        raise RepresentationDatasetError(msg)
    frame = pd.DataFrame(rows)
    frame = frame.loc[:, list(REPRESENTATION_DATASET_COLUMN_ORDER)]
    for column in REPRESENTATION_FIELD_ORDER:
        if column in REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS or column not in (
            "discount_price_inr",
            "original_price_inr",
        ):
            frame[column] = frame[column].astype("string")
    for column in TEXT_COLUMNS:
        frame[column] = frame[column].astype("string")
    frame["source"] = frame["source"].astype("string")
    frame["color_raw"] = frame["color_raw"].astype("string")
    frame["color_is_coded"] = frame["color_is_coded"].astype("boolean")
    frame["price_anomaly"] = frame["price_anomaly"].astype("boolean")
    frame["discount_price_inr"] = frame["discount_price_inr"].astype("Int64")
    frame["original_price_inr"] = frame["original_price_inr"].astype("Int64")
    return frame


class RepresentationDatasetValidator:
    """Validate a materialized representation dataset artifact."""

    def validate(
        self,
        path: Path,
        *,
        expected_row_count: int | None = None,
    ) -> RepresentationDatasetValidationReport:
        resolved = Path(path)
        if not resolved.is_file():
            msg = f"Representation dataset artifact not found: {resolved}"
            raise RepresentationDatasetError(msg)

        dataframe = pd.read_parquet(resolved, engine=PARQUET_ENGINE)
        self._validate_dataframe(dataframe, expected_row_count=expected_row_count)
        return RepresentationDatasetValidationReport(
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            product_id_unique=bool(dataframe["product_id"].is_unique),
            validation_passed=True,
        )

    @staticmethod
    def _validate_dataframe(
        dataframe: pd.DataFrame,
        *,
        expected_row_count: int | None,
    ) -> None:
        if list(dataframe.columns) != list(REPRESENTATION_DATASET_COLUMN_ORDER):
            msg = "Representation dataset column order does not match the Phase 3.11 contract"
            raise RepresentationDatasetError(msg)
        if len(dataframe.columns) != REPRESENTATION_DATASET_COLUMN_COUNT:
            msg = (
                f"Representation dataset must contain {REPRESENTATION_DATASET_COLUMN_COUNT} columns, "
                f"found {len(dataframe.columns)}"
            )
            raise RepresentationDatasetError(msg)
        row_count = len(dataframe)
        if expected_row_count is not None and row_count != expected_row_count:
            msg = (
                f"Representation dataset row count mismatch: "
                f"expected={expected_row_count}, found={row_count}"
            )
            raise RepresentationDatasetError(msg)
        if dataframe["product_id"].isna().any():
            msg = "Representation dataset product_id must be non-null"
            raise RepresentationDatasetError(msg)
        if dataframe["product_id"].duplicated().any():
            msg = "Representation dataset product_id must be unique"
            raise RepresentationDatasetError(msg)
        forbidden_tokens = ("unknown", "none", "unavailable")
        for column in REPRESENTATION_FIELD_ORDER:
            if column in REPRESENTATION_DATASET_MULTI_VALUE_COLUMNS:
                continue
            series = dataframe[column]
            if not pd.api.types.is_string_dtype(series):
                continue
            lowered = series.dropna().astype(str).str.lower()
            for token in forbidden_tokens:
                if (lowered == token).any():
                    msg = f"Representation dataset column {column} contains forbidden placeholder token"
                    raise RepresentationDatasetError(msg)


class RepresentationDatasetGenerator:
    """Batch-generate a representation dataset from Phase 2 canonical Parquet."""

    def __init__(self, *, batch_size: int = DEFAULT_REPRESENTATION_DATASET_BATCH_SIZE) -> None:
        if batch_size <= 0:
            msg = "Representation dataset batch_size must be positive"
            raise RepresentationDatasetError(msg)
        self.batch_size = batch_size
        self._validator = RepresentationDatasetValidator()

    def generate(
        self,
        canonical_parquet_path: Path,
        output_path: Path,
        *,
        manifest_path: Path | None = None,
        validate_canonical_input: bool = True,
        expected_source_row_count: int | None = None,
    ) -> RepresentationDatasetWriteResult:
        """Build representation rows in batches and publish Parquet + manifest atomically."""
        source_path = Path(canonical_parquet_path)
        resolved_output = Path(output_path)
        resolved_manifest = (
            Path(manifest_path)
            if manifest_path is not None
            else resolved_output.parent / REPRESENTATION_MANIFEST_FILENAME
        )

        if validate_canonical_input:
            ProcessedDatasetWriter().validate(
                source_path,
                expected_row_count=expected_source_row_count,
            )

        parquet_file = pq.ParquetFile(source_path)
        source_row_count = parquet_file.metadata.num_rows
        if expected_source_row_count is not None and source_row_count != expected_source_row_count:
            msg = (
                f"Canonical catalog row count mismatch: "
                f"expected={expected_source_row_count}, found={source_row_count}"
            )
            raise RepresentationDatasetError(msg)

        source_manifest = _load_source_manifest_if_present(source_path)
        source_checksum = source_manifest.get("checksum") if source_manifest else None

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        temp_parquet_path: Path | None = None
        temp_manifest_path: Path | None = None
        rows_written = 0
        writer: pq.ParquetWriter | None = None

        try:
            with NamedTemporaryFile(
                delete=False,
                dir=resolved_output.parent,
                prefix=f".{resolved_output.stem}.",
                suffix=".parquet.tmp",
            ) as temp_file:
                temp_parquet_path = Path(temp_file.name)

            for batch in parquet_file.iter_batches(batch_size=self.batch_size):
                records = _parquet_batch_to_records(batch)
                rows = [
                    bundle_to_dataset_row(build_product_representation_bundle(record))
                    for record in records
                ]
                frame = _rows_to_dataframe(rows)
                table = pa.Table.from_pandas(frame, preserve_index=False)
                if writer is None:
                    writer = pq.ParquetWriter(temp_parquet_path, table.schema, compression="snappy")
                writer.write_table(table)
                rows_written += len(rows)

            if writer is not None:
                writer.close()
                writer = None
            elif temp_parquet_path is not None:
                msg = "Representation dataset generation produced no rows"
                raise RepresentationDatasetError(msg)

            if rows_written != source_row_count:
                msg = (
                    f"Representation dataset row count must match canonical catalog: "
                    f"source={source_row_count}, generated={rows_written}"
                )
                raise RepresentationDatasetError(msg)

            self._validator.validate(temp_parquet_path, expected_row_count=source_row_count)

            checksum = _checksum_file(temp_parquet_path)
            manifest_payload = _build_manifest_payload(
                output_filename=resolved_output.name,
                row_count=rows_written,
                checksum=checksum,
                source_path=source_path,
                source_row_count=source_row_count,
                source_checksum=source_checksum,
                batch_size=self.batch_size,
            )
            temp_manifest_path = _write_manifest_temp(resolved_manifest.parent, manifest_payload)
            _publish_prepared_artifacts(
                temp_parquet_path=temp_parquet_path,
                temp_manifest_path=temp_manifest_path,
                final_parquet_path=resolved_output,
                final_manifest_path=resolved_manifest,
            )
            temp_parquet_path = None
            temp_manifest_path = None

            report = RepresentationDatasetWriteReport(
                source_path=source_path,
                output_path=resolved_output,
                manifest_path=resolved_manifest,
                source_row_count=source_row_count,
                output_row_count=rows_written,
                column_count=REPRESENTATION_DATASET_COLUMN_COUNT,
                batch_size=self.batch_size,
                schema_version=REPRESENTATION_DATASET_SCHEMA_VERSION,
                checksum=checksum,
                validation_passed=True,
            )
            return RepresentationDatasetWriteResult(
                parquet_path=resolved_output,
                manifest_path=resolved_manifest,
                report=report,
            )
        except Exception:
            if writer is not None:
                writer.close()
            if temp_parquet_path is not None and temp_parquet_path.exists():
                temp_parquet_path.unlink(missing_ok=True)
            if temp_manifest_path is not None and temp_manifest_path.exists():
                temp_manifest_path.unlink(missing_ok=True)
            raise


def generate_representation_dataset(
    canonical_parquet_path: Path,
    output_path: Path,
    *,
    batch_size: int = DEFAULT_REPRESENTATION_DATASET_BATCH_SIZE,
    manifest_path: Path | None = None,
    validate_canonical_input: bool = True,
    expected_source_row_count: int | None = None,
) -> RepresentationDatasetWriteResult:
    """Convenience entry point for representation dataset generation."""
    generator = RepresentationDatasetGenerator(batch_size=batch_size)
    return generator.generate(
        canonical_parquet_path,
        output_path,
        manifest_path=manifest_path,
        validate_canonical_input=validate_canonical_input,
        expected_source_row_count=expected_source_row_count,
    )


def validate_representation_dataset(
    path: Path,
    *,
    expected_row_count: int | None = None,
) -> RepresentationDatasetValidationReport:
    """Validate an on-disk representation dataset artifact."""
    return RepresentationDatasetValidator().validate(path, expected_row_count=expected_row_count)


def load_representation_dataset_manifest(path: Path) -> dict[str, Any]:
    """Load the representation dataset manifest JSON object."""
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"Representation dataset manifest is not valid JSON: {manifest_path}"
        raise RepresentationDatasetError(msg) from exc
    if not isinstance(payload, dict):
        msg = "Representation dataset manifest must be a JSON object"
        raise RepresentationDatasetError(msg)
    return payload


def _load_source_manifest_if_present(source_parquet: Path) -> dict[str, Any] | None:
    manifest_path = source_parquet.parent / f"{SOURCE_CATALOG_DATASET_NAME}.manifest.json"
    if not manifest_path.is_file():
        return None
    return ProcessedDatasetWriter.load_manifest(manifest_path)


def _checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize_manifest(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, indent=2, sort_keys=True)
    return f"{serialized}\n"


def _write_manifest_temp(parent: Path, payload: dict[str, Any]) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{REPRESENTATION_MANIFEST_FILENAME}.",
        suffix=".json.tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(_serialize_manifest(payload).encode("utf-8"))
    return temp_path


def _build_manifest_payload(
    *,
    output_filename: str,
    row_count: int,
    checksum: str,
    source_path: Path,
    source_row_count: int,
    source_checksum: str | None,
    batch_size: int,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "batch_size": batch_size,
        "checksum": checksum,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "column_count": REPRESENTATION_DATASET_COLUMN_COUNT,
        "columns": list(REPRESENTATION_DATASET_COLUMN_ORDER),
        "dataset_name": REPRESENTATION_DATASET_NAME,
        "format": REPRESENTATION_DATASET_FORMAT,
        "output_filename": output_filename,
        "pipeline_phase": REPRESENTATION_PIPELINE_PHASE,
        "row_count": row_count,
        "schema_version": REPRESENTATION_DATASET_SCHEMA_VERSION,
        "source_catalog_dataset_name": SOURCE_CATALOG_DATASET_NAME,
        "source_catalog_filename": SOURCE_CATALOG_PARQUET_FILENAME,
        "source_catalog_path": source_path.name,
        "source_row_count": source_row_count,
    }
    if source_checksum is not None:
        payload["source_catalog_checksum"] = source_checksum
    return payload


def _publish_prepared_artifacts(
    *,
    temp_parquet_path: Path,
    temp_manifest_path: Path,
    final_parquet_path: Path,
    final_manifest_path: Path,
) -> None:
    parquet_backup = _move_aside_if_exists(final_parquet_path)
    try:
        manifest_backup = _move_aside_if_exists(final_manifest_path)
    except Exception:
        _restore_aside(final_parquet_path, parquet_backup)
        raise

    parquet_published = False
    try:
        os.replace(temp_parquet_path, final_parquet_path)
        parquet_published = True
        os.replace(temp_manifest_path, final_manifest_path)
    except Exception:
        if parquet_published:
            _rollback_published_parquet(
                final_parquet_path=final_parquet_path,
                parquet_backup=parquet_backup,
            )
        else:
            _restore_aside(final_parquet_path, parquet_backup)
        _restore_aside(final_manifest_path, manifest_backup)
        raise
    finally:
        _cleanup_aside(parquet_backup)
        _cleanup_aside(manifest_backup)


def _move_aside_if_exists(path: Path) -> Path | None:
    if not path.exists():
        return None
    backup_path = path.with_name(f"{path.name}.publish-backup")
    if backup_path.exists():
        backup_path.unlink()
    os.replace(path, backup_path)
    return backup_path


def _restore_aside(final_path: Path, backup_path: Path | None) -> None:
    if backup_path is None:
        return
    if final_path.exists():
        final_path.unlink()
    os.replace(backup_path, final_path)


def _rollback_published_parquet(*, final_parquet_path: Path, parquet_backup: Path | None) -> None:
    if parquet_backup is not None:
        if final_parquet_path.exists():
            final_parquet_path.unlink()
        os.replace(parquet_backup, final_parquet_path)
        return
    if final_parquet_path.exists():
        final_parquet_path.unlink()


def _cleanup_aside(backup_path: Path | None) -> None:
    if backup_path is not None and backup_path.exists():
        backup_path.unlink()


__all__ = [
    "DEFAULT_REPRESENTATION_DATASET_BATCH_SIZE",
    "PARQUET_ENGINE",
    "RepresentationDatasetGenerator",
    "RepresentationDatasetValidationReport",
    "RepresentationDatasetValidator",
    "RepresentationDatasetWriteReport",
    "RepresentationDatasetWriteResult",
    "bundle_to_dataset_row",
    "generate_representation_dataset",
    "load_representation_dataset_manifest",
    "validate_representation_dataset",
]
