"""Generate product embeddings from product_representations.parquet (Phase 4.11)."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings  # noqa: F401
from productiq.retrieval.embedding_builder import (
    generate_product_embeddings_from_representation_dataset,
    validate_embedding_vectors,
    validate_product_embeddings_parquet,
)
from productiq.retrieval.embedding_device import (
    get_torch_runtime_info,
    resolve_embedding_device,
    runtime_info_to_dict,
)
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.embedding_schema import (
    DEFAULT_EMBEDDING_CUDA_BATCH_SIZE,
    EXPECTED_CATALOG_PRODUCT_COUNT,
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    REPRESENTATION_PARQUET_FILENAME,
)


def _default_paths(root: Path) -> tuple[Path, Path, Path]:
    processed = root / "resources" / "processed"
    return (
        processed / REPRESENTATION_PARQUET_FILENAME,
        processed / PRODUCT_EMBEDDINGS_FILENAME,
        processed / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    )


def _pin_model_revision_in_selection(root: Path, revision: str) -> None:
    selection_path = root / "resources" / "embedding" / "productiq_embedding_model_selection_v1.json"
    payload = json.loads(selection_path.read_text(encoding="utf-8"))
    primary = payload.get("primary_model")
    if not isinstance(primary, dict):
        return
    if primary.get("model_revision") == revision:
        return
    primary["model_revision"] = revision
    limitations = payload.get("limitations")
    if isinstance(limitations, list):
        payload["limitations"] = [
            item
            for item in limitations
            if "model_revision null" not in str(item).lower()
        ]
    selection_path.write_text(f"{json.dumps(payload, indent=2, sort_keys=True)}\n", encoding="utf-8")


def _load_semantic_texts(source: Path, limit: int) -> list[str]:
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(source)
    texts: list[str] = []
    for batch in parquet_file.iter_batches(batch_size=limit, columns=["semantic_text"]):
        column = batch.column(0)
        for index in range(len(column)):
            value = column[index].as_py()
            texts.append("" if value is None else str(value))
            if len(texts) >= limit:
                return texts
    return texts


def _run_gpu_smoke(source: Path, device: str, batch_size: int, allow_cpu_fallback: bool) -> int:
    resolution = resolve_embedding_device(device, allow_cpu_fallback=allow_cpu_fallback)
    runtime = get_torch_runtime_info()
    print(json.dumps({"runtime": runtime_info_to_dict(runtime), "resolution": resolution.__dict__}, indent=2))
    started = time.perf_counter()
    encoder = create_bge_small_en_v15_encoder(
        torch_device=resolution.selected,
        encode_batch_size=batch_size,
    )
    load_seconds = time.perf_counter() - started
    texts = _load_semantic_texts(source, 8)
    started = time.perf_counter()
    vectors = encoder.encode_documents(texts)
    encode_seconds = time.perf_counter() - started
    validate_embedding_vectors(vectors, expected_dimension=encoder.embedding_dimension)
    print(
        json.dumps(
            {
                "model_id": encoder.model_id,
                "model_revision": encoder.model_revision,
                "device": encoder.device,
                "device_requested": resolution.requested,
                "gpu_name": runtime.gpu_name,
                "batch_size": batch_size,
                "documents": len(texts),
                "MODEL_LOAD_SECONDS": round(load_seconds, 2),
                "ENCODE_SECONDS": round(encode_seconds, 2),
                "DOCS_PER_SECOND": round(len(texts) / encode_seconds, 2) if encode_seconds else None,
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


def _run_gpu_benchmark(source: Path, device: str, batch_size: int, allow_cpu_fallback: bool) -> int:
    resolution = resolve_embedding_device(device, allow_cpu_fallback=allow_cpu_fallback)
    runtime = get_torch_runtime_info()
    started = time.perf_counter()
    encoder = create_bge_small_en_v15_encoder(
        torch_device=resolution.selected,
        encode_batch_size=batch_size,
    )
    load_seconds = time.perf_counter() - started
    texts = _load_semantic_texts(source, 1000)
    started = time.perf_counter()
    encoder.encode_documents(texts)
    elapsed = time.perf_counter() - started
    docs_per_second = len(texts) / elapsed if elapsed > 0 else 0.0
    est_full_hours = (EXPECTED_CATALOG_PRODUCT_COUNT / len(texts)) * elapsed / 3600.0
    print(
        json.dumps(
            {
                "MODEL_LOAD_SECONDS": round(load_seconds, 2),
                "1000_DOC_SECONDS": round(elapsed, 2),
                "DOCS_PER_SECOND": round(docs_per_second, 2),
                "EST_FULL_HOURS": round(est_full_hours, 2),
                "ESTIMATE_NOTE": "approximate; based on one 1,000-document batch",
                "DEVICE": encoder.device,
                "DEVICE_REQUESTED": resolution.requested,
                "GPU_NAME": runtime.gpu_name,
                "BATCH_SIZE": batch_size,
                "TORCH_VERSION": runtime.torch_version,
                "CUDA_VERSION": runtime.cuda_version,
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ProductIQ Phase 4.11 embedding generation")
    parser.add_argument("--source", type=Path, default=None)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--manifest", type=Path, default=None)
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument(
        "--device",
        type=str,
        default="auto",
        help="cpu, cuda, or auto (prefers CUDA when available)",
    )
    parser.add_argument(
        "--allow-cpu-fallback",
        action="store_true",
        help="When --device cuda and CUDA is unavailable, run on CPU instead of failing",
    )
    parser.add_argument("--max-products", type=int, default=None)
    parser.add_argument("--publish", action=argparse.BooleanOptionalAction, default=True)
    parser.add_argument("--pin-selection-revision", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Resume from .embedding_generation checkpoint")
    parser.add_argument(
        "--fresh-run",
        action="store_true",
        help="Discard existing .embedding_generation checkpoint state before starting",
    )
    parser.add_argument(
        "--checkpoint",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Enable chunked checkpoint/resume (default: on for full catalog)",
    )
    parser.add_argument("--checkpoint-dir", type=Path, default=None)
    parser.add_argument("--chunk-size", type=int, default=10_000)
    parser.add_argument("--gpu-smoke", action="store_true", help="Run small GPU/CPU encoder smoke test and exit")
    parser.add_argument(
        "--gpu-benchmark",
        action="store_true",
        help="Benchmark 1,000 semantic_text documents and exit",
    )
    args = parser.parse_args()

    source_default, output_default, _manifest_default = _default_paths(_ROOT)
    source_path = args.source or source_default

    resolution = resolve_embedding_device(args.device, allow_cpu_fallback=args.allow_cpu_fallback)
    if args.batch_size is None:
        batch_size = DEFAULT_EMBEDDING_CUDA_BATCH_SIZE if resolution.selected == "cuda" else 64
    else:
        batch_size = args.batch_size

    if args.gpu_smoke:
        return _run_gpu_smoke(source_path, args.device, batch_size, args.allow_cpu_fallback)
    if args.gpu_benchmark:
        return _run_gpu_benchmark(source_path, args.device, batch_size, args.allow_cpu_fallback)

    pilot = args.max_products is not None
    if args.output is not None:
        output_path = args.output
    elif pilot:
        output_path = source_default.parent / "validation" / "product_embeddings_validation.parquet"
    else:
        output_path = output_default
    manifest_path = args.manifest or output_path.parent / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME
    publish = args.publish and not pilot
    use_checkpoint = args.checkpoint if args.checkpoint is not None else (args.resume or not pilot)

    runtime = get_torch_runtime_info()
    print(json.dumps({"runtime": runtime_info_to_dict(runtime), "device_resolution": resolution.__dict__}, indent=2))
    print(f"Source: {source_path}", flush=True)
    print(f"Output: {output_path}", flush=True)
    print(f"Selected device: {resolution.selected}, batch_size: {batch_size}", flush=True)
    if resolution.fell_back_to_cpu:
        print("WARNING: CUDA was requested but execution fell back to CPU (--allow-cpu-fallback).", flush=True)
    if pilot:
        print(f"Validation max_products: {args.max_products}", flush=True)
    else:
        print(f"Full catalog target rows: {EXPECTED_CATALOG_PRODUCT_COUNT}", flush=True)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = generate_product_embeddings_from_representation_dataset(
        source_path,
        embeddings_path=output_path,
        manifest_path=manifest_path,
        batch_size=batch_size,
        device=args.device,
        allow_cpu_fallback=args.allow_cpu_fallback,
        max_products=args.max_products,
        publish=publish,
        use_checkpoint=use_checkpoint,
        resume=args.resume,
        fresh_run=args.fresh_run,
        checkpoint_dir=args.checkpoint_dir,
        chunk_size=args.chunk_size,
    )
    validate_product_embeddings_parquet(
        result.embeddings_path,
        expected_row_count=result.product_count,
        expected_dimension=result.manifest.embedding_dimension,
        manifest_path=result.manifest_path,
    )
    if args.pin_selection_revision:
        _pin_model_revision_in_selection(_ROOT, result.manifest.model_revision)
    print(
        json.dumps(
            {
                "product_count": result.product_count,
                "duration_seconds": round(result.duration_seconds, 3),
                "throughput_products_per_second": round(result.throughput_products_per_second, 3),
                "model_id": result.manifest.model_id,
                "model_revision": result.manifest.model_revision,
                "device": result.manifest.device,
                "device_requested": result.manifest.device_requested,
                "gpu_name": result.manifest.gpu_name,
                "checksum": result.manifest.checksum,
                "embeddings_path": str(result.embeddings_path),
                "manifest_path": str(result.manifest_path),
            },
            indent=2,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
