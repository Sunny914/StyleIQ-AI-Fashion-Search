"""Write and validate the ProductIQ processed product catalog artifact."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import pandas as pd

from data.export.schema import (
    AJIO_SOURCE_NAME,
    ATTRIBUTE_COLUMNS,
    CANONICAL_STRING_COLUMNS,
    CHECKSUM_ALGORITHM,
    PIPELINE_PHASE,
    PROCESSED_COLUMN_COUNT,
    PROCESSED_COLUMN_ORDER,
    PROCESSED_DATASET_FORMAT,
    PROCESSED_DATASET_NAME,
    PROCESSED_DATASET_SCHEMA_VERSION,
    PROCESSED_EXPECTED_DTYPES,
    PROCESSED_MANIFEST_FILENAME,
)
from productiq.exceptions import DataExportError

PARQUET_ENGINE: Literal["pyarrow"] = "pyarrow"


@dataclass(frozen=True)
class ProcessedDatasetWriteReport:
    """Summary of a processed dataset write operation."""

    input_row_count: int
    output_row_count: int
    column_count: int
    output_path: Path
    manifest_path: Path
    format: str
    file_size_bytes: int
    schema_version: str
    checksum: str
    validation_passed: bool

    def summary(self) -> str:
        """Return a human-readable write summary."""
        return "\n".join(
            [
                f"Input rows: {self.input_row_count}",
                f"Output rows: {self.output_row_count}",
                f"Columns: {self.column_count}",
                f"Format: {self.format}",
                f"Schema version: {self.schema_version}",
                f"Output file: {self.output_path.name}",
                f"File size (bytes): {self.file_size_bytes}",
                f"Checksum ({CHECKSUM_ALGORITHM}): {self.checksum}",
                f"Validation passed: {self.validation_passed}",
            ]
        )


@dataclass(frozen=True)
class ProcessedDatasetWriteResult:
    """Processed dataset artifact paths and write report."""

    parquet_path: Path
    manifest_path: Path
    report: ProcessedDatasetWriteReport


@dataclass(frozen=True)
class ProcessedDatasetValidationReport:
    """Summary of read-back validation for a processed dataset artifact."""

    row_count: int
    column_count: int
    product_id_unique: bool
    source_value: str
    validation_passed: bool

    def summary(self) -> str:
        """Return a human-readable validation summary."""
        return "\n".join(
            [
                f"Rows: {self.row_count}",
                f"Columns: {self.column_count}",
                f"product_id unique: {self.product_id_unique}",
                f"source: {self.source_value}",
                f"Validation passed: {self.validation_passed}",
            ]
        )


class ProcessedDatasetWriter:
    """Persist and validate the 22-column ProductIQ processed catalog artifact."""

    def write(
        self,
        dataframe: pd.DataFrame,
        output_path: Path,
        *,
        expected_row_count: int | None = None,
        manifest_path: Path | None = None,
    ) -> ProcessedDatasetWriteResult:
        """Validate input, write Parquet atomically, validate read-back, and write manifest."""
        import logging

        logger = logging.getLogger(__name__)
        resolved_output = Path(output_path)
        resolved_manifest = (
            Path(manifest_path)
            if manifest_path is not None
            else resolved_output.parent / PROCESSED_MANIFEST_FILENAME
        )

        self._validate_input_contract(dataframe, expected_row_count=expected_row_count)
        input_row_count = len(dataframe)
        prepared = self._prepare_output_dataframe(dataframe)

        resolved_output.parent.mkdir(parents=True, exist_ok=True)
        temp_parquet_path: Path | None = None
        temp_manifest_path: Path | None = None
        try:
            with NamedTemporaryFile(
                delete=False,
                dir=resolved_output.parent,
                prefix=f".{resolved_output.stem}.",
                suffix=".parquet.tmp",
            ) as temp_file:
                temp_parquet_path = Path(temp_file.name)

            self._write_parquet(prepared, temp_parquet_path)
            self.validate(temp_parquet_path, expected_row_count=expected_row_count)

            checksum = self._checksum_file(temp_parquet_path)
            manifest_payload = self._build_manifest_payload(
                output_filename=resolved_output.name,
                row_count=input_row_count,
                checksum=checksum,
            )
            temp_manifest_path = self._write_manifest_temp(resolved_manifest.parent, manifest_payload)
            self._validate_manifest_file(temp_manifest_path, expected_checksum=checksum)

            self._publish_prepared_artifacts(
                temp_parquet_path=temp_parquet_path,
                temp_manifest_path=temp_manifest_path,
                final_parquet_path=resolved_output,
                final_manifest_path=resolved_manifest,
            )
            temp_parquet_path = None
            temp_manifest_path = None

            file_size_bytes = resolved_output.stat().st_size

            report = ProcessedDatasetWriteReport(
                input_row_count=input_row_count,
                output_row_count=input_row_count,
                column_count=PROCESSED_COLUMN_COUNT,
                output_path=resolved_output,
                manifest_path=resolved_manifest,
                format=PROCESSED_DATASET_FORMAT,
                file_size_bytes=file_size_bytes,
                schema_version=PROCESSED_DATASET_SCHEMA_VERSION,
                checksum=checksum,
                validation_passed=True,
            )
            logger.info(
                "Wrote processed ProductIQ dataset (%s rows) to %s",
                report.output_row_count,
                resolved_output.name,
            )
            return ProcessedDatasetWriteResult(
                parquet_path=resolved_output,
                manifest_path=resolved_manifest,
                report=report,
            )
        except Exception:
            if temp_parquet_path is not None and temp_parquet_path.exists():
                temp_parquet_path.unlink(missing_ok=True)
            if temp_manifest_path is not None and temp_manifest_path.exists():
                temp_manifest_path.unlink(missing_ok=True)
            raise

    def validate_dataframe(
        self,
        dataframe: pd.DataFrame,
        *,
        expected_row_count: int | None = None,
    ) -> ProcessedDatasetValidationReport:
        """Validate an in-memory dataframe against the processed dataset contract."""
        self._validate_input_contract(dataframe, expected_row_count=expected_row_count)
        source_values = dataframe["source"].dropna().unique()
        source_value = str(source_values[0]) if len(source_values) else ""
        return ProcessedDatasetValidationReport(
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            product_id_unique=bool(dataframe["product_id"].is_unique),
            source_value=source_value,
            validation_passed=True,
        )

    def validate(
        self,
        path: Path,
        *,
        expected_row_count: int | None = None,
    ) -> ProcessedDatasetValidationReport:
        """Read a Parquet artifact and verify the processed dataset contract."""
        resolved_path = Path(path)
        if not resolved_path.is_file():
            msg = f"Processed dataset artifact not found: {resolved_path}"
            raise DataExportError(msg)

        dataframe = pd.read_parquet(resolved_path, engine=PARQUET_ENGINE)
        self._validate_loaded_contract(dataframe, expected_row_count=expected_row_count)

        source_values = dataframe["source"].dropna().unique()
        source_value = str(source_values[0]) if len(source_values) else ""

        return ProcessedDatasetValidationReport(
            row_count=len(dataframe),
            column_count=len(dataframe.columns),
            product_id_unique=bool(dataframe["product_id"].is_unique),
            source_value=source_value,
            validation_passed=True,
        )

    @staticmethod
    def checksum_file(path: Path) -> str:
        """Return the SHA-256 checksum of an on-disk artifact."""
        return ProcessedDatasetWriter._checksum_file(path)

    @staticmethod
    def load_manifest(path: Path) -> dict[str, Any]:
        """Load and parse a processed dataset manifest."""
        manifest_path = Path(path)
        try:
            payload = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            msg = f"Processed dataset manifest is not valid JSON: {manifest_path}"
            raise DataExportError(msg) from exc
        if not isinstance(payload, dict):
            msg = "Processed dataset manifest must be a JSON object"
            raise DataExportError(msg)
        return payload

    def _validate_input_contract(
        self,
        dataframe: pd.DataFrame,
        *,
        expected_row_count: int | None,
    ) -> None:
        if not isinstance(dataframe, pd.DataFrame):
            msg = "Processed dataset input must be a pandas DataFrame"
            raise DataExportError(msg)

        if list(dataframe.columns) != list(PROCESSED_COLUMN_ORDER):
            if set(dataframe.columns) != set(PROCESSED_COLUMN_ORDER):
                unexpected = sorted(set(dataframe.columns) - set(PROCESSED_COLUMN_ORDER))
                missing = sorted(set(PROCESSED_COLUMN_ORDER) - set(dataframe.columns))
                details: list[str] = []
                if missing:
                    details.append(f"missing={', '.join(missing)}")
                if unexpected:
                    details.append(f"unexpected={', '.join(unexpected)}")
                msg = f"Processed dataset column mismatch ({'; '.join(details)})"
                raise DataExportError(msg)
            msg = "Processed dataset columns must match the deterministic ProductIQ column order"
            raise DataExportError(msg)

        if len(dataframe.columns) != PROCESSED_COLUMN_COUNT:
            msg = (
                f"Processed dataset must contain {PROCESSED_COLUMN_COUNT} columns, "
                f"found {len(dataframe.columns)}"
            )
            raise DataExportError(msg)

        self._validate_row_semantics(dataframe, expected_row_count=expected_row_count)
        self._validate_dtypes(dataframe)

    def _validate_loaded_contract(
        self,
        dataframe: pd.DataFrame,
        *,
        expected_row_count: int | None,
    ) -> None:
        if list(dataframe.columns) != list(PROCESSED_COLUMN_ORDER):
            msg = "Processed dataset read-back column order does not match the ProductIQ contract"
            raise DataExportError(msg)

        if len(dataframe.columns) != PROCESSED_COLUMN_COUNT:
            msg = (
                f"Processed dataset read-back must contain {PROCESSED_COLUMN_COUNT} columns, "
                f"found {len(dataframe.columns)}"
            )
            raise DataExportError(msg)

        self._validate_row_semantics(dataframe, expected_row_count=expected_row_count)
        self._validate_readback_dtypes(dataframe)

    @staticmethod
    def _validate_row_semantics(
        dataframe: pd.DataFrame,
        *,
        expected_row_count: int | None,
    ) -> None:
        row_count = len(dataframe)
        if expected_row_count is not None and row_count != expected_row_count:
            msg = (
                f"Processed dataset row count contract violation: "
                f"expected={expected_row_count}, found={row_count}"
            )
            raise DataExportError(msg)

        if dataframe["product_id"].isna().any():
            msg = "Processed dataset product_id must be non-null"
            raise DataExportError(msg)

        if dataframe["product_id"].duplicated().any():
            duplicate_count = int(dataframe["product_id"].duplicated().sum())
            msg = f"Processed dataset product_id must be unique (duplicates={duplicate_count})"
            raise DataExportError(msg)

        if len(dataframe) != len(dataframe.drop_duplicates()):
            msg = "Processed dataset must not contain duplicate rows"
            raise DataExportError(msg)

        source_values = dataframe["source"].dropna().unique()
        if len(source_values) != 1 or str(source_values[0]) != AJIO_SOURCE_NAME:
            msg = f'Processed dataset source must be "{AJIO_SOURCE_NAME}"'
            raise DataExportError(msg)

    @staticmethod
    def _validate_dtypes(dataframe: pd.DataFrame) -> None:
        for column, expected_dtype in PROCESSED_EXPECTED_DTYPES.items():
            actual = str(dataframe[column].dtype)
            if actual != expected_dtype:
                msg = (
                    f"Processed dataset column {column} has dtype {actual}, "
                    f"expected {expected_dtype}"
                )
                raise DataExportError(msg)

        for column in ATTRIBUTE_COLUMNS:
            if str(dataframe[column].dtype) == "object":
                msg = f"Processed dataset attribute column {column} must not use object dtype"
                raise DataExportError(msg)

    @staticmethod
    def _validate_readback_dtypes(dataframe: pd.DataFrame) -> None:
        for column in ("discount_price_inr", "original_price_inr"):
            if not pd.api.types.is_integer_dtype(dataframe[column]):
                msg = f"Processed dataset read-back column {column} must be integer dtype"
                raise DataExportError(msg)

        for column in ("color_is_coded", "price_anomaly"):
            if not pd.api.types.is_bool_dtype(dataframe[column]):
                msg = f"Processed dataset read-back column {column} must be boolean dtype"
                raise DataExportError(msg)

        for column in CANONICAL_STRING_COLUMNS:
            ProcessedDatasetWriter._validate_readback_string_column(dataframe, column)

        for column in ATTRIBUTE_COLUMNS:
            ProcessedDatasetWriter._validate_readback_string_column(
                dataframe,
                column,
                label="attribute",
            )

    @staticmethod
    def _validate_readback_string_column(
        dataframe: pd.DataFrame,
        column: str,
        *,
        label: str = "canonical",
    ) -> None:
        series = dataframe[column]
        dtype_name = str(series.dtype)
        if dtype_name == "object":
            msg = f"Processed dataset read-back {label} column {column} must not be object"
            raise DataExportError(msg)
        if pd.api.types.is_bool_dtype(series):
            msg = f"Processed dataset read-back {label} column {column} must not be boolean"
            raise DataExportError(msg)
        if pd.api.types.is_numeric_dtype(series):
            msg = f"Processed dataset read-back {label} column {column} must not be numeric"
            raise DataExportError(msg)
        if dtype_name not in {"string", "str"} and not pd.api.types.is_string_dtype(series):
            msg = f"Processed dataset read-back {label} column {column} must be string dtype"
            raise DataExportError(msg)

    @staticmethod
    def _prepare_output_dataframe(dataframe: pd.DataFrame) -> pd.DataFrame:
        prepared = dataframe.loc[:, list(PROCESSED_COLUMN_ORDER)].copy(deep=True)
        if len(prepared) != len(dataframe):
            msg = "Processed dataset persistence must not remove rows"
            raise DataExportError(msg)
        return prepared

    @staticmethod
    def _write_parquet(dataframe: pd.DataFrame, path: Path) -> None:
        dataframe.to_parquet(
            path,
            engine=PARQUET_ENGINE,
            index=False,
            compression="snappy",
        )

    @staticmethod
    def _checksum_file(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as artifact:
            for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    @staticmethod
    def _serialize_manifest(payload: dict[str, Any]) -> str:
        serialized = json.dumps(payload, indent=2, sort_keys=True)
        return f"{serialized}\n"

    @staticmethod
    def _write_manifest_temp(parent: Path, payload: dict[str, Any]) -> Path:
        parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            delete=False,
            dir=parent,
            prefix=f".{PROCESSED_MANIFEST_FILENAME}.",
            suffix=".json.tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            temp_file.write(ProcessedDatasetWriter._serialize_manifest(payload).encode("utf-8"))
        return temp_path

    @staticmethod
    def _validate_manifest_file(path: Path, *, expected_checksum: str | None = None) -> dict[str, Any]:
        payload = ProcessedDatasetWriter.load_manifest(path)
        if expected_checksum is not None and payload.get("checksum") != expected_checksum:
            msg = "Processed dataset manifest checksum does not match prepared Parquet artifact"
            raise DataExportError(msg)
        return payload

    @staticmethod
    def _publish_prepared_artifacts(
        *,
        temp_parquet_path: Path,
        temp_manifest_path: Path,
        final_parquet_path: Path,
        final_manifest_path: Path,
    ) -> None:
        """Publish validated temporary Parquet and manifest atomically with simple rollback."""
        parquet_backup = ProcessedDatasetWriter._move_aside_if_exists(final_parquet_path)
        manifest_backup = ProcessedDatasetWriter._move_aside_if_exists(final_manifest_path)
        parquet_published = False
        try:
            os.replace(temp_parquet_path, final_parquet_path)
            parquet_published = True
            os.replace(temp_manifest_path, final_manifest_path)
        except Exception:
            if parquet_published:
                ProcessedDatasetWriter._rollback_published_parquet(
                    final_parquet_path=final_parquet_path,
                    parquet_backup=parquet_backup,
                )
            else:
                ProcessedDatasetWriter._restore_aside(final_parquet_path, parquet_backup)
            ProcessedDatasetWriter._restore_aside(final_manifest_path, manifest_backup)
            raise
        finally:
            ProcessedDatasetWriter._cleanup_aside(parquet_backup)
            ProcessedDatasetWriter._cleanup_aside(manifest_backup)

    @staticmethod
    def _move_aside_if_exists(path: Path) -> Path | None:
        if not path.exists():
            return None
        backup_path = path.with_name(f"{path.name}.publish-backup")
        if backup_path.exists():
            backup_path.unlink()
        os.replace(path, backup_path)
        return backup_path

    @staticmethod
    def _restore_aside(final_path: Path, backup_path: Path | None) -> None:
        if backup_path is None:
            return
        if final_path.exists():
            final_path.unlink()
        os.replace(backup_path, final_path)

    @staticmethod
    def _rollback_published_parquet(
        *,
        final_parquet_path: Path,
        parquet_backup: Path | None,
    ) -> None:
        if parquet_backup is not None:
            if final_parquet_path.exists():
                final_parquet_path.unlink()
            os.replace(parquet_backup, final_parquet_path)
            return
        if final_parquet_path.exists():
            final_parquet_path.unlink()

    @staticmethod
    def _cleanup_aside(backup_path: Path | None) -> None:
        if backup_path is not None and backup_path.exists():
            backup_path.unlink()

    @staticmethod
    def _build_manifest_payload(
        *,
        output_filename: str,
        row_count: int,
        checksum: str,
    ) -> dict[str, Any]:
        return {
            "dataset_name": PROCESSED_DATASET_NAME,
            "schema_version": PROCESSED_DATASET_SCHEMA_VERSION,
            "source": AJIO_SOURCE_NAME,
            "format": PROCESSED_DATASET_FORMAT,
            "output_filename": output_filename,
            "row_count": row_count,
            "column_count": PROCESSED_COLUMN_COUNT,
            "columns": list(PROCESSED_COLUMN_ORDER),
            "checksum_algorithm": CHECKSUM_ALGORITHM,
            "checksum": checksum,
            "pipeline_phase": PIPELINE_PHASE,
        }


__all__ = [
    "PARQUET_ENGINE",
    "ProcessedDatasetValidationReport",
    "ProcessedDatasetWriteReport",
    "ProcessedDatasetWriteResult",
    "ProcessedDatasetWriter",
]
