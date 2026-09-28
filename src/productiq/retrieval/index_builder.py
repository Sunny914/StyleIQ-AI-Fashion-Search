"""Build and load persisted BM25 lexical indexes from representation datasets (Phase 4.6)."""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import time
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import pandas as pd
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import LexicalRetrievalError
from productiq.representation.dataset_schema import REPRESENTATION_PARQUET_FILENAME
from productiq.retrieval.bm25 import BM25Config
from productiq.retrieval.index_schema import (
    BM25_LEXICAL_INDEX_FILENAME,
    BM25_LEXICAL_INDEX_FORMAT,
    BM25_LEXICAL_INDEX_MANIFEST_FILENAME,
    BM25_LEXICAL_INDEX_NAME,
    BM25_LEXICAL_INDEX_PIPELINE_PHASE,
    BM25_LEXICAL_INDEX_SCHEMA_VERSION,
    CHECKSUM_ALGORITHM,
    DEFAULT_INDEX_BUILD_BATCH_SIZE,
    INDEX_INPUT_LEXICAL_TEXT_COLUMN,
    INDEX_INPUT_PRODUCT_ID_COLUMN,
    LEXICAL_TOKENIZER_IDENTIFIER,
    REPRESENTATION_DATASET_NAME,
    REPRESENTATION_DATASET_SCHEMA_VERSION,
    REPRESENTATION_MANIFEST_FILENAME,
)
from productiq.retrieval.lexical import (
    InvertedLexicalIndex,
    assemble_inverted_lexical_index,
    tokenize_lexical_text,
)

PARQUET_ENGINE: Literal["pyarrow"] = "pyarrow"
_PICKLE_PROTOCOL = 5


class LexicalIndexStatistics(BaseModel):
    """Summary statistics for a built inverted lexical index."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    document_count: int = Field(ge=0)
    total_document_length: int = Field(ge=0)
    average_document_length: float = Field(ge=0.0)
    unique_term_count: int = Field(ge=0)
    total_posting_count: int = Field(ge=0)
    empty_lexical_document_count: int = Field(ge=0)


class BM25LexicalIndexManifest(BaseModel):
    """Manifest describing a persisted BM25 lexical index artifact."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    index_name: str
    format: str
    schema_version: str
    output_filename: str
    checksum: str
    checksum_algorithm: str
    pipeline_phase: str
    source_representation_dataset_name: str
    source_representation_filename: str
    source_representation_schema_version: str
    source_representation_checksum: str | None = None
    source_representation_row_count: int = Field(ge=0)
    document_count: int = Field(ge=0)
    total_document_length: int = Field(ge=0)
    average_document_length: float = Field(ge=0.0)
    unique_term_count: int = Field(ge=0)
    total_posting_count: int = Field(ge=0)
    empty_lexical_document_count: int = Field(ge=0)
    lexical_tokenizer: str
    bm25_k1: float
    bm25_b: float
    build_duration_seconds: float = Field(ge=0.0)


@dataclass(frozen=True)
class BM25LexicalIndexBuildResult:
    """Result of building and publishing a BM25 lexical index."""

    source_path: Path
    index_path: Path
    manifest_path: Path
    index: InvertedLexicalIndex
    statistics: LexicalIndexStatistics
    manifest: BM25LexicalIndexManifest
    bm25_config: BM25Config


def compute_lexical_index_statistics(index: InvertedLexicalIndex) -> LexicalIndexStatistics:
    document_count = index.total_document_count()
    total_document_length = sum(index.document_lengths.values())
    average_document_length = (
        total_document_length / document_count if document_count > 0 else 0.0
    )
    unique_term_count = len(index.postings_by_term)
    total_posting_count = sum(len(postings) for postings in index.postings_by_term.values())
    empty_lexical_document_count = sum(
        1 for length in index.document_lengths.values() if length == 0
    )
    return LexicalIndexStatistics(
        document_count=document_count,
        total_document_length=total_document_length,
        average_document_length=average_document_length,
        unique_term_count=unique_term_count,
        total_posting_count=total_posting_count,
        empty_lexical_document_count=empty_lexical_document_count,
    )


def validate_inverted_lexical_index_integrity(index: InvertedLexicalIndex) -> None:
    """Validate structural invariants without rescanning source lexical text."""
    document_ids = index.document_ids
    if len(set(document_ids)) != len(document_ids):
        msg = "document_ids must be unique"
        raise LexicalRetrievalError(msg)

    document_id_set = set(document_ids)
    if set(index.document_lengths.keys()) != document_id_set:
        msg = "document_lengths keys must match document_ids exactly"
        raise LexicalRetrievalError(msg)

    for product_id, length in index.document_lengths.items():
        if length < 0:
            msg = f"document_length must be non-negative for {product_id}"
            raise LexicalRetrievalError(msg)

    for term, postings in index.postings_by_term.items():
        if not term:
            msg = "index term keys must not be empty"
            raise LexicalRetrievalError(msg)
        seen_products: set[str] = set()
        for posting in postings:
            if posting.product_id not in document_id_set:
                msg = f"posting references unknown product_id: {posting.product_id}"
                raise LexicalRetrievalError(msg)
            if posting.product_id in seen_products:
                msg = f"duplicate posting for term {term!r} and product {posting.product_id}"
                raise LexicalRetrievalError(msg)
            seen_products.add(posting.product_id)
            if posting.term_frequency <= 0:
                msg = "posting term_frequency must be positive"
                raise LexicalRetrievalError(msg)


def _normalize_lexical_cell(value: object) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        return ""
    if not isinstance(value, str):
        msg = "lexical_text must be a string or null"
        raise LexicalRetrievalError(msg)
    return value


def _normalize_product_id(value: object) -> str:
    if value is None or value is pd.NA or (isinstance(value, float) and pd.isna(value)):
        msg = "product_id must not be null"
        raise LexicalRetrievalError(msg)
    product_id = str(value).strip()
    if not product_id:
        msg = "product_id must not be empty"
        raise LexicalRetrievalError(msg)
    return product_id


def _read_representation_lexical_rows(
    source_path: Path,
    *,
    batch_size: int,
) -> list[tuple[str, str]]:
    resolved = Path(source_path)
    if not resolved.is_file():
        msg = f"Representation dataset not found: {resolved}"
        raise LexicalRetrievalError(msg)

    parquet_file = pq.ParquetFile(resolved)
    schema_columns = set(parquet_file.schema_arrow.names)
    missing = {
        INDEX_INPUT_PRODUCT_ID_COLUMN,
        INDEX_INPUT_LEXICAL_TEXT_COLUMN,
    } - schema_columns
    if missing:
        msg = f"Representation dataset missing required columns: {sorted(missing)}"
        raise LexicalRetrievalError(msg)

    rows: list[tuple[str, str]] = []
    seen_ids: set[str] = set()
    for batch in parquet_file.iter_batches(
        batch_size=batch_size,
        columns=[INDEX_INPUT_PRODUCT_ID_COLUMN, INDEX_INPUT_LEXICAL_TEXT_COLUMN],
    ):
        chunk = batch.to_pandas()
        for record in chunk.to_dict(orient="records"):
            product_id = _normalize_product_id(record[INDEX_INPUT_PRODUCT_ID_COLUMN])
            if product_id in seen_ids:
                msg = f"duplicate product_id in representation dataset: {product_id}"
                raise LexicalRetrievalError(msg)
            seen_ids.add(product_id)
            lexical_text = _normalize_lexical_cell(record[INDEX_INPUT_LEXICAL_TEXT_COLUMN])
            rows.append((product_id, lexical_text))

    rows.sort(key=lambda item: item[0])
    return rows


def build_inverted_lexical_index_from_lexical_rows(
    rows: Sequence[tuple[str, str]],
) -> InvertedLexicalIndex:
    """Build an inverted index from sorted ``(product_id, lexical_text)`` rows."""
    if not rows:
        return assemble_inverted_lexical_index((), {}, {})

    document_ids: list[str] = []
    document_lengths: dict[str, int] = {}
    term_to_postings: dict[str, dict[str, int]] = {}

    for product_id, lexical_text in rows:
        document_ids.append(product_id)
        tokens = tokenize_lexical_text(lexical_text)
        document_lengths[product_id] = len(tokens)

        term_counts: dict[str, int] = {}
        for token in tokens:
            term_counts[token] = term_counts.get(token, 0) + 1

        for term, tf in term_counts.items():
            postings_for_term = term_to_postings.setdefault(term, {})
            postings_for_term[product_id] = tf

    return assemble_inverted_lexical_index(document_ids, document_lengths, term_to_postings)


def inverted_lexical_index_to_payload(index: InvertedLexicalIndex) -> dict[str, Any]:
    postings_payload: dict[str, list[dict[str, int | str]]] = {}
    for term in sorted(index.postings_by_term):
        postings_payload[term] = [
            {
                "product_id": posting.product_id,
                "term_frequency": posting.term_frequency,
            }
            for posting in index.postings_by_term[term]
        ]
    return {
        "schema_version": BM25_LEXICAL_INDEX_SCHEMA_VERSION,
        "document_ids": list(index.document_ids),
        "document_lengths": dict(index.document_lengths),
        "postings_by_term": postings_payload,
    }


def inverted_lexical_index_from_payload(payload: dict[str, Any]) -> InvertedLexicalIndex:
    schema_version = payload.get("schema_version")
    if schema_version != BM25_LEXICAL_INDEX_SCHEMA_VERSION:
        msg = f"unsupported BM25 lexical index schema version: {schema_version!r}"
        raise LexicalRetrievalError(msg)

    document_ids_raw = payload.get("document_ids")
    document_lengths_raw = payload.get("document_lengths")
    postings_raw = payload.get("postings_by_term")
    if not isinstance(document_ids_raw, list) or not isinstance(document_lengths_raw, dict):
        msg = "index payload missing document_ids or document_lengths"
        raise LexicalRetrievalError(msg)
    if not isinstance(postings_raw, dict):
        msg = "index payload missing postings_by_term"
        raise LexicalRetrievalError(msg)

    document_ids = tuple(str(product_id) for product_id in document_ids_raw)
    document_lengths = {str(key): int(value) for key, value in document_lengths_raw.items()}

    term_to_postings: dict[str, dict[str, int]] = {}
    for term in sorted(postings_raw):
        entries = postings_raw[term]
        if not isinstance(entries, list):
            msg = f"invalid postings list for term {term!r}"
            raise LexicalRetrievalError(msg)
        postings_map: dict[str, int] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                msg = f"invalid posting entry for term {term!r}"
                raise LexicalRetrievalError(msg)
            product_id = str(entry["product_id"])
            term_frequency = int(entry["term_frequency"])
            postings_map[product_id] = term_frequency
        term_to_postings[str(term)] = postings_map

    index = assemble_inverted_lexical_index(document_ids, document_lengths, term_to_postings)
    validate_inverted_lexical_index_integrity(index)
    return index


def save_inverted_lexical_index(index: InvertedLexicalIndex, path: Path) -> None:
    payload = inverted_lexical_index_to_payload(index)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as artifact:
        pickle.dump(payload, artifact, protocol=_PICKLE_PROTOCOL)


def load_inverted_lexical_index(path: Path) -> InvertedLexicalIndex:
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"BM25 lexical index artifact not found: {resolved}"
        raise LexicalRetrievalError(msg)
    try:
        with resolved.open("rb") as artifact:
            payload = pickle.load(artifact)
    except (OSError, pickle.UnpicklingError) as exc:
        msg = f"BM25 lexical index artifact is not readable: {resolved}"
        raise LexicalRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "BM25 lexical index payload must be a mapping object"
        raise LexicalRetrievalError(msg)
    return inverted_lexical_index_from_payload(payload)


def _checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize_manifest(payload: dict[str, Any]) -> str:
    return f"{json.dumps(payload, indent=2, sort_keys=True)}\n"


def _write_manifest_temp(parent: Path, payload: dict[str, Any]) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{BM25_LEXICAL_INDEX_MANIFEST_FILENAME}.",
        suffix=".json.tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(_serialize_manifest(payload).encode("utf-8"))
    return temp_path


def _write_index_temp(parent: Path, index: InvertedLexicalIndex) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{BM25_LEXICAL_INDEX_FILENAME}.",
        suffix=".pkl.tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        save_inverted_lexical_index(index, temp_path)
    return temp_path


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


def _rollback_published_index(*, final_index_path: Path, index_backup: Path | None) -> None:
    if index_backup is not None:
        if final_index_path.exists():
            final_index_path.unlink()
        os.replace(index_backup, final_index_path)
        return
    if final_index_path.exists():
        final_index_path.unlink()


def _cleanup_aside(backup_path: Path | None) -> None:
    if backup_path is not None and backup_path.exists():
        backup_path.unlink()


def _publish_index_artifacts(
    *,
    temp_index_path: Path,
    temp_manifest_path: Path,
    final_index_path: Path,
    final_manifest_path: Path,
) -> None:
    index_backup = _move_aside_if_exists(final_index_path)
    try:
        manifest_backup = _move_aside_if_exists(final_manifest_path)
    except Exception:
        _restore_aside(final_index_path, index_backup)
        raise

    index_published = False
    try:
        os.replace(temp_index_path, final_index_path)
        index_published = True
        os.replace(temp_manifest_path, final_manifest_path)
    except Exception:
        if index_published:
            _rollback_published_index(
                final_index_path=final_index_path,
                index_backup=index_backup,
            )
        else:
            _restore_aside(final_index_path, index_backup)
        _restore_aside(final_manifest_path, manifest_backup)
        raise
    finally:
        _cleanup_aside(index_backup)
        _cleanup_aside(manifest_backup)


def _load_source_representation_manifest(source_path: Path) -> dict[str, Any] | None:
    from productiq.representation.dataset import load_representation_dataset_manifest

    manifest_path = source_path.parent / REPRESENTATION_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    return load_representation_dataset_manifest(manifest_path)


def load_bm25_lexical_index_manifest(path: Path) -> BM25LexicalIndexManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"BM25 lexical index manifest is not valid JSON: {manifest_path}"
        raise LexicalRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "BM25 lexical index manifest must be a JSON object"
        raise LexicalRetrievalError(msg)
    return BM25LexicalIndexManifest.model_validate(payload)


def build_bm25_lexical_index_from_representation_dataset(
    source_path: Path,
    *,
    index_path: Path | None = None,
    manifest_path: Path | None = None,
    bm25_config: BM25Config | None = None,
    batch_size: int = DEFAULT_INDEX_BUILD_BATCH_SIZE,
) -> BM25LexicalIndexBuildResult:
    """Build, validate, and atomically publish a BM25 lexical index from a representation dataset."""
    resolved_source = Path(source_path)
    resolved_index = (
        Path(index_path)
        if index_path is not None
        else resolved_source.parent / BM25_LEXICAL_INDEX_FILENAME
    )
    resolved_manifest = (
        Path(manifest_path)
        if manifest_path is not None
        else resolved_source.parent / BM25_LEXICAL_INDEX_MANIFEST_FILENAME
    )
    config = bm25_config or BM25Config()

    started = time.perf_counter()
    rows = _read_representation_lexical_rows(resolved_source, batch_size=batch_size)
    index = build_inverted_lexical_index_from_lexical_rows(rows)
    validate_inverted_lexical_index_integrity(index)
    statistics = compute_lexical_index_statistics(index)
    duration = time.perf_counter() - started

    source_manifest = _load_source_representation_manifest(resolved_source)
    source_checksum = source_manifest.get("checksum") if source_manifest else None
    source_row_count = (
        int(source_manifest["row_count"])
        if source_manifest and "row_count" in source_manifest
        else len(rows)
    )

    temp_index_path: Path | None = None
    temp_manifest_path: Path | None = None
    try:
        temp_index_path = _write_index_temp(resolved_index.parent, index)
        checksum = _checksum_file(temp_index_path)
        manifest_payload = {
            "average_document_length": statistics.average_document_length,
            "bm25_b": config.b,
            "bm25_k1": config.k1,
            "build_duration_seconds": duration,
            "checksum": checksum,
            "checksum_algorithm": CHECKSUM_ALGORITHM,
            "document_count": statistics.document_count,
            "empty_lexical_document_count": statistics.empty_lexical_document_count,
            "format": BM25_LEXICAL_INDEX_FORMAT,
            "index_name": BM25_LEXICAL_INDEX_NAME,
            "lexical_tokenizer": LEXICAL_TOKENIZER_IDENTIFIER,
            "output_filename": resolved_index.name,
            "pipeline_phase": BM25_LEXICAL_INDEX_PIPELINE_PHASE,
            "schema_version": BM25_LEXICAL_INDEX_SCHEMA_VERSION,
            "source_representation_checksum": source_checksum,
            "source_representation_dataset_name": REPRESENTATION_DATASET_NAME,
            "source_representation_filename": REPRESENTATION_PARQUET_FILENAME,
            "source_representation_row_count": source_row_count,
            "source_representation_schema_version": REPRESENTATION_DATASET_SCHEMA_VERSION,
            "total_document_length": statistics.total_document_length,
            "total_posting_count": statistics.total_posting_count,
            "unique_term_count": statistics.unique_term_count,
        }
        temp_manifest_path = _write_manifest_temp(resolved_manifest.parent, manifest_payload)
        _publish_index_artifacts(
            temp_index_path=temp_index_path,
            temp_manifest_path=temp_manifest_path,
            final_index_path=resolved_index,
            final_manifest_path=resolved_manifest,
        )
        temp_index_path = None
        temp_manifest_path = None
    finally:
        if temp_index_path is not None and temp_index_path.exists():
            temp_index_path.unlink(missing_ok=True)
        if temp_manifest_path is not None and temp_manifest_path.exists():
            temp_manifest_path.unlink(missing_ok=True)

    manifest = load_bm25_lexical_index_manifest(resolved_manifest)
    return BM25LexicalIndexBuildResult(
        source_path=resolved_source,
        index_path=resolved_index,
        manifest_path=resolved_manifest,
        index=index,
        statistics=statistics,
        manifest=manifest,
        bm25_config=config,
    )


__all__ = [
    "BM25LexicalIndexBuildResult",
    "BM25LexicalIndexManifest",
    "LexicalIndexStatistics",
    "build_bm25_lexical_index_from_representation_dataset",
    "build_inverted_lexical_index_from_lexical_rows",
    "compute_lexical_index_statistics",
    "inverted_lexical_index_from_payload",
    "inverted_lexical_index_to_payload",
    "load_bm25_lexical_index_manifest",
    "load_inverted_lexical_index",
    "save_inverted_lexical_index",
    "validate_inverted_lexical_index_integrity",
]
