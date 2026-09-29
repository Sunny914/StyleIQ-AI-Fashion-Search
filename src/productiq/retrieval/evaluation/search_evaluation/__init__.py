"""Search evaluation contracts (Phase 12.1) and benchmark artifacts (Phase 12.2)."""

from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    default_baseline_metric_configuration,
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_evaluation import (
    SUPPORTED_SEARCH_BASELINE_VARIANTS,
    evaluate_search_baseline,
    load_canonical_search_benchmark,
    run_bm25_search_baseline,
    run_rrf_search_baseline,
    run_semantic_search_baseline,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_BM25_VARIANT_NAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_RRF_VARIANT_NAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_VARIANT_NAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    DEFAULT_LEGACY_BINARY_RELEVANT_GRADE,
    LEGACY_LEXICAL_BENCHMARK_NAME,
    LEGACY_LEXICAL_BENCHMARK_VERSION,
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
    SEARCH_BENCHMARK_FILENAME,
    SEARCH_BENCHMARK_NAME,
    SEARCH_BENCHMARK_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_integrity import (
    SearchBenchmarkCatalogProvenance,
    SearchBenchmarkIntegritySummary,
    catalog_provenance_from_benchmark,
    sort_benchmark_for_stable_serialization,
    stable_benchmark_artifact_dict,
    summarize_search_benchmark_integrity,
    validate_search_benchmark_integrity,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    SearchBenchmarkArtifactFile,
    build_search_evaluation_request,
    default_search_benchmark_path,
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchRelevanceJudgment,
    lexical_query_to_search_evaluation_query,
    search_evaluation_benchmark_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.comparison import (
    compare_search_evaluation_variants,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_loader import (
    artifact_reference_from_baseline_payload,
    load_variant_evaluation_from_baseline_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_runner import (
    build_default_baseline_comparison_experiment_definition,
    run_default_baseline_comparison_experiment,
    run_search_evaluation_experiment,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME,
    SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
    SearchBaselineArtifactReference,
    SearchEvaluationExperimentDefinition,
    SearchEvaluationExperimentEnvelope,
    SearchEvaluationExperimentResult,
    search_evaluation_experiment_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
    build_search_failure_analysis_artifact_dict,
    validate_search_failure_analysis_artifact,
    write_search_failure_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_classifier import (
    build_failure_record,
    build_rank_lookup,
    classify_failure_category,
    retrieval_pattern_label,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_runner import (
    run_default_search_failure_analysis,
    run_search_failure_analysis,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
    SEARCH_FAILURE_ANALYSIS_FILENAME,
    SEARCH_FAILURE_ANALYSIS_NAME,
    SEARCH_FAILURE_ANALYSIS_VERSION,
    SearchFailureAnalysisConfiguration,
    SearchFailureAnalysisRecord,
    SearchFailureAnalysisResult,
    SearchFailureCategory,
    search_failure_analysis_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
    build_search_statistical_analysis_artifact_dict,
    validate_search_statistical_analysis_artifact,
    write_search_statistical_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_runner import (
    build_default_statistical_configuration,
    run_default_search_statistical_analysis,
    run_search_statistical_analysis,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
    SEARCH_STATISTICAL_ANALYSIS_FILENAME,
    SEARCH_STATISTICAL_ANALYSIS_NAME,
    SEARCH_STATISTICAL_ANALYSIS_VERSION,
    BootstrapConfiguration,
    PermutationConfiguration,
    SearchMetricStatisticalComparison,
    SearchStatisticalAnalysisConfiguration,
    SearchStatisticalAnalysisResult,
    SearchStatisticalMetricName,
    search_statistical_analysis_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.reporting import (
    REPORT_MARKDOWN_DIR,
    run_default_search_evaluation_report,
    run_search_evaluation_report,
    render_search_evaluation_report_markdown,
    validate_search_evaluation_report_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_artifact import (
    build_search_evaluation_report_artifact_dict,
    write_search_evaluation_report_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION,
    SEARCH_EVALUATION_REPORT_FILENAME,
    SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME,
    SEARCH_EVALUATION_REPORT_NAME,
    SEARCH_EVALUATION_REPORT_VERSION,
    SearchEvaluationReport,
    search_evaluation_report_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.legacy_benchmark_adapter import (
    convert_lexical_benchmark_path_to_search,
    convert_lexical_benchmark_payload_to_search,
    convert_lexical_retrieval_benchmark_to_search,
    lexical_evaluation_query_to_search_query,
)
from productiq.retrieval.evaluation.search_evaluation.mapping_executor import (
    MappingSearchEvaluationExecutor,
)
from productiq.retrieval.evaluation.search_evaluation.metrics import (
    aggregate_search_query_metrics,
    compute_search_query_metrics,
    evaluate_search_variant_metrics,
    validate_search_ranked_product_ids,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    build_ranking_experiment_artifact_dict,
    load_validated_ranking_experiment_artifact,
    validate_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_loader import (
    candidate_pool_from_rrf_baseline_artifact,
    generate_candidate_pool_from_retriever,
    load_ranking_contexts_from_parquet,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_runner import (
    build_default_search_ranking_experiment_definition,
    run_default_search_ranking_experiment,
    run_search_ranking_experiment,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
    SEARCH_RANKING_EXPERIMENT_FILENAME,
    SearchRankingExperimentDefinition,
    SearchRankingExperimentResult,
    SearchRankingVariantType,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_variant_executor import (
    FixedCandidateRankingSearchExecutor,
    SearchRankingExecutionContext,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationRequest,
    SearchEvaluationVariant,
    SearchMetricConfiguration,
    SearchRankedResultsForQuery,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchAggregateMetricResult,
    SearchEvaluationLineage,
    SearchExperimentComparison,
    SearchQueryMetricResult,
    SearchVariantEvaluationResult,
    search_experiment_comparison_to_dict,
    search_variant_evaluation_result_to_dict,
)
from productiq.retrieval.evaluation.search_evaluation.retriever_executor import (
    RetrieverSearchEvaluationExecutor,
)
from productiq.retrieval.evaluation.search_evaluation.run_context import SearchEvaluationRunContext
from productiq.retrieval.evaluation.search_evaluation.runner import (
    SearchEvaluationRunner,
    SearchEvaluationVariantExecutor,
    run_search_evaluation,
)
from productiq.retrieval.evaluation.search_evaluation.schema import (
    MAX_SEARCH_RELEVANCE_GRADE,
    MIN_SEARCH_RELEVANCE_GRADE,
    SEARCH_EVALUATION_CONTRACT_VERSION,
    SUPPORTED_SEARCH_METRIC_FAMILIES,
)

__all__ = [
    "DEFAULT_LEGACY_BINARY_RELEVANT_GRADE",
    "LEGACY_LEXICAL_BENCHMARK_NAME",
    "LEGACY_LEXICAL_BENCHMARK_VERSION",
    "MAX_SEARCH_RELEVANCE_GRADE",
    "MIN_SEARCH_RELEVANCE_GRADE",
    "SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_BASELINE_BM25_RUN_FILENAME",
    "SEARCH_BASELINE_BM25_VARIANT_NAME",
    "SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME",
    "SEARCH_BASELINE_RRF_RUN_FILENAME",
    "SEARCH_BASELINE_RRF_VARIANT_NAME",
    "SEARCH_BASELINE_SEMANTIC_RUN_FILENAME",
    "SEARCH_BASELINE_SEMANTIC_VARIANT_NAME",
    "SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_BENCHMARK_FILENAME",
    "SEARCH_BENCHMARK_NAME",
    "SEARCH_BENCHMARK_VERSION",
    "SEARCH_EVALUATION_CONTRACT_VERSION",
    "SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_FAILURE_ANALYSIS_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_FAILURE_ANALYSIS_FILENAME",
    "SEARCH_FAILURE_ANALYSIS_NAME",
    "SEARCH_FAILURE_ANALYSIS_VERSION",
    "SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_RANKING_EXPERIMENT_FILENAME",
    "SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_STATISTICAL_ANALYSIS_FILENAME",
    "SEARCH_STATISTICAL_ANALYSIS_NAME",
    "SEARCH_STATISTICAL_ANALYSIS_VERSION",
    "SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_EVALUATION_REPORT_FILENAME",
    "SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME",
    "SEARCH_EVALUATION_REPORT_NAME",
    "SEARCH_EVALUATION_REPORT_VERSION",
    "REPORT_MARKDOWN_DIR",
    "SUPPORTED_SEARCH_BASELINE_VARIANTS",
    "SUPPORTED_SEARCH_METRIC_FAMILIES",
    "BootstrapConfiguration",
    "FixedCandidateRankingSearchExecutor",
    "MappingSearchEvaluationExecutor",
    "PermutationConfiguration",
    "RetrieverSearchEvaluationExecutor",
    "SearchAggregateMetricResult",
    "SearchBaselineArtifactReference",
    "SearchBenchmarkArtifactFile",
    "SearchBenchmarkCatalogProvenance",
    "SearchBenchmarkIntegritySummary",
    "SearchEvaluationBenchmark",
    "SearchEvaluationBenchmarkMetadata",
    "SearchEvaluationExperimentDefinition",
    "SearchEvaluationExperimentEnvelope",
    "SearchEvaluationExperimentResult",
    "SearchEvaluationLineage",
    "SearchEvaluationQuery",
    "SearchEvaluationRequest",
    "SearchEvaluationRunContext",
    "SearchEvaluationRunner",
    "SearchEvaluationVariant",
    "SearchEvaluationVariantExecutor",
    "SearchExperimentComparison",
    "SearchFailureAnalysisConfiguration",
    "SearchFailureAnalysisRecord",
    "SearchFailureAnalysisResult",
    "SearchFailureCategory",
    "SearchMetricStatisticalComparison",
    "SearchMetricConfiguration",
    "SearchQueryMetricResult",
    "SearchRankedResultsForQuery",
    "SearchRankingExecutionContext",
    "SearchRankingExperimentDefinition",
    "SearchRankingExperimentResult",
    "SearchRankingVariantType",
    "SearchRelevanceJudgment",
    "SearchStatisticalAnalysisConfiguration",
    "SearchStatisticalAnalysisResult",
    "SearchStatisticalMetricName",
    "SearchEvaluationReport",
    "SearchVariantEvaluationResult",
    "aggregate_search_query_metrics",
    "artifact_reference_from_baseline_payload",
    "build_default_baseline_comparison_experiment_definition",
    "build_default_search_ranking_experiment_definition",
    "build_default_statistical_configuration",
    "build_failure_record",
    "build_rank_lookup",
    "build_ranking_experiment_artifact_dict",
    "build_search_evaluation_request",
    "build_search_failure_analysis_artifact_dict",
    "build_search_evaluation_report_artifact_dict",
    "build_search_statistical_analysis_artifact_dict",
    "candidate_pool_from_rrf_baseline_artifact",
    "catalog_provenance_from_benchmark",
    "classify_failure_category",
    "compare_search_evaluation_variants",
    "compute_search_query_metrics",
    "convert_lexical_benchmark_path_to_search",
    "convert_lexical_benchmark_payload_to_search",
    "convert_lexical_retrieval_benchmark_to_search",
    "default_baseline_metric_configuration",
    "default_search_benchmark_path",
    "evaluate_search_baseline",
    "evaluate_search_variant_metrics",
    "generate_candidate_pool_from_retriever",
    "lexical_evaluation_query_to_search_query",
    "lexical_query_to_search_evaluation_query",
    "load_baseline_run_artifact",
    "load_canonical_search_benchmark",
    "load_ranking_contexts_from_parquet",
    "load_search_evaluation_benchmark",
    "load_validated_ranking_experiment_artifact",
    "load_variant_evaluation_from_baseline_artifact",
    "retrieval_pattern_label",
    "render_search_evaluation_report_markdown",
    "run_bm25_search_baseline",
    "run_default_baseline_comparison_experiment",
    "run_default_search_failure_analysis",
    "run_default_search_statistical_analysis",
    "run_default_search_evaluation_report",
    "run_default_search_ranking_experiment",
    "run_rrf_search_baseline",
    "run_search_evaluation",
    "run_search_evaluation_experiment",
    "run_search_failure_analysis",
    "run_search_statistical_analysis",
    "run_search_evaluation_report",
    "run_search_ranking_experiment",
    "run_semantic_search_baseline",
    "search_evaluation_benchmark_to_dict",
    "search_evaluation_experiment_result_to_dict",
    "search_experiment_comparison_to_dict",
    "search_failure_analysis_result_to_dict",
    "search_evaluation_report_to_dict",
    "search_statistical_analysis_result_to_dict",
    "search_variant_evaluation_result_to_dict",
    "sort_benchmark_for_stable_serialization",
    "stable_benchmark_artifact_dict",
    "summarize_search_benchmark_integrity",
    "validate_baseline_run_artifact",
    "validate_ranking_experiment_artifact",
    "validate_search_benchmark_integrity",
    "validate_search_failure_analysis_artifact",
    "validate_search_evaluation_report_artifact",
    "validate_search_statistical_analysis_artifact",
    "validate_search_ranked_product_ids",
    "validate_shared_evaluation_envelope",
    "write_search_failure_analysis_artifact",
    "write_search_evaluation_report_artifact",
    "write_search_statistical_analysis_artifact",
]
