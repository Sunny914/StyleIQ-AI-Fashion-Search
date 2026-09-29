"""Run search evaluation failure analysis over Phase 12 artifacts (Phase 12.8)."""

from __future__ import annotations

from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.catalog_constraint_match import (
    constraints_are_active,
    filtering_satisfies_query_constraints,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_aggregator import (
    aggregate_by_variant_and_k,
    aggregate_retrieval_relationships,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
    build_search_failure_analysis_artifact_dict,
    write_search_failure_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_classifier import (
    build_failure_record,
    rank_for_product,
    retrieval_pattern_label,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_loader import (
    BaselineVariantArtifactSlice,
    judged_products_for_query,
    load_canonical_benchmark,
    load_ranking_experiment_result,
    ranked_lists_from_baseline_artifact,
    variant_slices_from_ranking_experiment,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_FILENAME,
    SEARCH_FAILURE_ANALYSIS_NAME,
    SEARCH_FAILURE_ANALYSIS_VERSION,
    SearchFailureAnalysisConfiguration,
    SearchFailureAnalysisLineage,
    SearchFailureAnalysisRecord,
    SearchFailureAnalysisResult,
    SearchFailureCategory,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_FILENAME,
    SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
)


def _constraint_incompatible(
    query_text: str,
    product_id: str,
    *,
    filtering_by_product_id: dict[str, object] | None,
) -> bool:
    if filtering_by_product_id is None:
        return False
    filtering = filtering_by_product_id.get(product_id)
    if filtering is None:
        return False
    from productiq.representation.filtering import FilteringRepresentation

    if not isinstance(filtering, FilteringRepresentation):
        return False
    query = build_query_representation(query_text)
    constraints = query.constraints
    if not constraints_are_active(constraints):
        return False
    assert constraints is not None
    return not filtering_satisfies_query_constraints(filtering, constraints)


def analyze_variant_slice(
    benchmark: object,
    variant_slice: BaselineVariantArtifactSlice,
    *,
    configuration: SearchFailureAnalysisConfiguration,
    reference_ranks_by_query: dict[str, dict[str, int]] | None = None,
    filtering_by_product_id: dict[str, object] | None = None,
) -> tuple[SearchFailureAnalysisRecord, ...]:
    from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
        SearchEvaluationBenchmark,
    )

    if not isinstance(benchmark, SearchEvaluationBenchmark):
        msg = "benchmark must be SearchEvaluationBenchmark"
        raise RetrievalError(msg)
    records: list[SearchFailureAnalysisRecord] = []
    ref_lookup = reference_ranks_by_query or {}
    for query in sorted(benchmark.queries, key=lambda row: row.query_id):
        ranked = variant_slice.ranked_by_query_id.get(query.query_id)
        if ranked is None:
            msg = f"variant {variant_slice.variant_name!r} missing query {query.query_id!r}"
            raise RetrievalError(msg)
        judged = judged_products_for_query(query, min_relevant_grade=configuration.min_relevant_grade)
        for analysis_k in configuration.analysis_k_values:
            for product_id, grade in judged:
                constraint_bad = configuration.enable_constraint_diagnostics and _constraint_incompatible(
                    query.query_text,
                    product_id,
                    filtering_by_product_id=filtering_by_product_id,
                )
                reference_rank = ref_lookup.get(query.query_id, {}).get(product_id)
                records.append(
                    build_failure_record(
                        query_id=query.query_id,
                        product_id=product_id,
                        relevance_grade=grade,
                        variant_name=variant_slice.variant_name,
                        variant_version=variant_slice.variant_version,
                        analysis_k=analysis_k,
                        evaluated_depth=variant_slice.evaluated_depth,
                        ranked_product_ids=ranked,
                        depth_limited_threshold=configuration.depth_limited_threshold,
                        reference_rank=reference_rank,
                        constraint_incompatible=constraint_bad,
                    )
                )
    return tuple(records)


def build_retrieval_relationship_counts(
    benchmark: object,
    bm25: BaselineVariantArtifactSlice,
    semantic: BaselineVariantArtifactSlice,
    *,
    min_relevant_grade: int,
) -> dict[str, int]:
    from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
        SearchEvaluationBenchmark,
    )

    if not isinstance(benchmark, SearchEvaluationBenchmark):
        msg = "benchmark must be SearchEvaluationBenchmark"
        raise RetrievalError(msg)
    counts: dict[str, int] = {}
    depth = min(bm25.evaluated_depth, semantic.evaluated_depth)
    for query in benchmark.queries:
        bm25_list = bm25.ranked_by_query_id.get(query.query_id, ())
        semantic_list = semantic.ranked_by_query_id.get(query.query_id, ())
        for product_id, _grade in judged_products_for_query(query, min_relevant_grade=min_relevant_grade):
            bm25_rank = rank_for_product(bm25_list, product_id)
            semantic_rank = rank_for_product(semantic_list, product_id)
            if bm25_rank is not None and bm25_rank > depth:
                bm25_rank = None
            if semantic_rank is not None and semantic_rank > depth:
                semantic_rank = None
            label = retrieval_pattern_label(
                bm25_rank=bm25_rank,
                semantic_rank=semantic_rank,
                evaluated_depth=depth,
            )
            counts[label] = counts.get(label, 0) + 1
    return counts


def run_search_failure_analysis(
    repo_root: Path,
    *,
    configuration: SearchFailureAnalysisConfiguration | None = None,
    filtering_by_product_id: dict[str, object] | None = None,
) -> SearchFailureAnalysisResult:
    """Analyze canonical Phase 12.5 baselines and optional 12.7 ranking experiment."""
    root = Path(repo_root)
    config = configuration or SearchFailureAnalysisConfiguration()
    benchmark = load_canonical_benchmark(root)
    eval_dir = root / "resources" / "evaluation"

    baseline_paths = (
        SEARCH_BASELINE_BM25_RUN_FILENAME,
        SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
        SEARCH_BASELINE_RRF_RUN_FILENAME,
    )
    slices: list[BaselineVariantArtifactSlice] = []
    artifact_refs: list[str] = []
    for filename in baseline_paths:
        path = eval_dir / filename
        if not path.is_file():
            msg = f"missing baseline artifact for failure analysis: {path}"
            raise RetrievalError(msg)
        slice_row = ranked_lists_from_baseline_artifact(path)
        slices.append(slice_row)
        artifact_refs.append(f"resources/evaluation/{filename}")

    ranking_path = eval_dir / SEARCH_RANKING_EXPERIMENT_FILENAME
    ranking_ref: str | None = None
    reference_ranks: dict[str, dict[str, int]] = {}
    reference_name: str | None = None
    if ranking_path.is_file():
        ranking_result = load_ranking_experiment_result(ranking_path)
        ranking_slices = variant_slices_from_ranking_experiment(ranking_result)
        ranking_ref = f"resources/evaluation/{SEARCH_RANKING_EXPERIMENT_FILENAME}"
        ref_slice = ranking_slices.get(ranking_result.reference_ranking_variant_name)
        if ref_slice is None:
            ref_slice = ranking_slices.get(SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER)
        if ref_slice is not None:
            from productiq.retrieval.evaluation.search_evaluation.failure_analysis_classifier import (
                build_rank_lookup,
            )

            for query_id, ranked in ref_slice.ranked_by_query_id.items():
                reference_ranks[query_id] = build_rank_lookup(
                    ranked,
                    source_label=ref_slice.variant_name,
                )
        reference_name = ref_slice.variant_name if ref_slice else None
        for _name, rank_slice in sorted(ranking_slices.items()):
            slices.append(rank_slice)

    all_records: list[SearchFailureAnalysisRecord] = []
    for variant_slice in sorted(slices, key=lambda row: row.variant_name):
        is_ranking_candidate = (
            variant_slice.artifact_path == "ranking_experiment_artifact"
            and reference_ranks
            and variant_slice.variant_name != reference_name
        )
        ref_map = reference_ranks if is_ranking_candidate else None
        all_records.extend(
            analyze_variant_slice(
                benchmark,
                variant_slice,
                configuration=config,
                reference_ranks_by_query=ref_map,
                filtering_by_product_id=filtering_by_product_id,
            )
        )

    bm25_slice = next(row for row in slices if "bm25" in row.variant_name)
    semantic_slice = next(row for row in slices if "semantic" in row.variant_name)
    pattern_counts = build_retrieval_relationship_counts(
        benchmark,
        bm25_slice,
        semantic_slice,
        min_relevant_grade=config.min_relevant_grade,
    )

    lineage = SearchFailureAnalysisLineage(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        source_baseline_artifacts=tuple(sorted(artifact_refs)),
        source_ranking_experiment_artifact=ranking_ref,
    )
    taxonomy = tuple(category.value for category in SearchFailureCategory)
    records_tuple = tuple(all_records)
    return SearchFailureAnalysisResult(
        analysis_name=SEARCH_FAILURE_ANALYSIS_NAME,
        analysis_version=SEARCH_FAILURE_ANALYSIS_VERSION,
        description="Diagnostic layer over Phase 12.5 baselines and Phase 12.7 ranking experiment artifacts.",
        configuration=config,
        lineage=lineage,
        failure_taxonomy=taxonomy,
        records=records_tuple,
        aggregates=aggregate_by_variant_and_k(records_tuple),
        retrieval_relationship_aggregates=aggregate_retrieval_relationships(pattern_counts),
    )


def run_default_search_failure_analysis(repo_root: Path) -> SearchFailureAnalysisResult:
    result = run_search_failure_analysis(repo_root)
    out_path = Path(repo_root) / "resources" / "evaluation" / SEARCH_FAILURE_ANALYSIS_FILENAME
    write_search_failure_analysis_artifact(
        out_path,
        build_search_failure_analysis_artifact_dict(result),
    )
    return result


__all__ = [
    "run_default_search_failure_analysis",
    "run_search_failure_analysis",
]
