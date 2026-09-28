"""Tests for Phase 10.9 ranking hardening and failure analysis."""

from __future__ import annotations

import inspect
import math

import pytest
from pydantic import ValidationError

from productiq.exceptions import RankingError
from productiq.ranking.baseline_config import BASELINE_RANKER_VERSION
from productiq.ranking.baseline_ranker import rank_candidates
from productiq.ranking.contracts import RankingRequest, RankingResponse
from productiq.ranking.evaluation import RankingBenchmarkEvaluator, evaluate_ranking_query
from productiq.ranking.evaluation.schema import RankingEvaluationConfig
from productiq.ranking.failure_analysis import (
    RankingFailureCategory,
    build_failure_records_for_query,
    build_ranking_failure_analysis_report,
    ranking_failure_record_for_ltr_incompatibility,
)
from productiq.ranking.hardening import (
    ExperimentalLTRRankingConfig,
    load_experimental_ltr_artifact,
    resolve_production_ranking_mode,
)
from productiq.ranking.invariants import (
    validate_candidate_feature_product_alignment,
    validate_positive_top_k,
    validate_ranking_response_invariants,
    validate_unique_normalized_feature_product_ids,
)
from productiq.ranking.ltr.compatibility import validate_ltr_artifact_for_pipeline
from productiq.ranking.ltr.config import LTRTrainingConfig
from productiq.ranking.ltr.inference import rank_candidates_with_ltr
from productiq.ranking.ltr.training import train_ltr_model
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery, LexicalRetrievalBenchmark
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig
from tests.ranking.test_baseline_ranker import _candidate, _normalized, _query, _unit_weight_config
from tests.ranking.test_ltr_training import _fixture_dataset


def test_duplicate_candidate_ids_rejected() -> None:
    with pytest.raises(ValidationError, match="unique product_id"):
        RankingRequest(
            query=_query(),
            candidates=(_candidate("P1"), _candidate("P1")),
            top_k=5,
        )


def test_empty_candidates_response() -> None:
    request = RankingRequest(query=_query(), candidates=(), top_k=5)
    response = rank_candidates(
        request=request,
        normalized_features_by_product_id={},
    )
    validate_ranking_response_invariants(response)
    assert response.returned_candidate_count == 0


def test_contiguous_ranks_and_top_k() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("P1"), _candidate("P2"), _candidate("P3")),
        top_k=2,
    )
    features = {
        "P1": _normalized("P1", retrieval={"rrf_score": 0.1}),
        "P2": _normalized("P2", retrieval={"rrf_score": 0.9}),
        "P3": _normalized("P3", retrieval={"rrf_score": 0.5}),
    }
    response = rank_candidates(
        request=request,
        normalized_features_by_product_id=features,
        baseline_config=config,
    )
    validate_ranking_response_invariants(response)
    assert len(response.ranked_candidates) == 2
    assert [row.rank for row in response.ranked_candidates] == [1, 2]


def test_invalid_top_k_rejected() -> None:
    with pytest.raises(ValidationError):
        RankingRequest(query=_query(), candidates=(_candidate("P1"),), top_k=0)
    with pytest.raises(RankingError):
        validate_positive_top_k(0)


def test_deterministic_baseline_ordering() -> None:
    config = _unit_weight_config(rrf_score=1.0)
    request = RankingRequest(
        query=_query(),
        candidates=(_candidate("B"), _candidate("A")),
        top_k=10,
    )
    tie_score = _normalized("A", retrieval={"rrf_score": 0.5})
    tie_b = tie_score.model_copy(
        update={"product_id": "B", "raw": tie_score.raw.model_copy(update={"product_id": "B"})},
    )
    features = {"A": tie_score, "B": tie_b}
    first = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    second = rank_candidates(request=request, normalized_features_by_product_id=features, baseline_config=config)
    assert first.ranked_candidates == second.ranked_candidates
    assert first.ranked_candidates[0].product_id == "A"


def test_feature_alignment_mismatch() -> None:
    with pytest.raises(RankingError, match="product_id"):
        validate_candidate_feature_product_alignment(
            (_candidate("P1"),),
            (_normalized("P2"),),
        )


def test_duplicate_feature_ids_rejected() -> None:
    with pytest.raises(RankingError, match="unique product_id"):
        validate_unique_normalized_feature_product_ids((_normalized("P1"), _normalized("P1")))


def test_missing_feature_row_rejected() -> None:
    request = RankingRequest(query=_query(), candidates=(_candidate("P1"),), top_k=5)
    with pytest.raises(RankingError, match="missing normalized features"):
        rank_candidates(request=request, normalized_features_by_product_id={})


def test_ltr_incompatible_artifact_rejected() -> None:
    _, artifact = train_ltr_model(_fixture_dataset(), LTRTrainingConfig(num_boost_round=5))
    bad = artifact.metadata.model_copy(
        update={
            "feature_spec": artifact.metadata.feature_spec.model_copy(
                update={"feature_order_version": "99.0.0"},
            ),
        },
    )
    broken = type(artifact)(metadata=bad, booster=artifact.booster)
    with pytest.raises(RankingError):
        validate_ltr_artifact_for_pipeline(broken)


def test_ltr_deterministic_inference() -> None:
    _, artifact = train_ltr_model(_fixture_dataset(), LTRTrainingConfig(num_boost_round=10))
    dataset = _fixture_dataset()
    rows = dataset.rows[:2]
    request = RankingRequest(
        query=_query(),
        candidates=tuple(_candidate(row.product_id) for row in rows),
        top_k=10,
    )
    feature_map = {row.product_id: row.features for row in rows}
    first = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=feature_map,
        artifact=artifact,
    )
    second = rank_candidates_with_ltr(
        request=request,
        normalized_features_by_product_id=feature_map,
        artifact=artifact,
    )
    assert first == second


def test_production_retrieve_ranked_no_ltr() -> None:
    source = inspect.getsource(ProductionRetrievalPipeline.retrieve_ranked)
    assert "rank_candidates_with_ltr" not in source


def test_production_default_baseline_mode() -> None:
    stage = ProductionRankingStageConfig()
    assert stage.experimental_ltr.enabled is False
    assert resolve_production_ranking_mode(stage) == BASELINE_RANKER_VERSION


def test_experimental_ltr_disabled_raises_on_load() -> None:
    stage = ProductionRankingStageConfig()
    with pytest.raises(RankingError, match="disabled"):
        load_experimental_ltr_artifact(stage)


def test_experimental_ltr_enabled_requires_path() -> None:
    with pytest.raises(ValidationError):
        ExperimentalLTRRankingConfig(enabled=True, artifact_directory=None)


def test_failure_analysis_separates_facts_from_hypotheses() -> None:
    query = LexicalEvaluationQuery(
        query_id="q1",
        query_text="demo",
        category="demo",
        relevant_product_ids=("R1", "R2"),
    )
    row = evaluate_ranking_query(
        query,
        rrf_ordered_product_ids=("X",),
        baseline_ranked_product_ids=("X",),
        filtered_pool_product_ids=("X",),
        config=RankingEvaluationConfig(evaluation_top_k=5, k_values=(1, 5)),
    )
    records = build_failure_records_for_query(row)
    assert records
    record = records[0]
    assert record.observed_facts
    assert record.diagnosis_hypotheses
    assert record.category == RankingFailureCategory.RELEVANT_NOT_IN_CANDIDATE_POOL
    assert record.diagnosis_hypotheses[0].startswith("Hypothesis:")


def test_failure_report_from_evaluation() -> None:
    benchmark = LexicalRetrievalBenchmark(
        benchmark_name="demo",
        benchmark_version="1",
        catalog_artifact="x",
        methodology="t",
        limitations="t",
        queries=(
            LexicalEvaluationQuery(
                query_id="q1",
                query_text="t",
                category="c",
                relevant_product_ids=("A",),
            ),
        ),
    )
    evaluator = RankingBenchmarkEvaluator(RankingEvaluationConfig(k_values=(1, 5)))
    result = evaluator.evaluate_from_lists(
        benchmark,
        rrf_by_query_id={"q1": ("A",)},
        baseline_by_query_id={"q1": ("A",)},
        pool_by_query_id={"q1": ("A",)},
    )
    report = build_ranking_failure_analysis_report(benchmark, result)
    assert report.production_ranking_baseline_version == BASELINE_RANKER_VERSION


def test_ltr_incompatibility_record() -> None:
    record = ranking_failure_record_for_ltr_incompatibility(
        query_id="q1",
        error_message="feature_schema_version incompatible",
    )
    assert record.category == RankingFailureCategory.LTR_ARTIFACT_INCOMPATIBLE
    assert "RankingError" in record.observed_facts[0]


def test_ranking_response_finite_scores_enforced() -> None:
    from productiq.ranking.config import RankingConfig
    from productiq.ranking.contracts import RankedCandidate

    candidate = _candidate("P1")
    with pytest.raises(ValidationError, match="finite"):
        RankedCandidate(
            product_id="P1",
            rank=1,
            ranking_score=math.inf,
            candidate=candidate,
        )
    good = RankedCandidate(
        product_id="P1",
        rank=1,
        ranking_score=1.0,
        candidate=candidate,
    )
    validate_ranking_response_invariants(
        RankingResponse(
            ranked_candidates=(good,),
            requested_top_k=1,
            config=RankingConfig(),
        )
    )
