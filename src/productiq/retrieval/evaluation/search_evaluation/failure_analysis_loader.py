"""Load Phase 12 artifacts for failure analysis (Phase 12.8)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    SearchEvaluationQuery,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    evaluation_result_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    load_validated_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SearchRankingExperimentResult,
)


@dataclass(frozen=True, slots=True)
class BaselineVariantArtifactSlice:
    variant_name: str
    variant_version: str
    artifact_path: str
    evaluated_depth: int
    ranked_by_query_id: dict[str, tuple[str, ...]]


def ranked_lists_from_baseline_artifact(path: Path) -> BaselineVariantArtifactSlice:
    resolved = Path(path)
    payload = load_baseline_run_artifact(resolved)
    validate_baseline_run_artifact(payload)
    result = evaluation_result_from_baseline_artifact(payload)
    depth = result.lineage.metric_configuration.evaluation_top_k
    ranked_by_query: dict[str, tuple[str, ...]] = {}
    for row in result.per_query:
        ranked_by_query[row.query_id] = row.ranked_product_ids
    return BaselineVariantArtifactSlice(
        variant_name=result.lineage.variant_name,
        variant_version=result.lineage.variant_version,
        artifact_path=str(resolved).replace("\\", "/"),
        evaluated_depth=depth,
        ranked_by_query_id=ranked_by_query,
    )


def load_ranking_experiment_result(path: Path) -> SearchRankingExperimentResult:
    payload = load_validated_ranking_experiment_artifact(path)
    raw = payload.get("experiment_result")
    if not isinstance(raw, dict):
        msg = "ranking experiment artifact missing experiment_result"
        raise RetrievalError(msg)
    return SearchRankingExperimentResult.model_validate(raw)


def variant_slices_from_ranking_experiment(
    result: SearchRankingExperimentResult,
) -> dict[str, BaselineVariantArtifactSlice]:
    slices: dict[str, BaselineVariantArtifactSlice] = {}
    depth = result.envelope.metric_configuration.evaluation_top_k
    for variant_result in result.variant_evaluation_results:
        ranked_by_query = {row.query_id: row.ranked_product_ids for row in variant_result.per_query}
        slices[variant_result.lineage.variant_name] = BaselineVariantArtifactSlice(
            variant_name=variant_result.lineage.variant_name,
            variant_version=variant_result.lineage.variant_version,
            artifact_path="ranking_experiment_artifact",
            evaluated_depth=depth,
            ranked_by_query_id=ranked_by_query,
        )
    return slices


def judged_products_for_query(
    query: SearchEvaluationQuery,
    *,
    min_relevant_grade: int,
) -> tuple[tuple[str, int], ...]:
    rows: list[tuple[str, int]] = []
    for judgment in query.relevance_judgments:
        if judgment.grade >= min_relevant_grade:
            rows.append((judgment.product_id, judgment.grade))
    return tuple(sorted(rows, key=lambda item: item[0]))


def load_canonical_benchmark(repo_root: Path) -> SearchEvaluationBenchmark:
    path = Path(repo_root) / "resources" / "evaluation" / "productiq_search_benchmark_v1.json"
    return load_search_evaluation_benchmark(path)


def validate_rank_in_depth(rank: int | None, *, evaluated_depth: int, product_id: str) -> None:
    if rank is not None and rank > evaluated_depth:
        msg = f"rank {rank} for {product_id!r} exceeds evaluated depth {evaluated_depth}"
        raise RetrievalError(msg)


__all__ = [
    "BaselineVariantArtifactSlice",
    "judged_products_for_query",
    "load_canonical_benchmark",
    "load_ranking_experiment_result",
    "ranked_lists_from_baseline_artifact",
    "variant_slices_from_ranking_experiment",
]
