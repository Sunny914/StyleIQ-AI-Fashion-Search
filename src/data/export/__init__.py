"""Processed ProductIQ dataset export utilities."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = [
    "AJIO_PROCESSED_ROW_COUNT",
    "CHECKSUM_ALGORITHM",
    "PARQUET_ENGINE",
    "PIPELINE_PHASE",
    "PROCESSED_COLUMN_COUNT",
    "PROCESSED_COLUMN_ORDER",
    "PROCESSED_DATASET_FORMAT",
    "PROCESSED_DATASET_NAME",
    "PROCESSED_DATASET_SCHEMA_VERSION",
    "PROCESSED_MANIFEST_FILENAME",
    "PROCESSED_PARQUET_FILENAME",
    "ProcessedDatasetValidationReport",
    "ProcessedDatasetWriteReport",
    "ProcessedDatasetWriteResult",
    "ProcessedDatasetWriter",
]


def _lazy(module: str, *names: str) -> dict[str, tuple[str, str]]:
    return {name: (module, name) for name in names}


_LAZY_EXPORTS: dict[str, tuple[str, str]] = {}
_LAZY_EXPORTS.update(
    _lazy(
        "data.export.schema",
        "AJIO_PROCESSED_ROW_COUNT",
        "CHECKSUM_ALGORITHM",
        "PIPELINE_PHASE",
        "PROCESSED_COLUMN_COUNT",
        "PROCESSED_COLUMN_ORDER",
        "PROCESSED_DATASET_FORMAT",
        "PROCESSED_DATASET_NAME",
        "PROCESSED_DATASET_SCHEMA_VERSION",
        "PROCESSED_MANIFEST_FILENAME",
        "PROCESSED_PARQUET_FILENAME",
    )
)
_LAZY_EXPORTS.update(
    _lazy(
        "data.export.processed",
        "PARQUET_ENGINE",
        "ProcessedDatasetValidationReport",
        "ProcessedDatasetWriter",
        "ProcessedDatasetWriteReport",
        "ProcessedDatasetWriteResult",
    )
)


def __getattr__(name: str) -> Any:
    if name not in _LAZY_EXPORTS:
        msg = f"module {__name__!r} has no attribute {name!r}"
        raise AttributeError(msg)
    module_name, attr_name = _LAZY_EXPORTS[name]
    module = importlib.import_module(module_name)
    return getattr(module, attr_name)


def __dir__() -> list[str]:
    return sorted(__all__)
