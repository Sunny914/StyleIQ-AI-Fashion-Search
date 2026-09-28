"""Run semantic retrieval benchmark (Phase 4.14) via SemanticRetriever."""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.evaluation.semantic_dataset import (
    judged_relevant_product_count,
    load_semantic_retrieval_benchmark,
)
from productiq.retrieval.evaluation.semantic_evaluator import (
    SemanticRetrievalEvaluator,
    build_per_query_analysis_rows,
)
from productiq.retrieval.evaluation.semantic_schema import (
    SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME,
    SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME,
)
from productiq.retrieval.semantic_retriever import (
    create_semantic_retriever_from_engine,
)

PRODUCTIQ_VERSION = "0.1.0"


def _load_bm25_aggregate_for_comparison(root: Path) -> dict[str, object] | None:
    path = root / "resources" / "evaluation" / "lexical_retrieval_benchmark_v1_run.json"
    if not path.is_file():
        return None
    payload = json.loads(path.read_text(encoding="utf-8"))
    aggregate = payload.get("aggregate")
    return aggregate if isinstance(aggregate, dict) else None


def _build_run_payload(
    *,
    benchmark,
    output,
    evaluation_duration_seconds: float,
    encoder_load_seconds: float,
    bm25_aggregate: dict[str, object] | None,
) -> dict[str, object]:
    result = output.result
    ctx = output.context
    incomplete_warning = benchmark.limitations
    payload: dict[str, object] = {
        "productiq_version": PRODUCTIQ_VERSION,
        "incomplete_judgment_warning": incomplete_warning,
        "evaluation_duration_seconds": evaluation_duration_seconds,
        "encoder_load_seconds": encoder_load_seconds,
        "benchmark": {
            "benchmark_name": benchmark.benchmark_name,
            "benchmark_version": benchmark.benchmark_version,
            "query_count": len(benchmark.queries),
            "judged_relevant_product_count": judged_relevant_product_count(benchmark),
            "catalog_artifact": benchmark.catalog_artifact,
            "source_representation_checksum": benchmark.source_representation_checksum,
            "source_embedding_artifact_checksum": benchmark.source_embedding_artifact_checksum,
            "relevance_policy": benchmark.relevance_policy,
            "methodology": benchmark.methodology,
            "limitations": benchmark.limitations,
        },
        "retrieval": {
            "retrieval_method": ctx.retrieval_method,
            "embedding_model_id": ctx.embedding_model_id,
            "embedding_model_revision": ctx.embedding_model_revision,
            "embedding_dimension": ctx.embedding_dimension,
            "similarity_metric": ctx.similarity_metric,
            "vector_index_name": ctx.vector_index_name,
            "retrieval_top_k": result.retrieval_top_k,
            "k_values": list(result.k_values),
            "evaluation_timestamp_utc": ctx.evaluation_timestamp_utc,
        },
        "aggregate": result.aggregate.model_dump(mode="json"),
        "per_query": [row.model_dump(mode="json") for row in result.per_query],
    }
    if bm25_aggregate is not None:
        payload["bm25_comparison"] = {
            "note": (
                "Descriptive comparison only (same query texts and judged relevant_product_ids "
                "as lexical_retrieval_benchmark_v1). Not a hybrid score or winner declaration."
            ),
            "lexical_run_aggregate": bm25_aggregate,
        }
    return payload


def main() -> int:
    root = _ROOT
    benchmark_path = root / "resources" / "evaluation" / "semantic_retrieval_benchmark_v1.json"
    benchmark = load_semantic_retrieval_benchmark(benchmark_path)

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    try:
        t_encoder = time.perf_counter()
        print("Loading BGE query encoder ...", flush=True)
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        encoder_load_seconds = time.perf_counter() - t_encoder
        print(f"Encoder ready in {encoder_load_seconds:.1f}s", flush=True)

        retriever = create_semantic_retriever_from_engine(engine, encoder)
        evaluator = SemanticRetrievalEvaluator(retrieval_top_k=50, k_values=(1, 5, 10, 20, 50))
        print("Validating benchmark product IDs against catalog ...", flush=True)
        judged_ids = evaluator.validate_benchmark(benchmark, engine)
        print(f"Validated {judged_ids} unique judged relevant product IDs", flush=True)

        t_eval = time.perf_counter()
        output = evaluator.evaluate(
            benchmark,
            retriever,
            engine=engine,
            validate_catalog=False,
        )
        evaluation_duration_seconds = time.perf_counter() - t_eval
        print(f"Evaluation finished in {evaluation_duration_seconds:.1f}s", flush=True)

        bm25_aggregate = _load_bm25_aggregate_for_comparison(root)
        run_payload = _build_run_payload(
            benchmark=benchmark,
            output=output,
            evaluation_duration_seconds=evaluation_duration_seconds,
            encoder_load_seconds=encoder_load_seconds,
            bm25_aggregate=bm25_aggregate,
        )

        eval_dir = root / "resources" / "evaluation"
        run_path = eval_dir / SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME
        run_path.write_text(json.dumps(run_payload, indent=2), encoding="utf-8")
        print(f"Wrote {run_path}", flush=True)

        analysis_path = eval_dir / SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME
        with analysis_path.open("w", encoding="utf-8") as handle:
            for row in build_per_query_analysis_rows(output):
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"Wrote {analysis_path}", flush=True)

        print(json.dumps(run_payload["aggregate"], indent=2))
        if bm25_aggregate is not None:
            print("--- BM25 aggregate (lexical run, same judgments) ---")
            print(json.dumps(bm25_aggregate, indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
