"""Run RRF hybrid retrieval benchmark evaluation (Phase 4.16)."""

from __future__ import annotations

import gc
import json
import os
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.retrieval import create_bm25_retriever_from_index_path
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.evaluation import (
    LexicalRetrievalEvaluator,
    load_lexical_retrieval_benchmark,
)
from productiq.retrieval.evaluation.contracts import LexicalRetrievalEvaluationResult
from productiq.retrieval.evaluation.rrf_schema import (
    HYBRID_RRF_ANALYSIS_FILENAME,
    HYBRID_RRF_BENCHMARK_RUN_FILENAME,
)
from productiq.retrieval.evaluation.semantic_dataset import (
    judged_relevant_product_count,
    load_semantic_retrieval_benchmark,
)
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.rrf_hybrid_retriever import create_rrf_hybrid_retriever
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine

PRODUCTIQ_VERSION = "0.1.0"


def _evaluate_with_progress(evaluator, benchmark, retriever, label: str):
    per_query = []
    total = len(benchmark.queries)
    for index, query in enumerate(benchmark.queries, start=1):
        print(f"{label} query {index}/{total}: {query.query_id}", flush=True)
        slice_benchmark = benchmark.model_copy(update={"queries": (query,)})
        result = evaluator.evaluate(slice_benchmark, retriever)
        per_query.extend(result.per_query)
        gc.collect()
    return LexicalRetrievalEvaluationResult(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        retrieval_top_k=evaluator.retrieval_top_k,
        k_values=evaluator.k_values,
        per_query=tuple(per_query),
        aggregate=evaluator._aggregate(per_query),
    )


def _load_run(path: Path) -> dict[str, object] | None:
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else None


def _load_aggregate(path: Path) -> dict[str, object] | None:
    payload = _load_run(path)
    if payload is None:
        return None
    aggregate = payload.get("aggregate")
    return aggregate if isinstance(aggregate, dict) else None


def _load_bm25_retriever(root: Path, benchmark):
    index_path = root / "resources" / "processed" / "bm25_lexical_index.pkl"
    parquet_path = root / "resources" / "processed" / "product_representations.parquet"
    from productiq.retrieval.evaluation import build_benchmark_scoped_bm25_retriever

    use_full = os.environ.get("PRODUCTIQ_RRF_EVAL_FULL_BM25") == "1"
    if use_full:
        try:
            return create_bm25_retriever_from_index_path(index_path), "full_persisted_index"
        except (MemoryError, OSError):
            print("Full BM25 index unavailable; falling back to scoped slice", flush=True)
    retriever, doc_count = build_benchmark_scoped_bm25_retriever(
        parquet_path,
        benchmark,
        max_docs_per_term=500,
        max_total_docs=8_000,
    )
    return retriever, f"benchmark_scoped_slice_{doc_count}_docs"


def main() -> int:
    root = _ROOT
    eval_dir = root / "resources" / "evaluation"
    lexical_benchmark = load_lexical_retrieval_benchmark(
        eval_dir / "lexical_retrieval_benchmark_v1.json"
    )
    semantic_benchmark = load_semantic_retrieval_benchmark(
        eval_dir / "semantic_retrieval_benchmark_v1.json"
    )
    rrf_config = RRFConfig(rank_constant=60)
    lexical_run = _load_run(eval_dir / "lexical_retrieval_benchmark_v1_run.json")
    semantic_run = _load_run(eval_dir / "semantic_retrieval_benchmark_v1_run.json")
    if lexical_run is None or semantic_run is None:
        msg = "Phase 4.8 and 4.14 run artifacts are required for BM25/semantic comparison"
        raise FileNotFoundError(msg)
    bm25_stored = lexical_run.get("aggregate")
    semantic_stored = semantic_run.get("aggregate")
    bm25_per_query = lexical_run.get("per_query")
    semantic_per_query = semantic_run.get("per_query")
    if not isinstance(bm25_per_query, list) or not isinstance(semantic_per_query, list):
        msg = "stored BM25/semantic run artifacts must include per_query results"
        raise TypeError(msg)

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    evaluator = LexicalRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10, 20, 50))
    t_setup = time.perf_counter()
    try:
        print("Loading BM25 retriever ...", flush=True)
        bm25_retriever, bm25_index_mode = _load_bm25_retriever(root, lexical_benchmark)
        print(f"BM25 ready ({bm25_index_mode})", flush=True)
        print("Loading BGE encoder ...", flush=True)
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        semantic_retriever = create_semantic_retriever_from_engine(engine, encoder)
        rrf_retriever = create_rrf_hybrid_retriever(
            bm25_retriever,
            semantic_retriever,
            config=rrf_config,
        )
        setup_seconds = time.perf_counter() - t_setup
        print(f"Setup finished in {setup_seconds:.1f}s", flush=True)
        t_eval = time.perf_counter()
        print("Evaluating RRF (live); BM25/semantic metrics from stored Phase 4.8/4.14 runs", flush=True)
        rrf_result = _evaluate_with_progress(
            evaluator, lexical_benchmark, rrf_retriever, "RRF"
        )
        evaluation_seconds = time.perf_counter() - t_eval
        print(f"RRF evaluation finished in {evaluation_seconds:.1f}s", flush=True)
    finally:
        engine.dispose()

    bm25_by_id = {row["query_id"]: row for row in bm25_per_query if isinstance(row, dict)}
    semantic_by_id = {row["query_id"]: row for row in semantic_per_query if isinstance(row, dict)}
    rrf_by_id = {row.query_id: row for row in rrf_result.per_query}
    per_query_rows: list[dict[str, object]] = []
    for query in lexical_benchmark.queries:
        bm25_row = bm25_by_id[query.query_id]
        semantic_row = semantic_by_id[query.query_id]
        rrf_row = rrf_by_id[query.query_id]
        bm25_metrics = bm25_row["metrics"]
        semantic_metrics = semantic_row["metrics"]
        per_query_rows.append(
            {
                "query_id": query.query_id,
                "query_text": query.query_text,
                "category": query.category,
                "bm25_first_relevant_rank": bm25_metrics.get("first_relevant_rank"),
                "semantic_first_relevant_rank": semantic_metrics.get("first_relevant_rank"),
                "rrf_first_relevant_rank": rrf_row.metrics.first_relevant_rank,
                "bm25_metrics": bm25_metrics,
                "semantic_metrics": semantic_metrics,
                "rrf_metrics": rrf_row.metrics.model_dump(mode="json"),
            }
        )

    payload: dict[str, object] = {
        "productiq_version": PRODUCTIQ_VERSION,
        "incomplete_judgment_warning": semantic_benchmark.limitations,
        "setup_duration_seconds": setup_seconds,
        "evaluation_duration_seconds": evaluation_seconds,
        "benchmark": {
            "lexical_benchmark_name": lexical_benchmark.benchmark_name,
            "lexical_benchmark_version": lexical_benchmark.benchmark_version,
            "semantic_benchmark_name": semantic_benchmark.benchmark_name,
            "semantic_benchmark_version": semantic_benchmark.benchmark_version,
            "query_count": len(lexical_benchmark.queries),
            "judged_relevant_product_count": judged_relevant_product_count(semantic_benchmark),
        },
        "rrf": {
            "rank_constant": rrf_config.rank_constant,
            "retrieval_top_k": rrf_result.retrieval_top_k,
            "bm25_index_mode": bm25_index_mode,
            "bm25_index_note": (
                "Live RRF uses a benchmark-scoped BM25 slice by default because full-index "
                "BM25 scoring of broad queries can exhaust process memory. Set "
                "PRODUCTIQ_RRF_EVAL_FULL_BM25=1 to force the persisted full index. "
                "Reported BM25-only metrics remain the official full-catalog Phase 4.8 run."
            ),
            "embedding_model_id": semantic_benchmark.embedding_model_id,
            "embedding_model_revision": semantic_benchmark.embedding_model_revision,
            "bm25_metrics_source": "resources/evaluation/lexical_retrieval_benchmark_v1_run.json",
            "semantic_metrics_source": "resources/evaluation/semantic_retrieval_benchmark_v1_run.json",
            "rrf_metrics_source": "live RRFHybridRetriever",
        },
        "aggregate": {
            "bm25": bm25_stored,
            "semantic": semantic_stored,
            "rrf": rrf_result.aggregate.model_dump(mode="json"),
        },
        "stored_run_comparison": {
            "note": (
                "BM25 and semantic aggregates are the official Phase 4.8/4.14 run artifacts "
                "(same queries and judgments). RRF is measured live in this run."
            ),
            "bm25_stored_aggregate": bm25_stored,
            "semantic_stored_aggregate": semantic_stored,
        },
        "per_query": per_query_rows,
    }
    run_path = eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME
    run_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    analysis_path = eval_dir / HYBRID_RRF_ANALYSIS_FILENAME
    with analysis_path.open("w", encoding="utf-8") as handle:
        for row in per_query_rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"Wrote {run_path}", flush=True)
    print(json.dumps(payload["aggregate"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
