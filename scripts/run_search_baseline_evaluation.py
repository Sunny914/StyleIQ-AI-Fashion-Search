"""Run Phase 12.5 baseline search evaluation for BM25, semantic, and RRF variants."""

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
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.evaluation.search_evaluation.baseline_evaluation import (
    SUPPORTED_SEARCH_BASELINE_VARIANTS,
    run_bm25_search_baseline,
    run_rrf_search_baseline,
    run_semantic_search_baseline,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_executors import (
    create_bm25_baseline_setup,
    create_semantic_baseline_setup,
)


def _parse_variants(raw: str | None) -> tuple[str, ...]:
    if raw is None or raw.strip().lower() == "all":
        return SUPPORTED_SEARCH_BASELINE_VARIANTS
    selected = tuple(part.strip().lower() for part in raw.split(",") if part.strip())
    unknown = set(selected) - set(SUPPORTED_SEARCH_BASELINE_VARIANTS)
    if unknown:
        msg = f"unknown baseline variants: {sorted(unknown)}; supported: {SUPPORTED_SEARCH_BASELINE_VARIANTS}"
        raise SystemExit(msg)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description="ProductIQ Phase 12.5 search baseline evaluation")
    parser.add_argument(
        "--variants",
        default="all",
        help=f"Comma-separated subset of {','.join(SUPPORTED_SEARCH_BASELINE_VARIANTS)} or 'all' (default).",
    )
    args = parser.parse_args()
    variants = _parse_variants(args.variants)
    root = _ROOT
    summaries: list[dict[str, object]] = []

    if "bm25" in variants:
        print("Running BM25 baseline ...", flush=True)
        artifact = run_bm25_search_baseline(root)
        summaries.append(
            {
                "variant": "bm25",
                "artifact_path": artifact.get("artifact_path"),
                "deterministic_checksum_sha256": artifact.get("deterministic_checksum_sha256"),
                "query_count": artifact.get("query_count"),
                "aggregate_mrr": artifact["evaluation_result"]["aggregate"]["mrr"],
            }
        )
        print(f"Wrote {artifact.get('artifact_path')}", flush=True)

    needs_db = "semantic" in variants or "rrf" in variants
    engine = None
    encoder = None
    bm25_setup = None
    semantic_setup = None
    if needs_db:
        settings = get_settings()
        engine = create_engine_from_settings(settings)
        print("Loading BGE encoder ...", flush=True)
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        bm25_setup = create_bm25_baseline_setup(root)
        semantic_setup = create_semantic_baseline_setup(root, engine=engine, encoder=encoder)

    try:
        if "semantic" in variants:
            assert engine is not None and encoder is not None
            print("Running semantic baseline ...", flush=True)
            artifact = run_semantic_search_baseline(root, engine=engine, encoder=encoder)
            summaries.append(
                {
                    "variant": "semantic",
                    "artifact_path": artifact.get("artifact_path"),
                    "deterministic_checksum_sha256": artifact.get("deterministic_checksum_sha256"),
                    "query_count": artifact.get("query_count"),
                    "aggregate_mrr": artifact["evaluation_result"]["aggregate"]["mrr"],
                }
            )
            print(f"Wrote {artifact.get('artifact_path')}", flush=True)

        if "rrf" in variants:
            assert bm25_setup is not None and semantic_setup is not None
            print("Running RRF baseline ...", flush=True)
            artifact = run_rrf_search_baseline(
                root,
                bm25_setup=bm25_setup,
                semantic_setup=semantic_setup,
            )
            summaries.append(
                {
                    "variant": "rrf",
                    "artifact_path": artifact.get("artifact_path"),
                    "deterministic_checksum_sha256": artifact.get("deterministic_checksum_sha256"),
                    "query_count": artifact.get("query_count"),
                    "aggregate_mrr": artifact["evaluation_result"]["aggregate"]["mrr"],
                }
            )
            print(f"Wrote {artifact.get('artifact_path')}", flush=True)
    finally:
        if engine is not None:
            engine.dispose()

    print(json.dumps(summaries, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
