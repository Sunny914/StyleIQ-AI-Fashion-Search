"""Execute search ranking experiments (Phase 12.7)."""

from __future__ import annotations

import os
from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.ranking.baseline_config import BaselineRankingConfig
from productiq.ranking.ltr.artifact import LTRModelArtifact, load_validated_ltr_artifact
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    default_baseline_metric_configuration,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    build_search_evaluation_request,
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
)
from productiq.retrieval.evaluation.search_evaluation.comparison import (
    compare_search_evaluation_variants,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_loader import (
    candidate_pool_from_rrf_baseline_artifact,
    load_ranking_contexts_from_parquet,
    validate_candidate_pool_matches_definition,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_FILENAME,
    SEARCH_RANKING_EXPERIMENT_NAME,
    SEARCH_RANKING_EXPERIMENT_VERSION,
    SEARCH_RANKING_VARIANT_BASELINE_RANKER,
    SEARCH_RANKING_VARIANT_LTR,
    SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
    SEARCH_RANKING_VARIANT_VERSION,
    SearchCandidatePoolConfiguration,
    SearchRankingCandidatePool,
    SearchRankingExperimentDefinition,
    SearchRankingExperimentResult,
    SearchRankingVariantConfiguration,
    SearchRankingVariantType,
    SearchRetrievalProvenanceRecord,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_validation import (
    build_ranking_experiment_envelope,
    validate_ranking_variant_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_variant_executor import (
    FixedCandidateRankingSearchExecutor,
    SearchRankingExecutionContext,
    default_ranking_lineage_labels,
    ranking_executor_for_variant_type,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationVariant,
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)
from productiq.retrieval.evaluation.search_evaluation.runner import run_search_evaluation


def _search_variant_from_ranking_config(
    config: SearchRankingVariantConfiguration,
) -> SearchEvaluationVariant:
    return SearchEvaluationVariant(
        variant_name=config.variant_name,
        variant_version=config.variant_version,
        description=config.description,
        lineage_labels=default_ranking_lineage_labels(config.variant_type),
    )


def run_search_ranking_experiment(
    definition: SearchRankingExperimentDefinition,
    candidate_pool: SearchRankingCandidatePool,
    *,
    ranking_context: SearchRankingExecutionContext,
    benchmark: SearchEvaluationBenchmark,
) -> SearchRankingExperimentResult:
    """Evaluate ranking variants on a shared candidate pool and compute descriptive deltas."""
    validate_candidate_pool_matches_definition(
        candidate_pool,
        benchmark_name=definition.benchmark_name,
        benchmark_version=definition.benchmark_version,
        candidate_pool_configuration=definition.candidate_pool_configuration,
        retrieval_provenance=definition.retrieval_provenance,
    )
    envelope = build_ranking_experiment_envelope(definition, candidate_pool)
    candidate_sets = {row.query_id: row for row in candidate_pool.query_candidate_sets}
    expected_queries = {query.query_id for query in benchmark.queries}
    if set(candidate_sets.keys()) != expected_queries:
        msg = "candidate pool query coverage must match benchmark queries exactly"
        raise RetrievalError(msg)

    results_by_name: dict[str, SearchVariantEvaluationResult] = {}
    for variant_config in sorted(definition.ranking_variants, key=lambda row: row.variant_name):
        if (
            variant_config.variant_type is SearchRankingVariantType.LTR
            and ranking_context.ltr_artifact is None
        ):
            msg = f"LTR ranking variant {variant_config.variant_name!r} requires ltr_artifact"
            raise RetrievalError(msg)
        executor = FixedCandidateRankingSearchExecutor(
            ranking_executor=ranking_executor_for_variant_type(variant_config.variant_type),
            candidate_sets_by_query_id=candidate_sets,
            ranking_context=ranking_context,
        )
        search_variant = _search_variant_from_ranking_config(variant_config)
        request = build_search_evaluation_request(
            benchmark,
            search_variant,
            metric_configuration=definition.metric_configuration,
        )
        results_by_name[variant_config.variant_name] = run_search_evaluation(request, executor)

    typed_results: tuple[SearchVariantEvaluationResult, ...] = tuple(
        results_by_name[name] for name in sorted(results_by_name.keys())
    )
    validate_ranking_variant_envelope(typed_results, envelope)

    reference_name = definition.reference_ranking_variant_name
    reference_result = next(
        (row for row in typed_results if row.lineage.variant_name == reference_name),
        None,
    )
    if reference_result is None:
        msg = f"reference ranking variant {reference_name!r} missing from results"
        raise RetrievalError(msg)

    comparisons = []
    for row in typed_results:
        if row.lineage.variant_name == reference_name:
            continue
        comparisons.append(compare_search_evaluation_variants(reference_result, row))

    notes: list[str] = [
        "Ranking experiment comparisons report absolute metric deltas only.",
        "All ranking variants consumed the same fixed candidate set per query.",
        "No winner, best variant, or recommendation is selected.",
    ]
    if any(
        "phase_12_5_rrf_baseline_run" in row.candidate_provenance
        for row in candidate_pool.query_candidate_sets
    ):
        notes.append(
            "Candidate pool product IDs sourced from Phase 12.5 RRF baseline run; "
            "retrieval scores reconstructed for ranking feature extraction when full "
            "RetrievalCandidate rows were not persisted."
        )

    return SearchRankingExperimentResult(
        experiment_name=definition.experiment_name,
        experiment_version=definition.experiment_version,
        description=definition.description,
        reference_ranking_variant_name=reference_name,
        envelope=envelope,
        candidate_pool=candidate_pool,
        variant_evaluation_results=typed_results,
        candidate_comparisons=tuple(comparisons),
        provenance_notes=tuple(notes),
    )


def build_default_search_ranking_experiment_definition(
    benchmark: SearchEvaluationBenchmark,
    *,
    candidate_pool_top_k: int | None = None,
    include_ltr: bool = True,
) -> SearchRankingExperimentDefinition:
    metric_configuration = default_baseline_metric_configuration()
    pool_top_k = candidate_pool_top_k or metric_configuration.execution_top_k
    variants: list[SearchRankingVariantConfiguration] = [
        SearchRankingVariantConfiguration(
            variant_name=SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
            variant_version=SEARCH_RANKING_VARIANT_VERSION,
            description="Fixed-pool retrieval order reference ranking.",
            variant_type=SearchRankingVariantType.RETRIEVAL_ORDER,
        ),
        SearchRankingVariantConfiguration(
            variant_name=SEARCH_RANKING_VARIANT_BASELINE_RANKER,
            variant_version=SEARCH_RANKING_VARIANT_VERSION,
            description="Phase 10 deterministic baseline ranker on the fixed pool.",
            variant_type=SearchRankingVariantType.BASELINE_RANKER,
        ),
    ]
    if include_ltr:
        variants.append(
            SearchRankingVariantConfiguration(
                variant_name=SEARCH_RANKING_VARIANT_LTR,
                variant_version=SEARCH_RANKING_VARIANT_VERSION,
                description="Phase 10 experimental LTR inference on the fixed pool.",
                variant_type=SearchRankingVariantType.LTR,
            )
        )
    return SearchRankingExperimentDefinition(
        experiment_name=SEARCH_RANKING_EXPERIMENT_NAME,
        experiment_version=SEARCH_RANKING_EXPERIMENT_VERSION,
        description=(
            "Fixed-candidate ranking comparison on productiq_search_benchmark_v1 using "
            "Phase 12.5 RRF retrieval candidates."
        ),
        reference_ranking_variant_name=SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
        ranking_variants=tuple(sorted(variants, key=lambda row: row.variant_name)),
        candidate_pool_configuration=SearchCandidatePoolConfiguration(
            candidate_pool_top_k=pool_top_k,
            require_non_empty_candidates=True,
        ),
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        metric_configuration=metric_configuration,
        retrieval_provenance=SearchRetrievalProvenanceRecord(
            retrieval_variant_name=SEARCH_BASELINE_RRF_VARIANT_NAME,
            retrieval_variant_version="1.0.0",
            description="Phase 12.5 RRF baseline ranked_product_ids candidate pool.",
        ),
        catalog_artifact=benchmark.metadata.catalog_artifact,
        source_representation_checksum=benchmark.metadata.source_representation_checksum,
    )


def resolve_ltr_artifact_for_ranking_experiment(repo_root: Path) -> LTRModelArtifact | None:
    env_path = os.environ.get("PRODUCTIQ_EXPERIMENTAL_LTR_ARTIFACT_DIR", "").strip()
    if env_path:
        return load_validated_ltr_artifact(Path(env_path))
    default = Path(repo_root) / "resources" / "processed" / "experimental_ltr_ranker"
    if default.is_dir():
        return load_validated_ltr_artifact(default)
    reference = Path(repo_root) / "resources" / "models" / "ranking_ltr_reference_v10_7_0"
    if reference.is_dir():
        return load_validated_ltr_artifact(reference)
    return None


def build_default_ranking_execution_context(
    repo_root: Path,
    *,
    candidate_pool: SearchRankingCandidatePool,
    metric_configuration: SearchMetricConfiguration | None = None,
    ltr_artifact: LTRModelArtifact | None = None,
) -> SearchRankingExecutionContext:
    config = metric_configuration or default_baseline_metric_configuration()
    product_ids: list[str] = []
    for row in candidate_pool.query_candidate_sets:
        product_ids.extend(row.candidate_product_ids)
    parquet_path = Path(repo_root) / "resources" / "processed" / "product_representations.parquet"
    provider = load_ranking_contexts_from_parquet(tuple(product_ids), parquet_path)
    resolved_ltr = (
        ltr_artifact
        if ltr_artifact is not None
        else resolve_ltr_artifact_for_ranking_experiment(repo_root)
    )
    return SearchRankingExecutionContext(
        ranking_top_k=config.execution_top_k,
        product_context_provider=provider,
        baseline_config=BaselineRankingConfig(),
        ltr_artifact=resolved_ltr,
    )


def run_default_search_ranking_experiment(repo_root: Path) -> SearchRankingExperimentResult:
    from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
        build_ranking_experiment_artifact_dict,
        write_ranking_experiment_artifact,
    )

    root = Path(repo_root)
    benchmark = load_search_evaluation_benchmark(
        root / "resources" / "evaluation" / "productiq_search_benchmark_v1.json"
    )
    ltr_artifact = resolve_ltr_artifact_for_ranking_experiment(root)
    definition = build_default_search_ranking_experiment_definition(
        benchmark,
        include_ltr=ltr_artifact is not None,
    )
    rrf_path = root / "resources" / "evaluation" / SEARCH_BASELINE_RRF_RUN_FILENAME
    candidate_pool = candidate_pool_from_rrf_baseline_artifact(
        benchmark,
        rrf_path,
        candidate_pool_top_k=definition.candidate_pool_configuration.candidate_pool_top_k,
    ).model_copy(update={"retrieval_provenance": definition.retrieval_provenance})
    ranking_context = build_default_ranking_execution_context(
        root,
        candidate_pool=candidate_pool,
        metric_configuration=definition.metric_configuration,
        ltr_artifact=ltr_artifact,
    )
    result = run_search_ranking_experiment(
        definition,
        candidate_pool,
        ranking_context=ranking_context,
        benchmark=benchmark,
    )
    out_path = root / "resources" / "evaluation" / SEARCH_RANKING_EXPERIMENT_FILENAME
    write_ranking_experiment_artifact(
        out_path,
        build_ranking_experiment_artifact_dict(definition, result),
    )
    return result


__all__ = [
    "build_default_ranking_execution_context",
    "build_default_search_ranking_experiment_definition",
    "resolve_ltr_artifact_for_ranking_experiment",
    "run_default_search_ranking_experiment",
    "run_search_ranking_experiment",
]
