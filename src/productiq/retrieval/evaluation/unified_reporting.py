"""Artifact I/O for unified retrieval evaluation (Phase 4.18)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from productiq.retrieval.evaluation.dataset import load_lexical_retrieval_benchmark
from productiq.retrieval.evaluation.rrf_schema import HYBRID_RRF_BENCHMARK_RUN_FILENAME
from productiq.retrieval.evaluation.schema import (
    DEFAULT_EVALUATION_K_VALUES,
    LEXICAL_RETRIEVAL_BENCHMARK_FILENAME,
)
from productiq.retrieval.evaluation.semantic_schema import SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME
from productiq.retrieval.evaluation.unified_comparison import compare_evaluation_results
from productiq.retrieval.evaluation.unified_evaluation_schema import (
    RETRIEVAL_COMPARISON_V1_FILENAME,
    RETRIEVAL_EVALUATION_V1_FILENAME,
    RETRIEVAL_EVALUATION_V1_JSONL_FILENAME,
    EvaluationLineage,
    EvaluationResult,
    UnifiedEvaluationCatalog,
)
from productiq.retrieval.evaluation.unified_evaluator import (
    UnifiedRetrievalEvaluator,
    default_evaluation_request,
)

PRODUCTIQ_VERSION = "0.1.0"
LEXICAL_RUN_FILENAME = "lexical_retrieval_benchmark_v1_run.json"
K_VALUES: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
RETRIEVAL_TOP_K = 50


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise TypeError(msg)
    return payload


def _retrieved_from_metrics(metrics: dict[str, Any]) -> tuple[str, ...]:
    raw = metrics.get("retrieved_product_ids")
    if not isinstance(raw, list):
        msg = "retrieved_product_ids must be a list"
        raise TypeError(msg)
    return tuple(str(item) for item in raw)


def _build_retrieved_map_from_run(per_query: list[Any]) -> dict[str, tuple[str, ...]]:
    mapping: dict[str, tuple[str, ...]] = {}
    for row in per_query:
        if not isinstance(row, dict):
            continue
        query_id = row.get("query_id")
        metrics = row.get("metrics")
        if not isinstance(query_id, str) or not isinstance(metrics, dict):
            continue
        mapping[query_id] = _retrieved_from_metrics(metrics)
    return mapping


def evaluate_bm25_from_artifact(
    eval_dir: Path,
    benchmark_path: Path,
) -> EvaluationResult:
    benchmark = load_lexical_retrieval_benchmark(benchmark_path)
    run = _load_json(eval_dir / LEXICAL_RUN_FILENAME)
    retrieved = _build_retrieved_map_from_run(run.get("per_query", []))
    index_mode = run.get("index_mode")
    lineage = EvaluationLineage(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        system_name="bm25",
        retrieval_method="bm25",
        retrieval_top_k=RETRIEVAL_TOP_K,
        k_values=K_VALUES,
        evaluation_mode="artifact",
        source_artifact_path=str(eval_dir / LEXICAL_RUN_FILENAME),
        bm25_index_mode=str(index_mode) if isinstance(index_mode, str) else None,
        limitations=(benchmark.limitations,),
    )
    evaluator = UnifiedRetrievalEvaluator(default_evaluation_request("bm25"), lineage=lineage)
    return evaluator.evaluate_from_retrieved_by_query_id(
        benchmark,
        retrieved,
        lineage=lineage,
        productiq_version=PRODUCTIQ_VERSION,
    )


def evaluate_semantic_from_artifact(
    eval_dir: Path,
    benchmark_path: Path,
) -> EvaluationResult:
    benchmark = load_lexical_retrieval_benchmark(benchmark_path)
    run = _load_json(eval_dir / SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME)
    per_query = run.get("per_query", [])
    retrieved = _build_retrieved_map_from_run(
        per_query if isinstance(per_query, list) else []
    )
    retrieval = run.get("retrieval")
    embedding_model_id = None
    embedding_model_revision = None
    embedding_dimension = None
    similarity_metric = None
    vector_index_name = None
    if isinstance(retrieval, dict):
        embedding_model_id = retrieval.get("embedding_model_id")
        embedding_model_revision = retrieval.get("embedding_model_revision")
        embedding_dimension = retrieval.get("embedding_dimension")
        similarity_metric = retrieval.get("similarity_metric")
        vector_index_name = retrieval.get("vector_index_name")
    limitations_text = run.get("incomplete_judgment_warning")
    limitation_items: list[str] = [benchmark.limitations]
    if isinstance(limitations_text, str):
        limitation_items.append(limitations_text)
    lineage = EvaluationLineage(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        system_name="semantic",
        retrieval_method="vector",
        retrieval_top_k=RETRIEVAL_TOP_K,
        k_values=K_VALUES,
        evaluation_mode="artifact",
        source_artifact_path=str(eval_dir / SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME),
        embedding_model_id=str(embedding_model_id) if embedding_model_id else None,
        embedding_model_revision=str(embedding_model_revision)
        if embedding_model_revision
        else None,
        embedding_dimension=int(embedding_dimension)
        if isinstance(embedding_dimension, int)
        else None,
        similarity_metric=str(similarity_metric) if similarity_metric else None,
        vector_index_name=str(vector_index_name) if vector_index_name else None,
        limitations=tuple(limitation_items),
    )
    evaluator = UnifiedRetrievalEvaluator(default_evaluation_request("semantic"), lineage=lineage)
    return evaluator.evaluate_from_retrieved_by_query_id(
        benchmark,
        retrieved,
        lineage=lineage,
        productiq_version=PRODUCTIQ_VERSION,
    )


def evaluate_rrf_from_artifact(
    eval_dir: Path,
    benchmark_path: Path,
) -> EvaluationResult:
    benchmark = load_lexical_retrieval_benchmark(benchmark_path)
    run = _load_json(eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME)
    per_query = run.get("per_query", [])
    retrieved_by_query: dict[str, tuple[str, ...]] = {}
    if isinstance(per_query, list):
        for row in per_query:
            if not isinstance(row, dict):
                continue
            query_id = row.get("query_id")
            rrf_metrics = row.get("rrf_metrics")
            if isinstance(query_id, str) and isinstance(rrf_metrics, dict):
                retrieved_by_query[query_id] = _retrieved_from_metrics(rrf_metrics)
    rrf_meta = run.get("rrf")
    rank_constant = None
    rrf_bm25_mode = None
    if isinstance(rrf_meta, dict):
        rc = rrf_meta.get("rank_constant")
        if isinstance(rc, int):
            rank_constant = rc
        mode = rrf_meta.get("bm25_index_mode")
        if isinstance(mode, str):
            rrf_bm25_mode = mode
    scoped_note = (
        "RRF metrics are from live hybrid_rrf_benchmark_v1_run.json with scoped BM25 by default; "
        "not directly comparable to full-catalog BM25 artifact configuration."
    )
    lineage = EvaluationLineage(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        system_name="rrf",
        retrieval_method="hybrid_rrf",
        retrieval_top_k=RETRIEVAL_TOP_K,
        k_values=K_VALUES,
        evaluation_mode="artifact",
        source_artifact_path=str(eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME),
        rrf_rank_constant=rank_constant,
        rrf_bm25_index_mode=rrf_bm25_mode,
        limitations=(benchmark.limitations, scoped_note),
    )
    evaluator = UnifiedRetrievalEvaluator(default_evaluation_request("rrf"), lineage=lineage)
    return evaluator.evaluate_from_retrieved_by_query_id(
        benchmark,
        retrieved_by_query,
        lineage=lineage,
        productiq_version=PRODUCTIQ_VERSION,
    )


def build_catalog_from_evaluation_dir(eval_dir: Path) -> UnifiedEvaluationCatalog:
    benchmark_path = eval_dir / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
    benchmark = load_lexical_retrieval_benchmark(benchmark_path)
    bm25 = evaluate_bm25_from_artifact(eval_dir, benchmark_path)
    semantic = evaluate_semantic_from_artifact(eval_dir, benchmark_path)
    rrf = evaluate_rrf_from_artifact(eval_dir, benchmark_path)
    comparisons = (
        compare_evaluation_results(bm25, semantic),
        compare_evaluation_results(bm25, rrf),
        compare_evaluation_results(semantic, rrf),
    )
    judged_count = sum(len(query.relevant_product_ids) for query in benchmark.queries)
    return UnifiedEvaluationCatalog(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        incomplete_judgment_warning=benchmark.limitations,
        query_count=len(benchmark.queries),
        judged_relevant_product_count=judged_count,
        generated_at_utc=datetime.now(tz=UTC).isoformat(),
        evaluations=(bm25, semantic, rrf),
        comparisons=comparisons,
    )


def write_unified_evaluation_artifacts(
    eval_dir: Path,
    catalog: UnifiedEvaluationCatalog,
) -> tuple[Path, Path, Path]:
    eval_dir.mkdir(parents=True, exist_ok=True)
    json_path = eval_dir / RETRIEVAL_EVALUATION_V1_FILENAME
    jsonl_path = eval_dir / RETRIEVAL_EVALUATION_V1_JSONL_FILENAME
    comparison_path = eval_dir / RETRIEVAL_COMPARISON_V1_FILENAME

    json_path.write_text(catalog.model_dump_json(indent=2), encoding="utf-8")
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for evaluation in catalog.evaluations:
            for query_row in evaluation.per_query:
                handle.write(
                    json.dumps(
                        {
                            "system_name": evaluation.lineage.system_name,
                            "query_id": query_row.query_id,
                            "category": query_row.category,
                            "metrics": query_row.model_dump(mode="json"),
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
    comparison_payload = {
        "framework_version": catalog.framework_version,
        "benchmark_name": catalog.benchmark_name,
        "benchmark_version": catalog.benchmark_version,
        "comparisons": [row.model_dump(mode="json") for row in catalog.comparisons],
        "limitations": catalog.incomplete_judgment_warning,
    }
    comparison_path.write_text(json.dumps(comparison_payload, indent=2), encoding="utf-8")
    return json_path, jsonl_path, comparison_path


__all__ = [
    "build_catalog_from_evaluation_dir",
    "evaluate_bm25_from_artifact",
    "evaluate_rrf_from_artifact",
    "evaluate_semantic_from_artifact",
    "write_unified_evaluation_artifacts",
]
