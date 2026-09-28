"""Retrieval quality evaluation (Phase 4.8 lexical, Phase 4.14 semantic)."""

from productiq.retrieval.evaluation.benchmark_index import build_benchmark_scoped_bm25_retriever
from productiq.retrieval.evaluation.contracts import (
    AggregateMetricValues,
    LexicalRetrievalEvaluationResult,
    PerQueryMetricValues,
    QueryEvaluationResult,
)
from productiq.retrieval.evaluation.dataset import (
    LexicalEvaluationQuery,
    LexicalRetrievalBenchmark,
    default_benchmark_path,
    lexical_retrieval_benchmark_to_dict,
    load_lexical_retrieval_benchmark,
)
from productiq.retrieval.evaluation.evaluator import LexicalRetrievalEvaluator
from productiq.retrieval.evaluation.failure_analysis_schema import (
    RETRIEVAL_FAILURE_ANALYSIS_FILENAME,
    RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME,
    RETRIEVAL_FAILURE_SUMMARY_FILENAME,
)
from productiq.retrieval.evaluation.failure_reporting import (
    run_failure_analysis_from_evaluation_dir,
    write_failure_analysis_artifacts,
)
from productiq.retrieval.evaluation.metrics import (
    count_relevant_in_prefix,
    macro_mean,
    mean_reciprocal_rank,
    normalize_relevant_product_ids,
    normalize_retrieved_product_ids,
    precision_at_k,
    recall_at_k,
    reciprocal_rank,
    validate_positive_k,
)
from productiq.retrieval.evaluation.schema import (
    DEFAULT_EVALUATION_K_VALUES,
    DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
    LEXICAL_RETRIEVAL_BENCHMARK_FILENAME,
    LEXICAL_RETRIEVAL_BENCHMARK_VERSION,
)
from productiq.retrieval.evaluation.semantic_catalog_validation import (
    collect_benchmark_product_ids,
    validate_benchmark_product_ids_in_catalog,
)
from productiq.retrieval.evaluation.semantic_dataset import (
    DEFAULT_RELEVANCE_POLICY,
    SemanticRetrievalBenchmark,
    default_semantic_benchmark_path,
    judged_relevant_product_count,
    load_semantic_retrieval_benchmark,
    semantic_retrieval_benchmark_to_dict,
)
from productiq.retrieval.evaluation.semantic_evaluator import (
    SemanticRetrievalEvaluationContext,
    SemanticRetrievalEvaluationOutput,
    SemanticRetrievalEvaluator,
    build_per_query_analysis_rows,
)
from productiq.retrieval.evaluation.semantic_schema import (
    SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME,
    SEMANTIC_RETRIEVAL_BENCHMARK_FILENAME,
    SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME,
    SEMANTIC_RETRIEVAL_BENCHMARK_VERSION,
    SEMANTIC_RETRIEVAL_METHOD,
)
from productiq.retrieval.evaluation.unified_comparison import compare_evaluation_results
from productiq.retrieval.evaluation.unified_evaluation_schema import (
    RETRIEVAL_COMPARISON_V1_FILENAME,
    RETRIEVAL_EVALUATION_V1_FILENAME,
    RETRIEVAL_EVALUATION_V1_JSONL_FILENAME,
)
from productiq.retrieval.evaluation.unified_reporting import (
    build_catalog_from_evaluation_dir,
    write_unified_evaluation_artifacts,
)

__all__ = [
    "DEFAULT_EVALUATION_K_VALUES",
    "DEFAULT_RELEVANCE_POLICY",
    "DEFAULT_RETRIEVAL_EVALUATION_TOP_K",
    "LEXICAL_RETRIEVAL_BENCHMARK_FILENAME",
    "LEXICAL_RETRIEVAL_BENCHMARK_VERSION",
    "RETRIEVAL_COMPARISON_V1_FILENAME",
    "RETRIEVAL_EVALUATION_V1_FILENAME",
    "RETRIEVAL_EVALUATION_V1_JSONL_FILENAME",
    "RETRIEVAL_FAILURE_ANALYSIS_FILENAME",
    "RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME",
    "RETRIEVAL_FAILURE_SUMMARY_FILENAME",
    "SEMANTIC_RETRIEVAL_ANALYSIS_FILENAME",
    "SEMANTIC_RETRIEVAL_BENCHMARK_FILENAME",
    "SEMANTIC_RETRIEVAL_BENCHMARK_RUN_FILENAME",
    "SEMANTIC_RETRIEVAL_BENCHMARK_VERSION",
    "SEMANTIC_RETRIEVAL_METHOD",
    "AggregateMetricValues",
    "LexicalEvaluationQuery",
    "LexicalRetrievalBenchmark",
    "LexicalRetrievalEvaluationResult",
    "LexicalRetrievalEvaluator",
    "PerQueryMetricValues",
    "QueryEvaluationResult",
    "SemanticRetrievalBenchmark",
    "SemanticRetrievalEvaluationContext",
    "SemanticRetrievalEvaluationOutput",
    "SemanticRetrievalEvaluator",
    "build_benchmark_scoped_bm25_retriever",
    "build_catalog_from_evaluation_dir",
    "build_per_query_analysis_rows",
    "collect_benchmark_product_ids",
    "compare_evaluation_results",
    "count_relevant_in_prefix",
    "default_benchmark_path",
    "default_semantic_benchmark_path",
    "judged_relevant_product_count",
    "lexical_retrieval_benchmark_to_dict",
    "load_lexical_retrieval_benchmark",
    "load_semantic_retrieval_benchmark",
    "macro_mean",
    "mean_reciprocal_rank",
    "normalize_relevant_product_ids",
    "normalize_retrieved_product_ids",
    "precision_at_k",
    "recall_at_k",
    "reciprocal_rank",
    "run_failure_analysis_from_evaluation_dir",
    "semantic_retrieval_benchmark_to_dict",
    "validate_benchmark_product_ids_in_catalog",
    "validate_positive_k",
    "write_failure_analysis_artifacts",
    "write_unified_evaluation_artifacts",
]
