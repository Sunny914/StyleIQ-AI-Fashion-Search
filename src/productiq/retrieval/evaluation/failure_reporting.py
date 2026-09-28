"""Load benchmark artifacts and write Phase 4.17 failure-analysis outputs."""

from __future__ import annotations

import json
from collections import Counter
from pathlib import Path
from typing import Any

import pyarrow.parquet as pq  # type: ignore[import-untyped]

from productiq.retrieval.evaluation.dataset import load_lexical_retrieval_benchmark
from productiq.retrieval.evaluation.failure_analysis_schema import (
    RETRIEVAL_FAILURE_ANALYSIS_FILENAME,
    RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME,
    RETRIEVAL_FAILURE_ANALYSIS_VERSION,
    RETRIEVAL_FAILURE_SUMMARY_FILENAME,
    CategoryAggregationRow,
    FailureAnalysisLineage,
    QueryProductDiagnosticRecord,
    RetrievalFailureAnalysisReport,
    RetrievalFailureSummaryReport,
    RetrievalPatternClassification,
)
from productiq.retrieval.evaluation.failure_analyzer import (
    QueryRetrievalArtifactSlice,
    analyze_retrieval_failures,
)
from productiq.retrieval.evaluation.rrf_schema import HYBRID_RRF_BENCHMARK_RUN_FILENAME
from productiq.retrieval.evaluation.schema import (
    DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
    LEXICAL_RETRIEVAL_BENCHMARK_FILENAME,
)
from productiq.retrieval.evaluation.semantic_schema import (
    SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME,
    SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME,
)
from productiq.retrieval.rrf_config import DEFAULT_RRF_RANK_CONSTANT

PRODUCTIQ_VERSION = "0.1.0"
LEXICAL_RUN_FILENAME = "lexical_retrieval_benchmark_v1_run.json"

BM25_NATIVE_SCORE_LIMITATION = (
    "Phase 4.8 lexical run artifacts record retrieved_product_ids (ranks) only; "
    "native BM25 scores are not persisted and remain null in this analysis."
)
RRF_SCOPED_BM25_LIMITATION = (
    "RRF retrieved lists come from hybrid_rrf_benchmark_v1_run.json live evaluation "
    "with benchmark-scoped BM25 by default; BM25 lists in that artifact are the "
    "official full-catalog Phase 4.8 runs. RRF ranks reflect scoped BM25 fusion."
)

REPRESENTATION_PARQUET_COLUMNS: tuple[str, ...] = (
    "product_id",
    "brand",
    "category_gender",
    "product_type",
    "color",
    "pattern",
    "material",
    "fit",
    "sleeve",
    "neckline",
    "product_features",
    "style_attributes",
    "product_text",
    "lexical_text",
    "semantic_text",
)


def _load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"expected JSON object in {path}"
        raise TypeError(msg)
    return payload


def _metrics_retrieved_ids(metrics: dict[str, Any]) -> tuple[str, ...]:
    raw = metrics.get("retrieved_product_ids")
    if not isinstance(raw, list):
        msg = "metrics.retrieved_product_ids must be a list"
        raise TypeError(msg)
    return tuple(str(item) for item in raw)


def _semantic_scores_from_analysis_row(row: dict[str, Any]) -> dict[str, float]:
    details = row.get("retrieved_details")
    if not isinstance(details, list):
        return {}
    scores: dict[str, float] = {}
    for item in details:
        if not isinstance(item, dict):
            continue
        product_id = item.get("product_id")
        score = item.get("similarity_score")
        if isinstance(product_id, str) and isinstance(score, (int, float)):
            scores[product_id] = float(score)
    return scores


def load_semantic_analysis_by_query_id(path: Path) -> dict[str, dict[str, Any]]:
    by_id: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                continue
            query_id = row.get("query_id")
            if isinstance(query_id, str):
                by_id[query_id] = row
    return by_id


def build_query_slices_from_artifacts(
    eval_dir: Path,
    *,
    benchmark_path: Path | None = None,
    lexical_run_path: Path | None = None,
    hybrid_rrf_run_path: Path | None = None,
    semantic_analysis_path: Path | None = None,
) -> tuple[QueryRetrievalArtifactSlice, ...]:
    benchmark_path = benchmark_path or eval_dir / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME
    lexical_run_path = lexical_run_path or eval_dir / LEXICAL_RUN_FILENAME
    hybrid_rrf_run_path = hybrid_rrf_run_path or eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME
    semantic_analysis_path = semantic_analysis_path or eval_dir / SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME

    benchmark = load_lexical_retrieval_benchmark(benchmark_path)
    lexical_run = _load_json(lexical_run_path)
    hybrid_run = _load_json(hybrid_rrf_run_path)
    semantic_analysis = load_semantic_analysis_by_query_id(semantic_analysis_path)

    lexical_by_id = {
        row["query_id"]: row
        for row in lexical_run.get("per_query", [])
        if isinstance(row, dict) and isinstance(row.get("query_id"), str)
    }
    hybrid_by_id = {
        row["query_id"]: row
        for row in hybrid_run.get("per_query", [])
        if isinstance(row, dict) and isinstance(row.get("query_id"), str)
    }

    slices: list[QueryRetrievalArtifactSlice] = []
    for evaluation_query in benchmark.queries:
        lexical_row = lexical_by_id.get(evaluation_query.query_id)
        hybrid_row = hybrid_by_id.get(evaluation_query.query_id)
        semantic_row = semantic_analysis.get(evaluation_query.query_id)
        if lexical_row is None or hybrid_row is None:
            msg = f"missing run data for query {evaluation_query.query_id}"
            raise KeyError(msg)
        bm25_metrics = hybrid_row.get("bm25_metrics")
        semantic_metrics = hybrid_row.get("semantic_metrics")
        rrf_metrics = hybrid_row.get("rrf_metrics")
        if not isinstance(bm25_metrics, dict):
            bm25_metrics = lexical_row.get("metrics", {})
        if not isinstance(semantic_metrics, dict):
            msg = f"semantic metrics missing for {evaluation_query.query_id}"
            raise TypeError(msg)
        if not isinstance(rrf_metrics, dict):
            msg = f"RRF metrics missing for {evaluation_query.query_id}"
            raise TypeError(msg)

        semantic_scores: dict[str, float] = {}
        if isinstance(semantic_row, dict):
            semantic_scores = _semantic_scores_from_analysis_row(semantic_row)

        slices.append(
            QueryRetrievalArtifactSlice(
                query_id=evaluation_query.query_id,
                query_text=evaluation_query.query_text,
                category=evaluation_query.category,
                judged_relevant_product_ids=evaluation_query.relevant_product_ids,
                bm25_retrieved_product_ids=_metrics_retrieved_ids(bm25_metrics),
                semantic_retrieved_product_ids=_metrics_retrieved_ids(semantic_metrics),
                rrf_retrieved_product_ids=_metrics_retrieved_ids(rrf_metrics),
                semantic_native_scores=semantic_scores,
            )
        )
    return tuple(slices)


def load_representation_rows_for_product_ids(
    parquet_path: Path,
    product_ids: set[str],
) -> dict[str, dict[str, Any]]:
    if not product_ids or not parquet_path.is_file():
        return {}
    table = pq.read_table(parquet_path, columns=list(REPRESENTATION_PARQUET_COLUMNS))
    rows: dict[str, dict[str, Any]] = {}
    data = table.to_pydict()
    ids = data.get("product_id", [])
    for index, product_id in enumerate(ids):
        if product_id not in product_ids:
            continue
        row = {column: data[column][index] for column in data}
        rows[str(product_id)] = row
    return rows


def build_failure_analysis_lineage(
    eval_dir: Path,
    *,
    retrieval_top_k: int = DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
    rrf_rank_constant: int = DEFAULT_RRF_RANK_CONSTANT,
) -> FailureAnalysisLineage:
    benchmark = load_lexical_retrieval_benchmark(eval_dir / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME)
    lexical_run = _load_json(eval_dir / LEXICAL_RUN_FILENAME)
    hybrid_run = _load_json(eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME)
    rrf_meta = hybrid_run.get("rrf")
    rrf_index_mode = None
    if isinstance(rrf_meta, dict):
        mode = rrf_meta.get("bm25_index_mode")
        if isinstance(mode, str):
            rrf_index_mode = mode
        constant = rrf_meta.get("rank_constant")
        if isinstance(constant, int) and constant > 0:
            rrf_rank_constant = constant
        top_k = rrf_meta.get("retrieval_top_k")
        if isinstance(top_k, int) and top_k > 0:
            retrieval_top_k = top_k
    index_mode = lexical_run.get("index_mode")
    return FailureAnalysisLineage(
        analysis_version=RETRIEVAL_FAILURE_ANALYSIS_VERSION,
        lexical_benchmark_name=benchmark.benchmark_name,
        lexical_benchmark_version=benchmark.benchmark_version,
        lexical_run_artifact=str(eval_dir / LEXICAL_RUN_FILENAME),
        lexical_index_mode=str(index_mode) if isinstance(index_mode, str) else None,
        semantic_run_artifact=str(eval_dir / SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME),
        semantic_analysis_artifact=str(eval_dir / SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME),
        hybrid_rrf_run_artifact=str(eval_dir / HYBRID_RRF_BENCHMARK_RUN_FILENAME),
        rrf_bm25_index_mode=rrf_index_mode,
        rrf_rank_constant=rrf_rank_constant,
        retrieval_top_k=retrieval_top_k,
        incomplete_judgment_warning=benchmark.limitations,
        rrf_scoped_bm25_limitation=RRF_SCOPED_BM25_LIMITATION,
        bm25_native_score_limitation=BM25_NATIVE_SCORE_LIMITATION,
    )


def build_summary_report(report: RetrievalFailureAnalysisReport) -> RetrievalFailureSummaryReport:
    pattern_counter: Counter[str] = Counter()
    bm25_counter: Counter[str] = Counter()
    semantic_counter: Counter[str] = Counter()
    depth_limited = 0
    review_candidates = 0

    by_category: dict[str, list[QueryProductDiagnosticRecord]] = {}
    for row in report.diagnostics:
        bm25_counter[row.bm25_observed_classification.value] += 1
        semantic_counter[row.semantic_observed_classification.value] += 1
        for pattern in row.retrieval_pattern_classifications:
            pattern_counter[pattern.value] += 1
            if pattern is RetrievalPatternClassification.DEPTH_LIMITED:
                depth_limited += 1
        if row.representation_review_candidate:
            review_candidates += 1
        by_category.setdefault(row.query_category, []).append(row)

    category_rows: list[CategoryAggregationRow] = []
    query_ids_by_category: dict[str, set[str]] = {}
    for row in report.diagnostics:
        query_ids_by_category.setdefault(row.query_category, set()).add(row.query_id)

    for category in sorted(by_category):
        rows = by_category[category]
        cat_patterns: Counter[str] = Counter()
        for diagnostic in rows:
            for pattern in diagnostic.retrieval_pattern_classifications:
                cat_patterns[pattern.value] += 1
        category_rows.append(
            CategoryAggregationRow(
                query_category=category,
                query_count=len(query_ids_by_category[category]),
                judged_relevant_product_count=len(rows),
                retrieval_pattern_counts=dict(sorted(cat_patterns.items())),
                bm25_not_retrieved_count=sum(
                    1
                    for diagnostic in rows
                    if diagnostic.bm25_observed_classification.value
                    == "NOT_RETRIEVED_BY_BM25"
                ),
                semantic_not_retrieved_count=sum(
                    1
                    for diagnostic in rows
                    if diagnostic.semantic_observed_classification.value
                    == "NOT_RETRIEVED_BY_SEMANTIC"
                ),
                rrf_not_retrieved_count=sum(
                    1 for diagnostic in rows if not diagnostic.rrf.retrieved
                ),
                depth_limited_count=sum(
                    1
                    for diagnostic in rows
                    if RetrievalPatternClassification.DEPTH_LIMITED
                    in diagnostic.retrieval_pattern_classifications
                ),
                representation_review_candidate_count=sum(
                    1 for diagnostic in rows if diagnostic.representation_review_candidate
                ),
            )
        )

    limitations = (
        report.lineage.incomplete_judgment_warning,
        report.lineage.bm25_native_score_limitation or "",
        report.lineage.rrf_scoped_bm25_limitation or "",
        "Interpretive diagnostics are hypotheses for investigation, not verified root causes.",
    )

    return RetrievalFailureSummaryReport(
        productiq_version=report.productiq_version,
        analysis_version=RETRIEVAL_FAILURE_ANALYSIS_VERSION,
        lineage=report.lineage,
        query_count=report.query_count,
        judged_relevant_product_count=report.judged_relevant_product_count,
        retrieval_pattern_counts=dict(sorted(pattern_counter.items())),
        bm25_observed_classification_counts=dict(sorted(bm25_counter.items())),
        semantic_observed_classification_counts=dict(sorted(semantic_counter.items())),
        depth_limited_count=depth_limited,
        representation_review_candidate_count=review_candidates,
        by_query_category=tuple(category_rows),
        limitations=tuple(item for item in limitations if item),
    )


def run_failure_analysis_from_evaluation_dir(
    eval_dir: Path,
    *,
    representation_parquet_path: Path | None = None,
    productiq_version: str = PRODUCTIQ_VERSION,
) -> tuple[RetrievalFailureAnalysisReport, RetrievalFailureSummaryReport]:
    lineage = build_failure_analysis_lineage(eval_dir)
    slices = build_query_slices_from_artifacts(eval_dir)
    product_ids: set[str] = set()
    for query in slices:
        product_ids.update(query.judged_relevant_product_ids)

    catalog_rows: dict[str, dict[str, Any]] = {}
    if representation_parquet_path is not None:
        catalog_rows = load_representation_rows_for_product_ids(
            representation_parquet_path, product_ids
        )

    report = analyze_retrieval_failures(
        productiq_version=productiq_version,
        lineage=lineage,
        queries=slices,
        catalog_rows_by_product_id=catalog_rows,
    )
    summary = build_summary_report(report)
    return report, summary


def write_failure_analysis_artifacts(
    eval_dir: Path,
    report: RetrievalFailureAnalysisReport,
    summary: RetrievalFailureSummaryReport,
) -> tuple[Path, Path, Path]:
    eval_dir.mkdir(parents=True, exist_ok=True)
    json_path = eval_dir / RETRIEVAL_FAILURE_ANALYSIS_FILENAME
    jsonl_path = eval_dir / RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME
    summary_path = eval_dir / RETRIEVAL_FAILURE_SUMMARY_FILENAME

    json_path.write_text(
        report.model_dump_json(indent=2),
        encoding="utf-8",
    )
    with jsonl_path.open("w", encoding="utf-8") as handle:
        for row in report.diagnostics:
            handle.write(row.model_dump_json() + "\n")
    summary_path.write_text(
        summary.model_dump_json(indent=2),
        encoding="utf-8",
    )
    return json_path, jsonl_path, summary_path


__all__ = [
    "build_failure_analysis_lineage",
    "build_query_slices_from_artifacts",
    "build_summary_report",
    "load_representation_rows_for_product_ids",
    "load_semantic_analysis_by_query_id",
    "run_failure_analysis_from_evaluation_dir",
    "write_failure_analysis_artifacts",
]
