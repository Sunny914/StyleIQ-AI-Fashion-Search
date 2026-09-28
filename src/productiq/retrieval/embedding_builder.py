"""Build, validate, and load product embedding artifacts (Phase 4.11)."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyarrow as pa  # type: ignore[import-untyped]
import pyarrow.parquet as pq  # type: ignore[import-untyped]
from numpy.typing import NDArray
from pydantic import BaseModel, ConfigDict, Field

from productiq.exceptions.base import SemanticRetrievalError
from productiq.representation.dataset import load_representation_dataset_manifest
from productiq.representation.dataset_schema import (
    REPRESENTATION_MANIFEST_FILENAME,
    REPRESENTATION_PARQUET_FILENAME,
)
from productiq.retrieval.embedding_checkpoint import (
    DEFAULT_EMBEDDING_CHUNK_SIZE,
    EmbeddingRunConfiguration,
    assert_checkpoint_compatible,
    build_run_configuration,
    checkpoint_path,
    chunk_file_path,
    chunks_dir,
    default_checkpoint_dir,
    list_chunk_files,
    load_checkpoint,
    new_checkpoint,
    save_checkpoint,
)
from productiq.retrieval.embedding_device import (
    ResolvedEmbeddingDevice,
    get_torch_runtime_info,
    resolve_embedding_device,
)
from productiq.retrieval.embedding_encoder import (
    DocumentEmbeddingEncoder,
    create_bge_small_en_v15_encoder,
)
from productiq.retrieval.embedding_schema import (
    BGE_QUERY_INSTRUCTION,
    CHECKSUM_ALGORITHM,
    DEFAULT_EMBEDDING_BATCH_SIZE,
    DEFAULT_EMBEDDING_READ_BATCH_SIZE,
    DOCUMENT_ENCODING_RULE,
    EMBEDDING_INPUT_PRODUCT_ID_COLUMN,
    EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN,
    EMBEDDING_OUTPUT_COLUMN,
    NORMALIZATION_L2,
    PRODUCT_EMBEDDINGS_DATASET_NAME,
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_FORMAT,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    PRODUCT_EMBEDDINGS_PIPELINE_PHASE,
    PRODUCT_EMBEDDINGS_SCHEMA_VERSION,
    REPRESENTATION_DATASET_NAME,
    SIMILARITY_METRIC_COSINE,
    UNIT_NORM_TOLERANCE,
)

PARQUET_ENGINE: Literal["pyarrow"] = "pyarrow"


class ProductEmbeddingManifest(BaseModel):
    """Manifest for persisted product embedding parquet."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_name: str
    format: str
    schema_version: str
    output_filename: str
    checksum: str
    checksum_algorithm: str
    pipeline_phase: str
    source_representation_dataset_name: str
    source_representation_filename: str
    source_representation_checksum: str | None = None
    source_representation_row_count: int = Field(ge=0)
    embedding_row_count: int = Field(ge=0)
    product_count: int = Field(ge=0)
    model_id: str
    model_revision: str
    embedding_dimension: int = Field(gt=0)
    similarity_metric: str
    normalization_method: str
    query_instruction: str
    document_encoding_rule: str
    batch_size: int = Field(gt=0)
    device: str
    device_requested: str | None = None
    torch_version: str | None = None
    cuda_version: str | None = None
    gpu_name: str | None = None
    sentence_transformers_version: str
    generation_timestamp_utc: str
    generation_duration_seconds: float = Field(ge=0.0)
    throughput_products_per_second: float = Field(ge=0.0)
    pilot_mode: bool = False
    max_products_limit: int | None = None


@dataclass(frozen=True)
class ProductEmbeddingBuildResult:
    source_path: Path
    embeddings_path: Path
    manifest_path: Path
    manifest: ProductEmbeddingManifest
    product_count: int
    duration_seconds: float
    throughput_products_per_second: float


@dataclass(frozen=True)
class EmbeddingGenerationStats:
    product_count: int
    duration_seconds: float
    throughput_products_per_second: float
    device: str
    batch_size: int
    embedding_dimension: int


def _checksum_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as artifact:
        for chunk in iter(lambda: artifact.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _serialize_manifest(payload: dict[str, Any]) -> str:
    return f"{json.dumps(payload, indent=2, sort_keys=True)}\n"


def _normalize_product_id(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        msg = "product_id must not be null"
        raise SemanticRetrievalError(msg)
    product_id = str(value).strip()
    if not product_id:
        msg = "product_id must not be empty"
        raise SemanticRetrievalError(msg)
    return product_id


def _normalize_semantic_cell(value: object) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    return str(value)


def _embedding_list_type(embedding_dimension: int) -> pa.DataType:
    return pa.list_(pa.float32(), list_size=embedding_dimension)


def _embedding_parquet_schema(embedding_dimension: int) -> pa.Schema:
    list_type = _embedding_list_type(embedding_dimension)
    return pa.schema(
        [
            (EMBEDDING_INPUT_PRODUCT_ID_COLUMN, pa.string()),
            (EMBEDDING_OUTPUT_COLUMN, list_type),
        ]
    )


def validate_embedding_vectors(
    vectors: NDArray[np.float32],
    *,
    expected_dimension: int,
    unit_norm_tolerance: float = UNIT_NORM_TOLERANCE,
) -> None:
    if vectors.ndim != 2:
        msg = "embedding matrix must be two-dimensional"
        raise SemanticRetrievalError(msg)
    if vectors.shape[1] != expected_dimension:
        msg = f"embedding dimension must be {expected_dimension}"
        raise SemanticRetrievalError(msg)
    if not np.all(np.isfinite(vectors)):
        msg = "embeddings contain non-finite values"
        raise SemanticRetrievalError(msg)
    norms = np.linalg.norm(vectors, axis=1)
    if np.any(norms == 0.0):
        msg = "embeddings must not include zero-norm vectors"
        raise SemanticRetrievalError(msg)
    if not np.allclose(norms, 1.0, atol=unit_norm_tolerance, rtol=0.0):
        msg = "embeddings must be approximately L2 unit norm after normalization"
        raise SemanticRetrievalError(msg)


def validate_embeddings_parquet_integrity(
    path: Path,
    *,
    expected_row_count: int | None = None,
    expected_dimension: int,
    unit_norm_tolerance: float = UNIT_NORM_TOLERANCE,
) -> int:
    """Validate embedding parquet rows, IDs, dimensions, and unit norms."""
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"product embeddings artifact not found: {resolved}"
        raise SemanticRetrievalError(msg)
    parquet_file = pq.ParquetFile(resolved)
    if EMBEDDING_INPUT_PRODUCT_ID_COLUMN not in parquet_file.schema_arrow.names:
        msg = "embeddings parquet missing product_id column"
        raise SemanticRetrievalError(msg)
    if EMBEDDING_OUTPUT_COLUMN not in parquet_file.schema_arrow.names:
        msg = "embeddings parquet missing embedding column"
        raise SemanticRetrievalError(msg)

    seen_ids: set[str] = set()
    row_count = 0
    for batch in parquet_file.iter_batches(batch_size=DEFAULT_EMBEDDING_READ_BATCH_SIZE):
        chunk = batch.to_pandas()
        for product_id_raw, embedding_raw in zip(
            chunk[EMBEDDING_INPUT_PRODUCT_ID_COLUMN],
            chunk[EMBEDDING_OUTPUT_COLUMN],
            strict=True,
        ):
            product_id = _normalize_product_id(product_id_raw)
            if product_id in seen_ids:
                msg = f"duplicate product_id in embeddings artifact: {product_id}"
                raise SemanticRetrievalError(msg)
            seen_ids.add(product_id)
            vector = np.asarray(embedding_raw, dtype=np.float32)
            validate_embedding_vectors(vector.reshape(1, -1), expected_dimension=expected_dimension)
            row_count += 1

    if expected_row_count is not None and row_count != expected_row_count:
        msg = f"expected {expected_row_count} embedding rows, found {row_count}"
        raise SemanticRetrievalError(msg)
    if len(seen_ids) != row_count:
        msg = "unique product_id count mismatch"
        raise SemanticRetrievalError(msg)
    return row_count


def _iter_product_ids_from_parquet(path: Path) -> list[str]:
    resolved = Path(path)
    parquet_file = pq.ParquetFile(resolved)
    ordered_ids: list[str] = []
    for batch in parquet_file.iter_batches(
        batch_size=DEFAULT_EMBEDDING_READ_BATCH_SIZE,
        columns=[EMBEDDING_INPUT_PRODUCT_ID_COLUMN],
    ):
        chunk = batch.to_pandas()
        for product_id_raw in chunk[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]:
            ordered_ids.append(_normalize_product_id(product_id_raw))
    return ordered_ids


def validate_embedding_product_ids_match_representation(
    embeddings_path: Path,
    source_path: Path,
) -> None:
    """Ensure embedding artifact product IDs match representation dataset order and set."""
    source_ids = _iter_product_ids_from_parquet(source_path)
    embedding_ids = _iter_product_ids_from_parquet(embeddings_path)
    if len(source_ids) != len(embedding_ids):
        msg = (
            f"embedding row count {len(embedding_ids)} != "
            f"representation row count {len(source_ids)}"
        )
        raise SemanticRetrievalError(msg)
    if len(set(source_ids)) != len(source_ids):
        msg = "representation dataset contains duplicate product_id values"
        raise SemanticRetrievalError(msg)
    if source_ids != embedding_ids:
        msg = "embedding product_id sequence does not match representation dataset"
        raise SemanticRetrievalError(msg)


def validate_product_embeddings_parquet(
    path: Path,
    *,
    expected_row_count: int | None = None,
    expected_dimension: int,
    expected_source_checksum: str | None = None,
    manifest_path: Path | None = None,
) -> ProductEmbeddingManifest:
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"product embeddings artifact not found: {resolved}"
        raise SemanticRetrievalError(msg)
    manifest = load_product_embeddings_manifest(
        manifest_path or resolved.parent / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME
    )
    if expected_source_checksum and manifest.source_representation_checksum != expected_source_checksum:
        msg = "embedding manifest source checksum does not match expected representation checksum"
        raise SemanticRetrievalError(msg)
    row_count = validate_embeddings_parquet_integrity(
        resolved,
        expected_row_count=expected_row_count or manifest.embedding_row_count,
        expected_dimension=expected_dimension,
    )
    if row_count != manifest.embedding_row_count:
        msg = "embedding row count does not match manifest"
        raise SemanticRetrievalError(msg)
    reloaded_checksum = _checksum_file(resolved)
    if reloaded_checksum != manifest.checksum:
        msg = "embedding artifact checksum does not match manifest"
        raise SemanticRetrievalError(msg)
    return manifest


def load_product_embeddings_manifest(path: Path) -> ProductEmbeddingManifest:
    manifest_path = Path(path)
    try:
        payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"product embeddings manifest is not valid JSON: {manifest_path}"
        raise SemanticRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "product embeddings manifest must be a JSON object"
        raise SemanticRetrievalError(msg)
    return ProductEmbeddingManifest.model_validate(payload)


def load_product_embeddings_dataframe(path: Path) -> pd.DataFrame:
    resolved = Path(path)
    frame = pd.read_parquet(resolved, engine=PARQUET_ENGINE)
    return frame


def generate_product_embeddings_from_representation_dataset(
    source_path: Path,
    *,
    embeddings_path: Path | None = None,
    manifest_path: Path | None = None,
    encoder: DocumentEmbeddingEncoder | None = None,
    batch_size: int = DEFAULT_EMBEDDING_BATCH_SIZE,
    read_batch_size: int = DEFAULT_EMBEDDING_READ_BATCH_SIZE,
    device: str | None = None,
    allow_cpu_fallback: bool = False,
    max_products: int | None = None,
    publish: bool = True,
    use_checkpoint: bool = False,
    resume: bool = False,
    fresh_run: bool = False,
    checkpoint_dir: Path | None = None,
    chunk_size: int = DEFAULT_EMBEDDING_CHUNK_SIZE,
) -> ProductEmbeddingBuildResult:
    """Encode ``semantic_text`` for products and publish parquet + manifest."""
    resolved_source = Path(source_path)
    resolved_embeddings = (
        Path(embeddings_path)
        if embeddings_path is not None
        else resolved_source.parent / PRODUCT_EMBEDDINGS_FILENAME
    )
    resolved_manifest = (
        Path(manifest_path)
        if manifest_path is not None
        else resolved_source.parent / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME
    )
    device_resolution = resolve_embedding_device(device, allow_cpu_fallback=allow_cpu_fallback)
    runtime_info = get_torch_runtime_info()
    active_encoder = encoder or create_bge_small_en_v15_encoder(
        torch_device=device_resolution.selected,
        encode_batch_size=batch_size,
    )
    source_manifest = _load_source_representation_manifest(resolved_source)
    expected_source_rows = (
        int(source_manifest["row_count"]) if source_manifest and "row_count" in source_manifest else None
    )

    resolved_checkpoint_dir = (
        Path(checkpoint_dir)
        if checkpoint_dir is not None
        else default_checkpoint_dir(resolved_source.parent)
    )
    checkpoint_enabled = resume or use_checkpoint or (max_products is None and expected_source_rows is not None)
    if fresh_run and resolved_checkpoint_dir.exists():
        shutil.rmtree(resolved_checkpoint_dir, ignore_errors=True)

    started = time.perf_counter()
    temp_parquet: Path | None = None
    temp_manifest: Path | None = None
    product_count = 0
    run_config: EmbeddingRunConfiguration | None = None
    try:
        if checkpoint_enabled:
            target_count = max_products if max_products is not None else expected_source_rows
            if target_count is None:
                msg = "target product count could not be determined from source manifest"
                raise SemanticRetrievalError(msg)
            run_config = build_run_configuration(
                source_manifest=source_manifest,
                target_product_count=int(target_count),
                model_id=active_encoder.model_id,
                model_revision=active_encoder.model_revision,
                embedding_dimension=active_encoder.embedding_dimension,
                batch_size=batch_size,
                device=active_encoder.device,
                chunk_size=chunk_size,
            )
            temp_parquet = _write_embeddings_with_checkpoint(
                resolved_source,
                encoder=active_encoder,
                batch_size=batch_size,
                read_batch_size=read_batch_size,
                max_products=max_products,
                checkpoint_dir=resolved_checkpoint_dir,
                run_config=run_config,
                resume=resume,
            )
        else:
            temp_parquet = _write_embeddings_streaming(
                resolved_source,
                encoder=active_encoder,
                batch_size=batch_size,
                read_batch_size=read_batch_size,
                max_products=max_products,
            )
        product_count = _count_parquet_rows(temp_parquet)
        if (
            expected_source_rows is not None
            and max_products is None
            and product_count != expected_source_rows
        ):
            msg = (
                f"embedding row count {product_count} != "
                f"source representation row count {expected_source_rows}"
            )
            raise SemanticRetrievalError(msg)
        validate_embeddings_parquet_integrity(
            temp_parquet,
            expected_row_count=product_count,
            expected_dimension=active_encoder.embedding_dimension,
        )
        if max_products is None:
            validate_embedding_product_ids_match_representation(temp_parquet, resolved_source)
        duration = time.perf_counter() - started
        throughput = product_count / duration if duration > 0 else 0.0
        checksum = _checksum_file(temp_parquet)
        manifest_payload = _build_manifest_payload(
            checksum=checksum,
            source_manifest=source_manifest,
            encoder=active_encoder,
            product_count=product_count,
            batch_size=batch_size,
            duration_seconds=duration,
            throughput=throughput,
            pilot_mode=max_products is not None,
            max_products_limit=max_products,
            device_resolution=device_resolution,
            runtime_info=runtime_info,
        )
        temp_manifest = _write_manifest_temp(resolved_manifest.parent, manifest_payload)
        if publish:
            _publish_embedding_artifacts(
                temp_parquet_path=temp_parquet,
                temp_manifest_path=temp_manifest,
                final_parquet_path=resolved_embeddings,
                final_manifest_path=resolved_manifest,
            )
            temp_parquet = None
            temp_manifest = None
        else:
            os.replace(temp_parquet, resolved_embeddings)
            temp_parquet = None
            os.replace(temp_manifest, resolved_manifest)
            temp_manifest = None
        if checkpoint_enabled and run_config is not None:
            _mark_checkpoint_complete(resolved_checkpoint_dir, run_config, product_count)
        manifest = ProductEmbeddingManifest.model_validate(manifest_payload)
        return ProductEmbeddingBuildResult(
            source_path=resolved_source,
            embeddings_path=resolved_embeddings,
            manifest_path=resolved_manifest,
            manifest=manifest,
            product_count=product_count,
            duration_seconds=duration,
            throughput_products_per_second=throughput,
        )
    finally:
        if temp_parquet is not None and temp_parquet.exists():
            temp_parquet.unlink(missing_ok=True)
        if temp_manifest is not None and temp_manifest.exists():
            temp_manifest.unlink(missing_ok=True)


def _load_completed_product_ids_from_chunks(chunk_paths: list[Path]) -> tuple[set[str], int, str | None]:
    completed_ids: set[str] = set()
    last_product_id: str | None = None
    total = 0
    for chunk in chunk_paths:
        parquet_file = pq.ParquetFile(chunk)
        for batch in parquet_file.iter_batches(
            batch_size=DEFAULT_EMBEDDING_READ_BATCH_SIZE,
            columns=[EMBEDDING_INPUT_PRODUCT_ID_COLUMN],
        ):
            frame = batch.to_pandas()
            for product_id_raw in frame[EMBEDDING_INPUT_PRODUCT_ID_COLUMN]:
                product_id = _normalize_product_id(product_id_raw)
                if product_id in completed_ids:
                    msg = f"duplicate product_id in checkpoint chunk data: {product_id}"
                    raise SemanticRetrievalError(msg)
                completed_ids.add(product_id)
                last_product_id = product_id
                total += 1
    return completed_ids, total, last_product_id


def _merge_embedding_chunk_files(
    chunk_paths: list[Path],
    output_path: Path,
    *,
    embedding_dimension: int,
) -> None:
    schema = _embedding_parquet_schema(embedding_dimension)
    writer = pq.ParquetWriter(output_path, schema=schema, compression="zstd")
    try:
        for chunk in chunk_paths:
            table = pq.read_table(chunk)
            writer.write_table(table)
    finally:
        writer.close()


def _mark_checkpoint_complete(
    checkpoint_dir: Path,
    run_config: EmbeddingRunConfiguration,
    product_count: int,
) -> None:
    checkpoint = new_checkpoint(
        run_config,
        completed_product_count=product_count,
        chunk_file_count=len(list_chunk_files(checkpoint_dir)),
        status="complete",
    )
    save_checkpoint(checkpoint_path(checkpoint_dir), checkpoint)


def _write_embeddings_with_checkpoint(
    source_path: Path,
    *,
    encoder: DocumentEmbeddingEncoder,
    batch_size: int,
    read_batch_size: int,
    max_products: int | None,
    checkpoint_dir: Path,
    run_config: EmbeddingRunConfiguration,
    resume: bool,
) -> Path:
    resolved = Path(source_path)
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    chunks_dir(checkpoint_dir).mkdir(parents=True, exist_ok=True)
    ckpt_file = checkpoint_path(checkpoint_dir)
    existing_chunks = list_chunk_files(checkpoint_dir)
    completed_ids: set[str] = set()
    if resume:
        if not ckpt_file.is_file():
            msg = f"cannot resume: checkpoint file missing at {ckpt_file}"
            raise SemanticRetrievalError(msg)
        loaded = load_checkpoint(ckpt_file)
        assert_checkpoint_compatible(loaded, run_config)
        if loaded.status == "complete":
            msg = "checkpoint is already marked complete; remove checkpoint dir or use --fresh-run"
            raise SemanticRetrievalError(msg)
        completed_ids, _, _ = _load_completed_product_ids_from_chunks(existing_chunks)
    elif ckpt_file.is_file() or existing_chunks:
        msg = (
            "in-progress checkpoint data exists; pass --resume to continue or --fresh-run "
            "to discard checkpoint state in .embedding_generation"
        )
        raise SemanticRetrievalError(msg)

    parent = resolved.parent
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{PRODUCT_EMBEDDINGS_FILENAME}.",
        suffix=".parquet.tmp",
    ) as temp_file:
        merged_temp = Path(temp_file.name)

    total_written = len(completed_ids)
    chunk_index = len(existing_chunks)
    current_chunk_rows = 0
    chunk_writer: pq.ParquetWriter | None = None
    schema = _embedding_parquet_schema(encoder.embedding_dimension)
    last_written_product_id: str | None = None
    encode_buffer_ids: list[str] = []
    encode_buffer_texts: list[str] = []

    def open_chunk_writer(index: int) -> pq.ParquetWriter:
        path = chunk_file_path(checkpoint_dir, index)
        return pq.ParquetWriter(path, schema=schema, compression="zstd")

    def finalize_chunk() -> None:
        nonlocal chunk_writer, chunk_index, current_chunk_rows
        if chunk_writer is None:
            return
        chunk_writer.close()
        chunk_writer = None
        chunk_index += 1
        current_chunk_rows = 0
        save_checkpoint(
            ckpt_file,
            new_checkpoint(
                run_config,
                completed_product_count=total_written,
                last_product_id=last_written_product_id,
                chunk_file_count=chunk_index,
            ),
        )

    def flush_encode_buffer() -> None:
        nonlocal total_written, chunk_writer, current_chunk_rows, last_written_product_id
        if not encode_buffer_ids:
            return
        if max_products is not None:
            remaining = max_products - total_written
            if remaining <= 0:
                encode_buffer_ids.clear()
                encode_buffer_texts.clear()
                return
            if len(encode_buffer_ids) > remaining:
                encode_buffer_ids[:] = encode_buffer_ids[:remaining]
                encode_buffer_texts[:] = encode_buffer_texts[:remaining]
        vectors = encoder.encode_documents(encode_buffer_texts)
        validate_embedding_vectors(vectors, expected_dimension=encoder.embedding_dimension)
        list_type = _embedding_list_type(encoder.embedding_dimension)
        table = pa.Table.from_pydict(
            {
                EMBEDDING_INPUT_PRODUCT_ID_COLUMN: encode_buffer_ids,
                EMBEDDING_OUTPUT_COLUMN: pa.array(vectors.tolist(), type=list_type),
            },
            schema=schema,
        )
        if chunk_writer is None:
            chunk_writer = open_chunk_writer(chunk_index)
            current_chunk_rows = 0
        chunk_writer.write_table(table)
        current_chunk_rows += len(encode_buffer_ids)
        total_written += len(encode_buffer_ids)
        last_written_product_id = encode_buffer_ids[-1]
        encode_buffer_ids.clear()
        encode_buffer_texts.clear()
        if current_chunk_rows >= run_config.chunk_size:
            finalize_chunk()

    parquet_file = pq.ParquetFile(resolved)
    try:
        for batch in parquet_file.iter_batches(
            batch_size=read_batch_size,
            columns=[EMBEDDING_INPUT_PRODUCT_ID_COLUMN, EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN],
        ):
            chunk = batch.to_pandas()
            for record in chunk.to_dict(orient="records"):
                if max_products is not None and total_written >= max_products:
                    break
                product_id = _normalize_product_id(record[EMBEDDING_INPUT_PRODUCT_ID_COLUMN])
                if product_id in completed_ids:
                    continue
                completed_ids.add(product_id)
                semantic_text = _normalize_semantic_cell(record[EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN])
                encode_buffer_ids.append(product_id)
                encode_buffer_texts.append(semantic_text)
                if len(encode_buffer_ids) >= batch_size:
                    flush_encode_buffer()
            if max_products is not None and total_written >= max_products:
                break
        flush_encode_buffer()
        if chunk_writer is not None:
            chunk_writer.close()
            chunk_writer = None
            save_checkpoint(
                ckpt_file,
                new_checkpoint(
                    run_config,
                    completed_product_count=total_written,
                    last_product_id=last_written_product_id,
                    chunk_file_count=chunk_index + 1,
                ),
            )
    except Exception:
        if chunk_writer is not None:
            chunk_writer.close()
        raise

    expected_rows = max_products if max_products is not None else run_config.target_product_count
    if total_written != expected_rows:
        msg = f"checkpointed generation wrote {total_written} rows, expected {expected_rows}"
        raise SemanticRetrievalError(msg)

    all_chunks = list_chunk_files(checkpoint_dir)
    _merge_embedding_chunk_files(all_chunks, merged_temp, embedding_dimension=encoder.embedding_dimension)
    return merged_temp


def _write_embeddings_streaming(
    source_path: Path,
    *,
    encoder: DocumentEmbeddingEncoder,
    batch_size: int,
    read_batch_size: int,
    max_products: int | None,
) -> Path:
    resolved = Path(source_path)
    if not resolved.is_file():
        msg = f"Representation dataset not found: {resolved}"
        raise SemanticRetrievalError(msg)
    parquet_file = pq.ParquetFile(resolved)
    schema = _embedding_parquet_schema(encoder.embedding_dimension)
    parent = resolved.parent
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{PRODUCT_EMBEDDINGS_FILENAME}.",
        suffix=".parquet.tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
    writer = pq.ParquetWriter(temp_path, schema=schema, compression="zstd")
    seen_ids: set[str] = set()
    encode_buffer_ids: list[str] = []
    encode_buffer_texts: list[str] = []
    total_written = 0

    def flush_encode_buffer() -> None:
        nonlocal total_written
        if not encode_buffer_ids:
            return
        if max_products is not None:
            remaining = max_products - total_written
            if remaining <= 0:
                encode_buffer_ids.clear()
                encode_buffer_texts.clear()
                return
            if len(encode_buffer_ids) > remaining:
                encode_buffer_ids[:] = encode_buffer_ids[:remaining]
                encode_buffer_texts[:] = encode_buffer_texts[:remaining]
        vectors = encoder.encode_documents(encode_buffer_texts)
        validate_embedding_vectors(vectors, expected_dimension=encoder.embedding_dimension)
        list_type = _embedding_list_type(encoder.embedding_dimension)
        table = pa.Table.from_pydict(
            {
                EMBEDDING_INPUT_PRODUCT_ID_COLUMN: encode_buffer_ids,
                EMBEDDING_OUTPUT_COLUMN: pa.array(vectors.tolist(), type=list_type),
            },
            schema=schema,
        )
        writer.write_table(table)
        total_written += len(encode_buffer_ids)
        encode_buffer_ids.clear()
        encode_buffer_texts.clear()

    try:
        for batch in parquet_file.iter_batches(
            batch_size=read_batch_size,
            columns=[EMBEDDING_INPUT_PRODUCT_ID_COLUMN, EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN],
        ):
            chunk = batch.to_pandas()
            for record in chunk.to_dict(orient="records"):
                if max_products is not None and total_written >= max_products:
                    break
                product_id = _normalize_product_id(record[EMBEDDING_INPUT_PRODUCT_ID_COLUMN])
                if product_id in seen_ids:
                    msg = f"duplicate product_id in representation dataset: {product_id}"
                    raise SemanticRetrievalError(msg)
                seen_ids.add(product_id)
                semantic_text = _normalize_semantic_cell(record[EMBEDDING_INPUT_SEMANTIC_TEXT_COLUMN])
                encode_buffer_ids.append(product_id)
                encode_buffer_texts.append(semantic_text)
                if len(encode_buffer_ids) >= batch_size:
                    flush_encode_buffer()
            if max_products is not None and total_written >= max_products:
                break
        flush_encode_buffer()
    finally:
        writer.close()
    return temp_path


def _count_parquet_rows(path: Path) -> int:
    return int(pq.ParquetFile(path).metadata.num_rows)


def _load_source_representation_manifest(source_path: Path) -> dict[str, Any] | None:
    manifest_path = source_path.parent / REPRESENTATION_MANIFEST_FILENAME
    if not manifest_path.is_file():
        return None
    return load_representation_dataset_manifest(manifest_path)


def _build_manifest_payload(
    *,
    checksum: str,
    source_manifest: dict[str, Any] | None,
    encoder: DocumentEmbeddingEncoder,
    product_count: int,
    batch_size: int,
    duration_seconds: float,
    throughput: float,
    pilot_mode: bool,
    max_products_limit: int | None,
    device_resolution: ResolvedEmbeddingDevice | None = None,
    runtime_info: Any | None = None,
) -> dict[str, Any]:
    source_row_count = int(source_manifest["row_count"]) if source_manifest and "row_count" in source_manifest else 0
    torch_version: str | None = None
    cuda_version: str | None = None
    gpu_name: str | None = None
    device_requested: str | None = None
    if runtime_info is not None:
        torch_version = runtime_info.torch_version
        cuda_version = runtime_info.cuda_version
        gpu_name = runtime_info.gpu_name
    if device_resolution is not None:
        device_requested = device_resolution.requested
    return {
        "artifact_name": PRODUCT_EMBEDDINGS_DATASET_NAME,
        "format": PRODUCT_EMBEDDINGS_FORMAT,
        "schema_version": PRODUCT_EMBEDDINGS_SCHEMA_VERSION,
        "output_filename": PRODUCT_EMBEDDINGS_FILENAME,
        "checksum": checksum,
        "checksum_algorithm": CHECKSUM_ALGORITHM,
        "pipeline_phase": PRODUCT_EMBEDDINGS_PIPELINE_PHASE,
        "source_representation_dataset_name": REPRESENTATION_DATASET_NAME,
        "source_representation_filename": REPRESENTATION_PARQUET_FILENAME,
        "source_representation_checksum": source_manifest.get("checksum") if source_manifest else None,
        "source_representation_row_count": source_row_count,
        "embedding_row_count": product_count,
        "product_count": product_count,
        "model_id": encoder.model_id,
        "model_revision": encoder.model_revision,
        "embedding_dimension": encoder.embedding_dimension,
        "similarity_metric": SIMILARITY_METRIC_COSINE,
        "normalization_method": NORMALIZATION_L2,
        "query_instruction": BGE_QUERY_INSTRUCTION,
        "document_encoding_rule": DOCUMENT_ENCODING_RULE,
        "batch_size": batch_size,
        "device": encoder.device,
        "device_requested": device_requested,
        "torch_version": torch_version,
        "cuda_version": cuda_version,
        "gpu_name": gpu_name,
        "sentence_transformers_version": encoder.library_version,
        "generation_timestamp_utc": datetime.now(tz=UTC).isoformat(),
        "generation_duration_seconds": duration_seconds,
        "throughput_products_per_second": throughput,
        "pilot_mode": pilot_mode,
        "max_products_limit": max_products_limit,
    }


def _write_manifest_temp(parent: Path, payload: dict[str, Any]) -> Path:
    parent.mkdir(parents=True, exist_ok=True)
    with NamedTemporaryFile(
        delete=False,
        dir=parent,
        prefix=f".{PRODUCT_EMBEDDINGS_MANIFEST_FILENAME}.",
        suffix=".json.tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(_serialize_manifest(payload).encode("utf-8"))
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


def _publish_embedding_artifacts(
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
            _restore_aside(final_parquet_path, parquet_backup)
        else:
            _restore_aside(final_parquet_path, parquet_backup)
        _restore_aside(final_manifest_path, manifest_backup)
        raise
    finally:
        if parquet_backup is not None and parquet_backup.exists():
            parquet_backup.unlink()
        if manifest_backup is not None and manifest_backup.exists():
            manifest_backup.unlink()


__all__ = [
    "EmbeddingGenerationStats",
    "ProductEmbeddingBuildResult",
    "ProductEmbeddingManifest",
    "generate_product_embeddings_from_representation_dataset",
    "load_product_embeddings_dataframe",
    "load_product_embeddings_manifest",
    "validate_embedding_product_ids_match_representation",
    "validate_embedding_vectors",
    "validate_embeddings_parquet_integrity",
    "validate_product_embeddings_parquet",
]
