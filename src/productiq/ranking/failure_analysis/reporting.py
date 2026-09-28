"""Ranking failure-analysis report assembly (Phase 10.9)."""

from __future__ import annotations

from pathlib import Path

from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION
from productiq.ranking.evaluation.schema import RankingBenchmarkEvaluationResult
from productiq.ranking.failure_analysis.analyzer import build_ranking_failure_records_from_benchmark
from productiq.ranking.failure_analysis.schema import (
    RANKING_FAILURE_ANALYSIS_FILENAME,
    RankingFailureAnalysisReport,
    RankingOperationalMeasurement,
)
from productiq.retrieval.evaluation.dataset import LexicalRetrievalBenchmark
from productiq.retrieval.ranked_search import RankedSearchTimingsMs


def operational_measurements_from_timings(
    timings: RankedSearchTimingsMs | None,
    *,
    candidate_pool_size: int | None,
    returned_count: int | None,
    requested_top_k: int | None,
) -> tuple[RankingOperationalMeasurement, ...]:
    rows: list[RankingOperationalMeasurement] = []
    if candidate_pool_size is not None:
        rows.append(
            RankingOperationalMeasurement(
                label="candidate_pool_size",
                value=candidate_pool_size,
                measurement_kind="benchmark/test measurement",
            )
        )
    if requested_top_k is not None:
        rows.append(
            RankingOperationalMeasurement(
                label="requested_top_k",
                value=requested_top_k,
                measurement_kind="implementation property",
            )
        )
    if returned_count is not None:
        rows.append(
            RankingOperationalMeasurement(
                label="returned_candidate_count",
                value=returned_count,
                measurement_kind="benchmark/test measurement",
            )
        )
    if timings is None:
        rows.append(
            RankingOperationalMeasurement(
                label="ranked_search_timings_ms",
                value=None,
                measurement_kind="not yet measured",
            )
        )
        return tuple(rows)
    for field_name in (
        "retrieval_ms",
        "feature_extraction_ms",
        "normalization_ms",
        "ranking_ms",
        "total_ms",
    ):
        value = getattr(timings, field_name)
        kind = "benchmark/test measurement" if value is not None else "not yet measured"
        rows.append(
            RankingOperationalMeasurement(
                label=field_name,
                value=value,
                measurement_kind=kind,
            )
        )
    rows.append(
        RankingOperationalMeasurement(
            label="ltr_inference_ms",
            value=None,
            measurement_kind="not yet measured",
        )
    )
    return tuple(rows)


def build_ranking_failure_analysis_report(
    benchmark: LexicalRetrievalBenchmark,
    evaluation: RankingBenchmarkEvaluationResult,
    *,
    operational_measurements: tuple[RankingOperationalMeasurement, ...] = (),
) -> RankingFailureAnalysisReport:
    judged_total = sum(len(query.relevant_product_ids) for query in benchmark.queries)
    return RankingFailureAnalysisReport(
        benchmark_name=benchmark.benchmark_name,
        benchmark_version=benchmark.benchmark_version,
        query_count=len(benchmark.queries),
        judged_relevance_count=judged_total,
        production_ranking_baseline_version=BASELINE_RANKER_VERSION,
        records=build_ranking_failure_records_from_benchmark(benchmark, evaluation),
        operational_measurements=operational_measurements,
    )


def write_ranking_failure_analysis_report(
    report: RankingFailureAnalysisReport,
    directory: Path,
    *,
    filename: str = RANKING_FAILURE_ANALYSIS_FILENAME,
) -> Path:
    resolved = Path(directory)
    resolved.mkdir(parents=True, exist_ok=True)
    path = resolved / filename
    path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return path


__all__ = [
    "build_ranking_failure_analysis_report",
    "operational_measurements_from_timings",
    "write_ranking_failure_analysis_report",
]
