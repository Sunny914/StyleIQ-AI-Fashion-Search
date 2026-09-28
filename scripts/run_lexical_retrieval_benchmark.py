"""Run BM25 lexical retrieval benchmark and print metrics."""

from __future__ import annotations

import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

# Bootstrap import order (same as tests/conftest) to avoid circular import on bare scripts.
from productiq.config.settings import get_settings  # noqa: F401
from productiq.retrieval import create_bm25_retriever_from_index_path
from productiq.retrieval.evaluation import (
    LexicalRetrievalEvaluator,
    build_benchmark_scoped_bm25_retriever,
    load_lexical_retrieval_benchmark,
)


def _load_retriever(root: Path, benchmark):
    import os

    index_path = root / "resources" / "processed" / "bm25_lexical_index.pkl"
    parquet_path = root / "resources" / "processed" / "product_representations.parquet"
    if os.environ.get("PRODUCTIQ_LEXICAL_EVAL_SCOPED") == "1":
        retriever, doc_count = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
        return retriever, f"benchmark_scoped_slice_{doc_count}_docs"
    try:
        print(f"Loading persisted BM25 index from {index_path} ...", flush=True)
        return create_bm25_retriever_from_index_path(index_path), "full_persisted_index"
    except MemoryError:
        print(
            "Persisted index load hit MemoryError; building benchmark-scoped in-memory index ...",
            flush=True,
        )
        retriever, doc_count = build_benchmark_scoped_bm25_retriever(
            parquet_path,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
        print(f"Scoped index document_count={doc_count}", flush=True)
        return retriever, f"benchmark_scoped_slice_{doc_count}_docs"


def main() -> None:
    import time

    root = _ROOT
    benchmark = load_lexical_retrieval_benchmark(
        root / "resources" / "evaluation" / "lexical_retrieval_benchmark_v1.json"
    )
    t0 = time.perf_counter()
    retriever, index_mode = _load_retriever(root, benchmark)
    print(f"Retriever ready ({index_mode}) in {time.perf_counter() - t0:.1f}s", flush=True)
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10, 20, 50))
    t1 = time.perf_counter()
    result = evaluator.evaluate(benchmark, retriever)
    print(f"Evaluation finished in {time.perf_counter() - t1:.1f}s", flush=True)
    out_path = root / "resources" / "evaluation" / "lexical_retrieval_benchmark_v1_run.json"
    payload = {
        "index_mode": index_mode,
        "aggregate": result.aggregate.model_dump(mode="json"),
        "per_query": [row.model_dump(mode="json") for row in result.per_query],
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {out_path}", flush=True)
    print(json.dumps(result.aggregate.model_dump(mode="json"), indent=2))
    print("--- per-query ---")
    for row in result.per_query:
        print(
            row.query_id,
            f"P@10={row.metrics.precision_at_k[10]:.4f}",
            f"R@10={row.metrics.recall_at_k[10]:.4f}",
            f"RR={row.metrics.reciprocal_rank:.4f}",
            f"rank1={row.metrics.first_relevant_rank}",
        )


if __name__ == "__main__":
    main()
