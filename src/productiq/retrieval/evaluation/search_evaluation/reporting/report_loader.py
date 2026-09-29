"""Load Phase 12 source artifacts for evaluation reporting (Phase 12.10)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    evaluation_result_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME,
    SearchEvaluationExperimentResult,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
    validate_search_failure_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_FILENAME,
    SearchFailureAnalysisResult,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    load_validated_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_FILENAME,
    SearchRankingExperimentResult,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
    validate_search_statistical_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_FILENAME,
    SearchStatisticalAnalysisResult,
)


@dataclass(frozen=True)
class BaselineArtifactBundle:
    artifact_path: str
    payload: dict[str, object]
    evaluation_result: SearchVariantEvaluationResult


@dataclass(frozen=True)
class OptionalArtifactBundle:
    artifact_path: str
    payload: dict[str, object]


@dataclass(frozen=True)
class SearchEvaluationReportSources:
    repo_root: Path
    benchmark: SearchEvaluationBenchmark
    benchmark_path: str
    benchmark_payload: dict[str, object]
    baselines: tuple[BaselineArtifactBundle, ...]
    baseline_experiment: SearchEvaluationExperimentResult | None
    baseline_experiment_payload: dict[str, object] | None
    ranking_experiment: SearchRankingExperimentResult | None
    ranking_experiment_payload: dict[str, object] | None
    failure_analysis: SearchFailureAnalysisResult | None
    failure_analysis_payload: dict[str, object] | None
    statistical_analysis: SearchStatisticalAnalysisResult | None
    statistical_analysis_payload: dict[str, object] | None


def _read_json(path: Path) -> dict[str, object]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        msg = f"artifact must be a JSON object: {path}"
        raise RetrievalError(msg)
    return raw


def _load_baseline_bundle(repo_root: Path, filename: str) -> BaselineArtifactBundle:
    path = repo_root / "resources" / "evaluation" / filename
    rel = f"resources/evaluation/{filename}"
    if not path.is_file():
        msg = f"missing baseline artifact required for reporting: {path}"
        raise RetrievalError(msg)
    payload = load_baseline_run_artifact(path)
    validate_baseline_run_artifact(payload)
    result = evaluation_result_from_baseline_artifact(payload)
    return BaselineArtifactBundle(artifact_path=rel, payload=payload, evaluation_result=result)


def load_search_evaluation_report_sources(repo_root: Path) -> SearchEvaluationReportSources:
    root = Path(repo_root)
    eval_dir = root / "resources" / "evaluation"
    benchmark_path = eval_dir / SEARCH_BENCHMARK_FILENAME
    if not benchmark_path.is_file():
        msg = f"missing benchmark artifact: {benchmark_path}"
        raise RetrievalError(msg)
    benchmark_rel = f"resources/evaluation/{SEARCH_BENCHMARK_FILENAME}"
    benchmark_payload = _read_json(benchmark_path)
    benchmark = load_search_evaluation_benchmark(benchmark_path)

    baselines = (
        _load_baseline_bundle(root, SEARCH_BASELINE_BM25_RUN_FILENAME),
        _load_baseline_bundle(root, SEARCH_BASELINE_SEMANTIC_RUN_FILENAME),
        _load_baseline_bundle(root, SEARCH_BASELINE_RRF_RUN_FILENAME),
    )

    baseline_experiment: SearchEvaluationExperimentResult | None = None
    baseline_experiment_payload: dict[str, object] | None = None
    exp_path = eval_dir / SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME
    if exp_path.is_file():
        baseline_experiment_payload = _read_json(exp_path)
        raw = baseline_experiment_payload.get("experiment_result")
        if not isinstance(raw, dict):
            msg = "12.6 experiment artifact missing experiment_result"
            raise RetrievalError(msg)
        baseline_experiment = SearchEvaluationExperimentResult.model_validate(raw)

    ranking_experiment: SearchRankingExperimentResult | None = None
    ranking_experiment_payload: dict[str, object] | None = None
    rank_path = eval_dir / SEARCH_RANKING_EXPERIMENT_FILENAME
    if rank_path.is_file():
        ranking_experiment_payload = load_validated_ranking_experiment_artifact(rank_path)
        raw = ranking_experiment_payload.get("experiment_result")
        if not isinstance(raw, dict):
            msg = "12.7 ranking artifact missing experiment_result"
            raise RetrievalError(msg)
        ranking_experiment = SearchRankingExperimentResult.model_validate(raw)

    failure_analysis: SearchFailureAnalysisResult | None = None
    failure_analysis_payload: dict[str, object] | None = None
    fail_path = eval_dir / SEARCH_FAILURE_ANALYSIS_FILENAME
    if fail_path.is_file():
        failure_analysis_payload = _read_json(fail_path)
        validate_search_failure_analysis_artifact(failure_analysis_payload)
        raw = failure_analysis_payload.get("analysis_result")
        if not isinstance(raw, dict):
            msg = "12.8 failure artifact missing analysis_result"
            raise RetrievalError(msg)
        failure_analysis = SearchFailureAnalysisResult.model_validate(raw)

    statistical_analysis: SearchStatisticalAnalysisResult | None = None
    statistical_analysis_payload: dict[str, object] | None = None
    stat_path = eval_dir / SEARCH_STATISTICAL_ANALYSIS_FILENAME
    if stat_path.is_file():
        statistical_analysis_payload = _read_json(stat_path)
        validate_search_statistical_analysis_artifact(statistical_analysis_payload)
        raw = statistical_analysis_payload.get("analysis_result")
        if not isinstance(raw, dict):
            msg = "12.9 statistical artifact missing analysis_result"
            raise RetrievalError(msg)
        statistical_analysis = SearchStatisticalAnalysisResult.model_validate(raw)

    return SearchEvaluationReportSources(
        repo_root=root,
        benchmark=benchmark,
        benchmark_path=benchmark_rel,
        benchmark_payload=benchmark_payload,
        baselines=baselines,
        baseline_experiment=baseline_experiment,
        baseline_experiment_payload=baseline_experiment_payload,
        ranking_experiment=ranking_experiment,
        ranking_experiment_payload=ranking_experiment_payload,
        failure_analysis=failure_analysis,
        failure_analysis_payload=failure_analysis_payload,
        statistical_analysis=statistical_analysis,
        statistical_analysis_payload=statistical_analysis_payload,
    )


__all__ = [
    "BaselineArtifactBundle",
    "SearchEvaluationReportSources",
    "load_search_evaluation_report_sources",
]
