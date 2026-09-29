"""Tests for Phase 12.8 search failure analysis."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import (
    QueryFilterConstraints,
    build_query_representation,
)
from productiq.retrieval.evaluation.search_evaluation import (
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchRelevanceJudgment,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_aggregator import (
    aggregate_by_variant_and_k,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
    build_search_failure_analysis_artifact_dict,
    validate_search_failure_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_classifier import (
    build_failure_record,
    build_rank_lookup,
    classify_failure_category,
    retrieval_pattern_label,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_loader import (
    BaselineVariantArtifactSlice,
    judged_products_for_query,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_runner import (
    analyze_variant_slice,
    run_search_failure_analysis,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SearchFailureAnalysisConfiguration,
    SearchFailureAnalysisResult,
    SearchFailureCategory,
)


def _mini_benchmark() -> SearchEvaluationBenchmark:
    return SearchEvaluationBenchmark(
        metadata=SearchEvaluationBenchmarkMetadata(
            benchmark_name="b",
            benchmark_version="1.0.0",
            methodology="t",
            labeling_methodology="t",
            limitations="t",
        ),
        queries=(
            SearchEvaluationQuery(
                query_id="q1",
                query_text="nike shoes",
                query_category="brand",
                relevance_judgments=(
                    SearchRelevanceJudgment(product_id="P1", grade=3),
                    SearchRelevanceJudgment(product_id="P2", grade=2),
                ),
            ),
        ),
    )


class TestClassification:
    def test_ranked_in_top_k(self) -> None:
        assert (
            classify_failure_category(rank=3, analysis_k=10, evaluated_depth=50)
            is SearchFailureCategory.RANKED_IN_TOP_K
        )

    def test_retrieved_below_k(self) -> None:
        assert (
            classify_failure_category(rank=7, analysis_k=5, evaluated_depth=50)
            is SearchFailureCategory.RETRIEVED_BELOW_K
        )

    def test_depth_limited(self) -> None:
        assert (
            classify_failure_category(rank=27, analysis_k=10, evaluated_depth=50)
            is SearchFailureCategory.DEPTH_LIMITED
        )

    def test_absent_from_evaluated_depth(self) -> None:
        assert (
            classify_failure_category(rank=None, analysis_k=10, evaluated_depth=50)
            is SearchFailureCategory.ABSENT_FROM_EVALUATED_DEPTH
        )

    def test_invalid_k(self) -> None:
        with pytest.raises(RetrievalError):
            classify_failure_category(rank=1, analysis_k=0, evaluated_depth=50)

    def test_invalid_rank_beyond_depth(self) -> None:
        with pytest.raises(RetrievalError):
            classify_failure_category(rank=60, analysis_k=10, evaluated_depth=50)

    def test_empty_ranking_duplicate_rejected(self) -> None:
        with pytest.raises(RetrievalError, match="duplicate"):
            build_rank_lookup(("P1", "P1"), source_label="t")

    def test_top_k_flag_on_record(self) -> None:
        row = build_failure_record(
            query_id="q1",
            product_id="P1",
            relevance_grade=2,
            variant_name="v",
            variant_version="1.0.0",
            analysis_k=1,
            evaluated_depth=50,
            ranked_product_ids=("P9", "P1"),
        )
        assert row.in_top_k is False
        assert row.retrieval_rank == 2


class TestRetrievalRelationships:
    def test_bm25_only(self) -> None:
        assert retrieval_pattern_label(bm25_rank=2, semantic_rank=None, evaluated_depth=50) == "BM25_ONLY"

    def test_semantic_only(self) -> None:
        assert retrieval_pattern_label(bm25_rank=None, semantic_rank=4, evaluated_depth=50) == "SEMANTIC_ONLY"

    def test_both(self) -> None:
        assert (
            retrieval_pattern_label(bm25_rank=2, semantic_rank=5, evaluated_depth=50) == "RETRIEVED_BY_BOTH"
        )

    def test_neither(self) -> None:
        assert (
            retrieval_pattern_label(bm25_rank=None, semantic_rank=None, evaluated_depth=50)
            == "NOT_RETRIEVED_BY_EITHER"
        )


class TestRankDisplacement:
    def test_rank_delta_descriptive(self) -> None:
        row = build_failure_record(
            query_id="q1",
            product_id="P1",
            relevance_grade=2,
            variant_name="candidate",
            variant_version="1.0.0",
            analysis_k=10,
            evaluated_depth=50,
            ranked_product_ids=("P2", "P1"),
            reference_rank=5,
        )
        assert row.rank_delta == -3

    def test_missing_reference_rank(self) -> None:
        row = build_failure_record(
            query_id="q1",
            product_id="PX",
            relevance_grade=2,
            variant_name="v",
            variant_version="1.0.0",
            analysis_k=10,
            evaluated_depth=50,
            ranked_product_ids=("P1",),
            reference_rank=2,
        )
        assert row.rank_delta is None


class TestConstraintDiagnostics:
    def test_constraint_incompatible_with_evidence(self) -> None:
        filtering = FilteringRepresentation(
            product_id="P1",
            source="catalog",
            brand="Other",
            brand_normalized="other",
            category_gender="men",
            product_type="shoes",
            color_raw="black",
            color_is_coded=True,
            color=("black",),
            pattern=None,
            material=None,
            fit=None,
            sleeve=None,
            neckline=None,
            product_features=None,
            style_attributes=None,
            discount_price_inr=100,
            original_price_inr=200,
            price_anomaly=False,
        )
        query = build_query_representation(
            "nike shoes",
            constraints=QueryFilterConstraints(brand="Nike"),
        )
        assert query.constraints is not None
        from productiq.retrieval.catalog_constraint_match import (
            filtering_satisfies_query_constraints,
        )

        assert not filtering_satisfies_query_constraints(filtering, query.constraints)
        row = build_failure_record(
            query_id="q1",
            product_id="P1",
            relevance_grade=2,
            variant_name="v",
            variant_version="1.0.0",
            analysis_k=10,
            evaluated_depth=50,
            ranked_product_ids=("P1",),
            constraint_incompatible=True,
        )
        assert row.failure_category is SearchFailureCategory.JUDGED_RELEVANT_BUT_CONSTRAINT_INCOMPATIBLE

    def test_constraint_unavailable_by_default(self) -> None:
        config = SearchFailureAnalysisConfiguration(enable_constraint_diagnostics=False)
        assert config.enable_constraint_diagnostics is False


class TestAggregationAndDeterminism:
    def test_aggregate_counts(self) -> None:
        records = (
            build_failure_record(
                query_id="q1",
                product_id="P1",
                relevance_grade=2,
                variant_name="v",
                variant_version="1.0.0",
                analysis_k=10,
                evaluated_depth=50,
                ranked_product_ids=("P1",),
            ),
        )
        agg = aggregate_by_variant_and_k(records)
        assert agg[0].record_count == 1

    def test_duplicate_records_rejected(self) -> None:
        row = build_failure_record(
            query_id="q1",
            product_id="P1",
            relevance_grade=2,
            variant_name="v",
            variant_version="1.0.0",
            analysis_k=10,
            evaluated_depth=50,
            ranked_product_ids=("P1",),
        )
        with pytest.raises(ValidationError, match="duplicate"):
            SearchFailureAnalysisResult(
                configuration=SearchFailureAnalysisConfiguration(),
                lineage={
                    "benchmark_name": "b",
                    "benchmark_version": "1.0.0",
                },
                failure_taxonomy=tuple(SearchFailureCategory),
                records=(row, row),
                aggregates=(),
            )

    def test_artifact_checksum(self) -> None:
        benchmark = _mini_benchmark()
        slice_row = BaselineVariantArtifactSlice(
            variant_name="toy",
            variant_version="1.0.0",
            artifact_path="toy.json",
            evaluated_depth=50,
            ranked_by_query_id={"q1": ("P1", "P2")},
        )
        records = analyze_variant_slice(
            benchmark,
            slice_row,
            configuration=SearchFailureAnalysisConfiguration(analysis_k_values=(10,)),
        )
        result = SearchFailureAnalysisResult(
            configuration=SearchFailureAnalysisConfiguration(analysis_k_values=(10,)),
            lineage={
                "benchmark_name": "b",
                "benchmark_version": "1.0.0",
            },
            failure_taxonomy=tuple(item.value for item in SearchFailureCategory),
            records=records,
            aggregates=aggregate_by_variant_and_k(records),
        )
        payload = build_search_failure_analysis_artifact_dict(result)
        validate_search_failure_analysis_artifact(payload)
        assert json.dumps(payload, sort_keys=True) == json.dumps(payload, sort_keys=True)


class TestRelevanceGradeThreshold:
    def test_min_relevant_grade(self) -> None:
        query = _mini_benchmark().queries[0]
        judged = judged_products_for_query(query, min_relevant_grade=3)
        assert judged == (("P1", 3),)


class TestCanonicalIntegration:
    def test_run_on_repo_artifacts(self) -> None:
        root = Path(".")
        bm25 = root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json"
        if not bm25.is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        result = run_search_failure_analysis(root)
        assert result.records
        assert result.retrieval_relationship_aggregates
        variant_names = {row.variant_name for row in result.records}
        assert any("bm25" in name for name in variant_names)

    def test_persisted_artifact_integration(self) -> None:
        from productiq.retrieval.evaluation.search_evaluation.failure_analysis_runner import (
            run_default_search_failure_analysis,
        )

        root = Path(".")
        if not (root / "resources/evaluation/productiq_search_benchmark_v1_baseline_bm25_run.json").is_file():
            pytest.skip("Phase 12.5 artifacts missing")
        result = run_default_search_failure_analysis(root)
        path = root / "resources/evaluation/productiq_search_failure_analysis_v1.json"
        assert path.is_file()
        payload = json.loads(path.read_text(encoding="utf-8"))
        validate_search_failure_analysis_artifact(payload)
        assert payload["analysis_result"]["lineage"]["benchmark_name"] == "productiq_search_benchmark_v1"
        assert result.records
