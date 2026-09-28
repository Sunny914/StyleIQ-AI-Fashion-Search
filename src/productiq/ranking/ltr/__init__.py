"""Learning-to-Rank training and offline inference (Phase 10.7–10.8)."""

from productiq.ranking.ltr.artifact import (
    LTRModelArtifact,
    load_ltr_model_artifact,
    load_validated_ltr_artifact,
    save_ltr_model_artifact,
)
from productiq.ranking.ltr.comparison import (
    LTRBaselineBenchmarkEvaluationResult,
    LTRBaselineBenchmarkEvaluator,
    compare_baseline_ltr_metrics,
    evaluate_baseline_vs_ltr_query,
)
from productiq.ranking.ltr.config import LTRTrainingConfig
from productiq.ranking.ltr.feature_matrix import (
    ORDERED_LTR_FEATURE_NAMES,
    LTRFeatureMatrix,
    build_feature_matrix_from_dataset,
)
from productiq.ranking.ltr.inference import (
    rank_candidates_with_ltr,
    rank_candidates_with_ltr_feature_rows,
)
from productiq.ranking.ltr.inference_config import (
    LTR_BASELINE_COMPARISON_VERSION,
    LTR_INFERENCE_VERSION,
)
from productiq.ranking.ltr.predict import predict_ltr_scores
from productiq.ranking.ltr.split import QueryGroupSplit, split_ranking_dataset_by_query
from productiq.ranking.ltr.training import LTRTrainingResult, train_ltr_model
from productiq.ranking.ltr.validation import validate_ltr_training_dataset

__all__ = [
    "LTR_BASELINE_COMPARISON_VERSION",
    "LTR_INFERENCE_VERSION",
    "ORDERED_LTR_FEATURE_NAMES",
    "LTRBaselineBenchmarkEvaluationResult",
    "LTRBaselineBenchmarkEvaluator",
    "LTRFeatureMatrix",
    "LTRModelArtifact",
    "LTRTrainingConfig",
    "LTRTrainingResult",
    "QueryGroupSplit",
    "build_feature_matrix_from_dataset",
    "compare_baseline_ltr_metrics",
    "evaluate_baseline_vs_ltr_query",
    "load_ltr_model_artifact",
    "load_validated_ltr_artifact",
    "predict_ltr_scores",
    "rank_candidates_with_ltr",
    "rank_candidates_with_ltr_feature_rows",
    "save_ltr_model_artifact",
    "split_ranking_dataset_by_query",
    "train_ltr_model",
    "validate_ltr_training_dataset",
]
