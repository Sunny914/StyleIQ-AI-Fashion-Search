"""Tests for Phase 10.8 LTR inference and baseline comparison."""

from __future__ import annotations

from pathlib import Path

import pytest

from productiq.exceptions import RankingError
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION
from productiq.ranking.contracts import RankingRequest
from productiq.ranking.evaluation.schema import RankingEvaluationConfig
from productiq.ranking.ltr.artifact import (
    LTR_MANIFEST_FILENAME,
    LTR_MODEL_FILENAME,
    load_ltr_model_artifact,
    load_validated_ltr_artifact,
)
from productiq.ranking.ltr.comparison import (
    LTRBaselineBenchmarkEvaluator,
    compare_baseline_ltr_metrics,
    evaluate_baseline_vs_ltr_query,
)
from productiq.ranking.ltr.compatibility import validate_ltr_artifact_for_pipeline
from productiq.ranking.ltr.config import LTRQuerySplitConfig, LTRTrainingConfig
from productiq.ranking.ltr.feature_matrix import ORDERED_LTR_FEATURE_NAMES
from productiq.ranking.ltr.inference import rank_candidates_with_ltr
from productiq.ranking.ltr.inference_config import LTR_INFERENCE_VERSION
from productiq.ranking.ltr.training import train_ltr_model
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.evaluation.unified_evaluation_schema import EvaluationMetrics
from tests.ranking.test_baseline_ranker import _candidate, _normalized
from tests.ranking.test_ltr_training import _fixture_dataset


@pytest.fixture
def trained_artifact(tmp_path: Path):
    dataset = _fixture_dataset()
    config = LTRTrainingConfig(
        num_boost_round=15,
        early_stopping_rounds=5,
        split=LTRQuerySplitConfig(split_seed=42),
    )
    _, artifact = train_ltr_model(dataset, config, artifact_directory=tmp_path / "ltr")
    return artifact


def test_valid_artifact_loads(trained_artifact, tmp_path: Path) -> None:
    loaded = load_ltr_model_artifact(tmp_path / "ltr")
    assert loaded.metadata.ltr_version == trained_artifact.metadata.ltr_version
    validate_ltr_artifact_for_pipeline(loaded)


def test_load_validated_artifact(trained_artifact, tmp_path: Path) -> None:
    validated = load_validated_ltr_artifact(tmp_path / "ltr")
    assert validated.metadata.feature_spec.feature_names == ORDERED_LTR_FEATURE_NAMES


def test_missing_directory_fails(tmp_path: Path) -> None:
    with pytest.raises(RankingError, match="artifact directory not found"):
        load_ltr_model_artifact(tmp_path / "missing")


def test_missing_model_fails(trained_artifact, tmp_path: Path) -> None:
    art_dir = tmp_path / "ltr"
    (art_dir / LTR_MODEL_FILENAME).unlink()
    with pytest.raises(RankingError, match="missing LTR model file"):
        load_ltr_model_artifact(art_dir)


def test_missing_manifest_fails(trained_artifact, tmp_path: Path) -> None:
    art_dir = tmp_path / "ltr"
    (art_dir / LTR_MANIFEST_FILENAME).unlink()
    with pytest.raises(RankingError, match="missing LTR manifest file"):
        load_ltr_model_artifact(art_dir)


def test_malformed_manifest_fails(trained_artifact, tmp_path: Path) -> None:
    art_dir = tmp_path / "ltr"
    (art_dir / LTR_MANIFEST_FILENAME).write_text("{not-json", encoding="utf-8")
    with pytest.raises(RankingError, match="manifest"):
        load_ltr_model_artifact(art_dir)


def test_feature_schema_mismatch_fails(trained_artifact) -> None:
    bad = trained_artifact.metadata.model_copy(
        update={
            "feature_spec": trained_artifact.metadata.feature_spec.model_copy(
                update={"feature_schema_version": "99.0.0"},
            ),
        },
    )
    broken = type(trained_artifact)(metadata=bad, booster=trained_artifact.booster)
    with pytest.raises(RankingError, match="feature_schema_version"):
        validate_ltr_artifact_for_pipeline(broken)


def test_normalization_mismatch_fails(trained_artifact) -> None:
    bad = trained_artifact.metadata.model_copy(
        update={
            "feature_spec": trained_artifact.metadata.feature_spec.model_copy(
                update={"normalization_schema_version": "99.0.0"},
            ),
        },
    )
    broken = type(trained_artifact)(metadata=bad, booster=trained_artifact.booster)
    with pytest.raises(RankingError, match="normalization_schema_version"):
        validate_ltr_artifact_for_pipeline(broken)


def test_feature_order_mismatch_fails(trained_artifact) -> None:
    bad = trained_artifact.metadata.model_copy(
        update={
            "feature_spec": trained_artifact.metadata.feature_spec.model_copy(
                update={"feature_order_version": "99.0.0"},
            ),
        },
    )
    broken = type(trained_artifact)(metadata=bad, booster=trained_artifact.booster)
    with pytest.raises(RankingError, match="feature_order_version"):
        validate_ltr_artifact_for_pipeline(broken)


def test_missing_value_policy_mismatch_fails(trained_artifact) -> None:
    bad = trained_artifact.metadata.model_copy(
        update={
            "feature_spec": trained_artifact.metadata.feature_spec.model_copy(
                update={"missing_value_policy_version": "legacy-zero"},
            ),
        },
    )
    broken = type(trained_artifact)(metadata=bad, booster=trained_artifact.booster)
    with pytest.raises(RankingError, match="missing_value_policy_version"):
        validate_ltr_artifact_for_pipeline(broken)


def test_feature_count_mismatch_fails(trained_artifact) -> None:
    bad = trained_artifact.metadata.model_copy(
        update={
            "feature_spec": trained_artifact.metadata.feature_spec.model_copy(
                update={"feature_dimension": 3},
            ),
        },
    )
    broken = type(trained_artifact)(metadata=bad, booster=trained_artifact.booster)
    with pytest.raises(RankingError, match="feature_dimension"):
        validate_ltr_artifact_for_pipeline(broken)


def test_ltr_inference_score_count(trained_artifact) -> None:
    dataset = _fixture_dataset()
    row = dataset.rows[0]
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(_candidate(row.product_id),),
        top_k=5,
    )
    response = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id={row.product_id: row.features},
        artifact=trained_artifact,
    )
    assert len(response.ranked_candidates) == 1
    assert response.ranked_candidates[0].product_id == row.product_id


def test_ltr_deterministic_ranking_and_tie_break(trained_artifact) -> None:
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(_candidate("P_B"), _candidate("P_A")),
        top_k=10,
    )
    shared = _normalized("P_A", retrieval={"bm25_score": 0.5, "rrf_score": 0.5})
    shared_b = shared.model_copy(update={"product_id": "P_B", "raw": shared.raw.model_copy(update={"product_id": "P_B"})})
    features = {"P_A": shared, "P_B": shared_b}
    first = rank_candidates_with_ltr(request=request, normalized_features_by_product_id=features, artifact=trained_artifact)
    second = rank_candidates_with_ltr(request=request, normalized_features_by_product_id=features, artifact=trained_artifact)
    assert [row.product_id for row in first.ranked_candidates] == [row.product_id for row in second.ranked_candidates]
    if first.ranked_candidates[0].ranking_score == first.ranked_candidates[1].ranking_score:
        assert first.ranked_candidates[0].product_id == "P_A"


def test_ltr_contiguous_ranks_and_top_k(trained_artifact) -> None:
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(_candidate("P1"), _candidate("P2"), _candidate("P3")),
        top_k=2,
    )
    features = {
        pid: _normalized(pid, retrieval={"bm25_score": float(index) * 0.1})
        for index, pid in enumerate(("P1", "P2", "P3"), start=1)
    }
    response = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=features,
        artifact=trained_artifact,
    )
    assert len(response.ranked_candidates) == 2
    assert [row.rank for row in response.ranked_candidates] == [1, 2]


def test_ltr_nan_handling(trained_artifact) -> None:
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(_candidate("P1"),),
        top_k=1,
    )
    features = {"P1": _normalized("P1", retrieval={"bm25_score": None})}
    response = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=features,
        artifact=trained_artifact,
    )
    assert response.ranked_candidates[0].product_id == "P1"


def test_product_id_mismatch_rejected(trained_artifact) -> None:
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(_candidate("P1"),),
        top_k=1,
    )
    with pytest.raises(RankingError, match="product_id"):
        rank_candidates_with_ltr(
            request=request,
            normalized_features_by_product_id={"P1": _normalized("OTHER")},
            artifact=trained_artifact,
        )


def test_empty_candidates_returns_empty(trained_artifact) -> None:
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=(),
        top_k=5,
    )
    response = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id={},
        artifact=trained_artifact,
    )
    assert response.ranked_candidates == ()
    assert response.config.ranking_version == LTR_INFERENCE_VERSION


def test_comparison_delta_calculation() -> None:
    baseline = EvaluationMetrics(
        query_count=1,
        recall_aggregate_query_count=1,
        k_values=(1, 5),
        mrr=0.5,
        mean_precision_at_k={1: 0.2, 5: 0.4},
        mean_recall_at_k={1: 0.1, 5: 0.3},
    )
    ltr = EvaluationMetrics(
        query_count=1,
        recall_aggregate_query_count=1,
        k_values=(1, 5),
        mrr=0.7,
        mean_precision_at_k={1: 0.3, 5: 0.5},
        mean_recall_at_k={1: 0.2, 5: 0.4},
    )
    comparison = compare_baseline_ltr_metrics(baseline=baseline, ltr=ltr, k_values=(1, 5))
    assert comparison.mrr.delta == pytest.approx(0.2)
    assert comparison.precision_at_k[1].delta == pytest.approx(0.1)


def test_evaluate_query_same_pool_metrics() -> None:
    query = LexicalEvaluationQuery(
        query_id="q1",
        query_text="demo",
        category="demo",
        relevant_product_ids=("R1", "R2"),
    )
    config = RankingEvaluationConfig(evaluation_top_k=5, k_values=(1, 5, 10))
    row = evaluate_baseline_vs_ltr_query(
        query,
        baseline_ranked_product_ids=("R1", "X", "R2"),
        ltr_ranked_product_ids=("X", "R1", "R2"),
        filtered_pool_product_ids=("R1", "X", "R2"),
        config=config,
    )
    assert row.baseline.metrics.reciprocal_rank == pytest.approx(1.0)
    assert row.ltr.metrics.reciprocal_rank == pytest.approx(0.5)
    assert row.filtered_pool_candidate_count == 3


def test_benchmark_evaluator_from_lists(trained_artifact) -> None:
    benchmark = LexicalRetrievalBenchmark(
        benchmark_name="demo",
        benchmark_version="1",
        catalog_artifact="x",
        methodology="test",
        limitations="test",
        queries=(
            LexicalEvaluationQuery(
                query_id="q1",
                query_text="t",
                category="c",
                relevant_product_ids=("A",),
            ),
        ),
    )
    evaluator = LTRBaselineBenchmarkEvaluator(
        RankingEvaluationConfig(evaluation_top_k=3, k_values=(1, 5), candidate_pool_top_k=10),
    )
    result = evaluator.evaluate_from_lists(
        benchmark,
        baseline_by_query_id={"q1": ("A", "B")},
        ltr_by_query_id={"q1": ("B", "A")},
        pool_by_query_id={"q1": ("A", "B", "C")},
        artifact=trained_artifact,
    )
    assert result.lineage.baseline_ranking_version == BASELINE_RANKER_VERSION
    assert result.lineage.ltr_inference_version == LTR_INFERENCE_VERSION
    assert result.comparison.mrr.baseline == result.baseline.mrr
    assert result.comparison.mrr.ltr == result.ltr.mrr


def test_evaluate_empty_ranked_lists() -> None:
    query = LexicalEvaluationQuery(
        query_id="q0",
        query_text="demo",
        category="demo",
        relevant_product_ids=("R1",),
    )
    config = RankingEvaluationConfig(evaluation_top_k=5, k_values=(1,))
    row = evaluate_baseline_vs_ltr_query(
        query,
        baseline_ranked_product_ids=(),
        ltr_ranked_product_ids=(),
        filtered_pool_product_ids=(),
        config=config,
    )
    assert row.filtered_pool_candidate_count == 0


def test_repeated_inference_identical(trained_artifact) -> None:
    dataset = _fixture_dataset()
    rows = dataset.rows[:3]
    request = RankingRequest(
        query=build_query_representation("demo"),
        candidates=tuple(_candidate(row.product_id) for row in rows),
        top_k=10,
    )
    feature_map = {row.product_id: row.features for row in rows}
    first = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=feature_map,
        artifact=trained_artifact,
    )
    second = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=feature_map,
        artifact=trained_artifact,
    )
    assert first.ranked_candidates == second.ranked_candidates


def test_retrieve_ranked_still_not_ltr() -> None:
    import inspect

    from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline

    source = inspect.getsource(ProductionRetrievalPipeline.retrieve_ranked)
    assert "rank_candidates_with_ltr" not in source
