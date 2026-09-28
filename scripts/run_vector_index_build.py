"""Build PostgreSQL/pgvector HNSW index from product_embeddings.parquet (Phase 4.12)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.retrieval.embedding_schema import (
    PRODUCT_EMBEDDINGS_FILENAME,
    PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
)
from productiq.retrieval.pgvector_search import benchmark_vector_search
from productiq.retrieval.vector_index_builder import (
    build_product_vector_index,
    load_product_vector_index_manifest,
    validate_product_vector_index_state,
)
from productiq.retrieval.vector_index_loader import validate_embedding_artifact_for_vector_index


def _default_paths(root: Path) -> tuple[Path, Path]:
    processed = root / "resources" / "processed"
    return (
        processed / PRODUCT_EMBEDDINGS_FILENAME,
        processed / PRODUCT_EMBEDDINGS_MANIFEST_FILENAME,
    )


def _read_first_embedding_vector(embeddings_path: Path) -> tuple[float, ...]:
    import pyarrow.parquet as pq

    parquet_file = pq.ParquetFile(embeddings_path)
    batch = next(parquet_file.iter_batches(batch_size=1))
    column = batch.column(batch.schema.get_field_index("embedding"))
    values = column[0].as_py()
    return tuple(float(value) for value in values)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ProductIQ pgvector HNSW index (Phase 4.12).")
    parser.add_argument("--root", type=Path, default=_ROOT, help="Repository root")
    parser.add_argument("--embeddings", type=Path, default=None, help="Embedding parquet path")
    parser.add_argument("--manifest", type=Path, default=None, help="Embedding manifest path")
    parser.add_argument("--output-dir", type=Path, default=None, help="Vector index manifest output dir")
    parser.add_argument("--chunk-size", type=int, default=5_000, help="Parquet load batch size")
    parser.add_argument("--max-rows", type=int, default=None, help="Load only the first N vectors")
    parser.add_argument(
        "--rebuild-hnsw",
        action="store_true",
        help="Drop and recreate the HNSW index",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="Validate embedding artifact metadata without touching PostgreSQL",
    )
    parser.add_argument(
        "--skip-load",
        action="store_true",
        help="Skip vector load (index/validate only)",
    )
    parser.add_argument(
        "--skip-index",
        action="store_true",
        help="Skip HNSW index creation",
    )
    parser.add_argument(
        "--benchmark-search",
        action="store_true",
        help="Run lightweight vector search latency samples after build",
    )
    parser.add_argument(
        "--allow-unofficial-artifact",
        action="store_true",
        help="Do not require the official Phase 4.11 artifact checksum",
    )
    args = parser.parse_args(argv)

    default_embeddings, default_manifest = _default_paths(args.root)
    embeddings_path = args.embeddings or default_embeddings
    manifest_path = args.manifest or default_manifest

    if args.validate_only:
        manifest = validate_embedding_artifact_for_vector_index(
            embeddings_path,
            manifest_path=manifest_path,
            enforce_official_checksums=not args.allow_unofficial_artifact,
        )
        print(json.dumps(manifest.model_dump(mode="json"), indent=2))
        return 0

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    try:
        result = build_product_vector_index(
            engine,
            embeddings_path,
            manifest_path=manifest_path,
            output_dir=args.output_dir,
            chunk_size=args.chunk_size,
            max_rows=args.max_rows,
            rebuild_hnsw=args.rebuild_hnsw,
            enforce_official_checksums=not args.allow_unofficial_artifact,
            skip_load=args.skip_load,
            skip_index=args.skip_index,
        )
        validation = validate_product_vector_index_state(
            engine,
            expected_product_count=result.vector_index_manifest.vectors_loaded,
        )
        payload = {
            "embeddings_path": str(result.embeddings_path),
            "manifest_path": str(result.manifest_path),
            "vectors_loaded": result.vectors_in_database,
            "catalog_product_count": result.catalog_product_count,
            "hnsw_index_present": result.hnsw_index_present,
            "load_duration_seconds": result.vector_index_manifest.load_duration_seconds,
            "index_build_duration_seconds": result.vector_index_manifest.index_build_duration_seconds,
            "total_build_duration_seconds": result.vector_index_manifest.total_build_duration_seconds,
            "index_size_bytes": result.vector_index_manifest.index_size_bytes,
            "validation": {
                "vectors_with_embeddings": validation.vectors_with_embeddings,
                "hnsw_operator_class": validation.hnsw_operator_class,
                "vector_dimension": validation.vector_dimension,
            },
        }
        if args.benchmark_search:
            query_vector = _read_first_embedding_vector(embeddings_path)
            samples = benchmark_vector_search(engine, query_vector)
            payload["search_baseline"] = [
                {
                    "top_k": sample.top_k,
                    "duration_seconds": sample.duration_seconds,
                    "hit_count": sample.hit_count,
                }
                for sample in samples
            ]
        print(json.dumps(payload, indent=2))
        print(result.load_report.summary())
        published = load_product_vector_index_manifest(result.manifest_path)
        print(f"Published vector index manifest: {published.index_name}")
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
