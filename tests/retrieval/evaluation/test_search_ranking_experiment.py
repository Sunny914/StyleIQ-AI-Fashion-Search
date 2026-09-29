"""Tests for Phase 12.7 search ranking experimentation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from productiq.exceptions.base import RetrievalError
from productiq.ranking.baseline_config import BaselineRankingConfig
from productiq.ranking.ltr.config import LTRQuerySplitConfig, LTRTrainingConfig
from productiq.ranking.ltr.training import train_ltr_model
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.product_context_provider import InMemoryRankingProductContextProvider
from productiq.representation.builder import build_product_representation
from productiq.representation.filtering import build_filtering_representation_from_canonical
from productiq.retrieval.evaluation.search_evaluation import (
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
    SearchMetricConfiguration,
    SearchRelevanceJudgment,
    default_baseline_metric_configuration,
)
from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_RRF_RUN_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    build_ranking_experiment_artifact_dict,
    validate_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_loader import (
    candidate_pool_from_rrf_baseline_artifact,
    candidate_set_from_product_ids,
    validate_candidate_pool_matches_definition,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_runner import (
    build_default_search_ranking_experiment_definition,
    run_search_ranking_experiment,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_VARIANT_BASELINE_RANKER,
    SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
    SEARCH_RANKING_VARIANT_VERSION,
    SearchCandidatePoolConfiguration,
    SearchQueryCandidateSet,
    SearchRankingCandidatePool,
    SearchRankingExperimentDefinition,
    SearchRankingExperimentResult,
    SearchRankingVariantConfiguration,
    SearchRankingVariantType,
    SearchRetrievalProvenanceRecord,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_variant_executor import (
    LtrRankingExecutor,
    RetrievalOrderRankingExecutor,
    SearchRankingExecutionContext,
)
from tests.database.catalog_fixtures import make_product_record
from tests.ranking.test_ltr_training import _fixture_dataset


def _mini_benchmark() -> SearchEvaluationBenchmark:
    return SearchEvaluationBenchmark(
        metadata=SearchEvaluationBenchmarkMetadata(
            benchmark_name="productiq_search_benchmark_v1",
            benchmark_version="1.0.0",
            methodology="test",
            labeling_methodology="test",
            limitations="test",
            catalog_artifact="resources/processed/product_representations.parquet",
            source_representation_checksum="checksum-test",
        ),
        queries=(
            SearchEvaluationQuery(
                query_id="q_a",
                query_text="alpha shoes",
                query_category="test",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P1", grade=2),),
            ),
            SearchEvaluationQuery(
                query_id="q_b",
                query_text="beta bag",
                query_category="test",
                relevance_judgments=(SearchRelevanceJudgment(product_id="P2", grade=2),),
            ),
        ),
    )


def _context_provider(*product_ids: str) -> InMemoryRankingProductContextProvider:
    contexts: dict[str, RankingProductContext] = {}
    for product_id in product_ids:
        record = make_product_record(product_id=product_id)
        product = build_product_representation(record)
        filtering = build_filtering_representation_from_canonical(record)
        contexts[product_id] = RankingProductContext(
            product_id=product_id,
            product=product,
            filtering=filtering,
        )
    return InMemoryRankingProductContextProvider(contexts)


def _pool(benchmark: SearchEvaluationBenchmark) -> SearchRankingCandidatePool:
    provenance = SearchRetrievalProvenanceRecord(
        retrieval_variant_name="toy_rrf",
        retrieval_variant_version="1.0.0",
    )
    sets = (
        candidate_set_from_product_ids(
            query_id="q_a",
            product_ids=("P3", "P1", "P4"),
            candidate_provenance="toy",
        ),
        candidate_set_from_product_ids(
            query_id="q_b",
            product_ids=("P2", "P5"),
            candidate_provenance="toy",
        ),
    )
    return SearchRankingCandidatePool(
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        candidate_pool_configuration=SearchCandidatePoolConfiguration(
            candidate_pool_top_k=5,
            require_non_empty_candidates=True,
        ),
        retrieval_provenance=provenance,
        query_candidate_sets=sets,
    )


def _definition(
    benchmark: SearchEvaluationBenchmark,
    *,
    reference: str = SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
    include_ltr: bool = False,
) -> SearchRankingExperimentDefinition:
    metric_configuration = SearchMetricConfiguration(
        k_values=(1, 5),
        evaluation_top_k=5,
        execution_top_k=5,
        min_relevant_grade=2,
        compute_ndcg=True,
    )
    variants = [
        SearchRankingVariantConfiguration(
            variant_name=SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
            variant_version=SEARCH_RANKING_VARIANT_VERSION,
            variant_type=SearchRankingVariantType.RETRIEVAL_ORDER,
        ),
        SearchRankingVariantConfiguration(
            variant_name=SEARCH_RANKING_VARIANT_BASELINE_RANKER,
            variant_version=SEARCH_RANKING_VARIANT_VERSION,
            variant_type=SearchRankingVariantType.BASELINE_RANKER,
        ),
    ]
    if include_ltr:
        variants.append(
            SearchRankingVariantConfiguration(
                variant_name="productiq_search_ranking_ltr",
                variant_version=SEARCH_RANKING_VARIANT_VERSION,
                variant_type=SearchRankingVariantType.LTR,
            )
        )
    return SearchRankingExperimentDefinition(
        experiment_name="toy_ranking_experiment",
        experiment_version="1.0.0",
        reference_ranking_variant_name=reference,
        ranking_variants=tuple(variants),
        candidate_pool_configuration=SearchCandidatePoolConfiguration(candidate_pool_top_k=5),
        benchmark_name=benchmark.metadata.benchmark_name,
        benchmark_version=benchmark.metadata.benchmark_version,
        metric_configuration=metric_configuration,
        retrieval_provenance=SearchRetrievalProvenanceRecord(
            retrieval_variant_name="toy_rrf",
            retrieval_variant_version="1.0.0",
        ),
        catalog_artifact=benchmark.metadata.catalog_artifact,
        source_representation_checksum=benchmark.metadata.source_representation_checksum,
    )


class TestRankingExperimentContracts:
    def test_valid_experiment(self) -> None:
        definition = _definition(_mini_benchmark())
        assert definition.reference_ranking_variant_name == SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER

    def test_duplicate_variants_rejected(self) -> None:
        with pytest.raises(ValidationError, match="unique"):
            SearchRankingExperimentDefinition(
                experiment_name="x",
                experiment_version="1.0.0",
                reference_ranking_variant_name="a",
                ranking_variants=(
                    SearchRankingVariantConfiguration(
                        variant_name="a",
                        variant_version="1.0.0",
                        variant_type=SearchRankingVariantType.RETRIEVAL_ORDER,
                    ),
                    SearchRankingVariantConfiguration(
                        variant_name="a",
                        variant_version="1.0.0",
                        variant_type=SearchRankingVariantType.BASELINE_RANKER,
                    ),
                ),
                candidate_pool_configuration=SearchCandidatePoolConfiguration(
                    candidate_pool_top_k=5
                ),
                benchmark_name="b",
                benchmark_version="1.0.0",
                metric_configuration=default_baseline_metric_configuration(),
                retrieval_provenance=SearchRetrievalProvenanceRecord(
                    retrieval_variant_name="r",
                    retrieval_variant_version="1.0.0",
                ),
            )

    def test_invalid_reference_rejected(self) -> None:
        with pytest.raises(ValidationError, match="reference_ranking_variant_name"):
            _definition(_mini_benchmark(), reference="missing")

    def test_extra_fields_rejected(self) -> None:
        with pytest.raises(ValidationError):
            SearchRankingExperimentDefinition(
                experiment_name="x",
                experiment_version="1.0.0",
                reference_ranking_variant_name=SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
                ranking_variants=(
                    SearchRankingVariantConfiguration(
                        variant_name=SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER,
                        variant_version="1.0.0",
                        variant_type=SearchRankingVariantType.RETRIEVAL_ORDER,
                    ),
                    SearchRankingVariantConfiguration(
                        variant_name=SEARCH_RANKING_VARIANT_BASELINE_RANKER,
                        variant_version="1.0.0",
                        variant_type=SearchRankingVariantType.BASELINE_RANKER,
                    ),
                ),
                candidate_pool_configuration=SearchCandidatePoolConfiguration(
                    candidate_pool_top_k=5
                ),
                benchmark_name="b",
                benchmark_version="1.0.0",
                metric_configuration=default_baseline_metric_configuration(),
                retrieval_provenance=SearchRetrievalProvenanceRecord(
                    retrieval_variant_name="r",
                    retrieval_variant_version="1.0.0",
                ),
                winner="a",  # type: ignore[call-arg]
            )


class TestCandidateSets:
    def test_duplicate_product_ids_rejected(self) -> None:
        with pytest.raises(ValidationError, match="duplicate"):
            SearchQueryCandidateSet(query_id="q1", candidate_product_ids=("P1", "P1"))

    def test_deterministic_ordering_required(self) -> None:
        with pytest.raises(ValidationError, match="sorted"):
            SearchRankingCandidatePool(
                benchmark_name="b",
                benchmark_version="1.0.0",
                candidate_pool_configuration=SearchCandidatePoolConfiguration(
                    candidate_pool_top_k=5
                ),
                retrieval_provenance=SearchRetrievalProvenanceRecord(
                    retrieval_variant_name="r",
                    retrieval_variant_version="1.0.0",
                ),
                query_candidate_sets=(
                    candidate_set_from_product_ids(
                        query_id="q_b",
                        product_ids=("P2",),
                        candidate_provenance="t",
                    ),
                    candidate_set_from_product_ids(
                        query_id="q_a",
                        product_ids=("P1",),
                        candidate_provenance="t",
                    ),
                ),
            )

    def test_candidate_configuration_mismatch_rejected(self) -> None:
        benchmark = _mini_benchmark()
        pool = _pool(benchmark)
        definition = _definition(benchmark)
        bad = definition.model_copy(
            update={
                "candidate_pool_configuration": SearchCandidatePoolConfiguration(
                    candidate_pool_top_k=99
                )
            }
        )
        with pytest.raises(RetrievalError, match="candidate pool configuration"):
            validate_candidate_pool_matches_definition(
                pool,
                benchmark_name=bad.benchmark_name,
                benchmark_version=bad.benchmark_version,
                candidate_pool_configuration=bad.candidate_pool_configuration,
                retrieval_provenance=bad.retrieval_provenance,
            )


class TestRankingExecutors:
    def test_retrieval_order_preserves_pool_order(self) -> None:
        benchmark = _mini_benchmark()
        query = benchmark.queries[0]
        candidate_set = candidate_set_from_product_ids(
            query_id=query.query_id,
            product_ids=("P3", "P1", "P4"),
            candidate_provenance="t",
        )
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1", "P3", "P4"),
            baseline_config=BaselineRankingConfig(),
        )
        row = RetrievalOrderRankingExecutor().execute_query(query, candidate_set, context)
        assert row.ranked_product_ids == ("P3", "P1", "P4")

    def test_query_mismatch_fails(self) -> None:
        benchmark = _mini_benchmark()
        query = benchmark.queries[0]
        candidate_set = candidate_set_from_product_ids(
            query_id="wrong",
            product_ids=("P1",),
            candidate_provenance="t",
        )
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1"),
            baseline_config=BaselineRankingConfig(),
        )
        with pytest.raises(RetrievalError, match="query_id"):
            RetrievalOrderRankingExecutor().execute_query(query, candidate_set, context)

    def test_ltr_requires_artifact(self) -> None:
        benchmark = _mini_benchmark()
        query = benchmark.queries[0]
        candidate_set = candidate_set_from_product_ids(
            query_id=query.query_id,
            product_ids=("P1",),
            candidate_provenance="t",
        )
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1"),
            baseline_config=BaselineRankingConfig(),
            ltr_artifact=None,
        )
        with pytest.raises(RetrievalError, match="LTR"):
            LtrRankingExecutor().execute_query(query, candidate_set, context)


class TestRankingExperimentRunner:
    def test_absolute_deltas_and_no_winner_fields(self) -> None:
        benchmark = _mini_benchmark()
        pool = _pool(benchmark)
        definition = _definition(benchmark)
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1", "P2", "P3", "P4", "P5"),
            baseline_config=BaselineRankingConfig(),
        )
        result = run_search_ranking_experiment(
            definition,
            pool,
            ranking_context=context,
            benchmark=benchmark,
        )
        assert len(result.candidate_comparisons) == 1
        blob = json.dumps(result.model_dump(mode="json"))
        assert '"winner"' not in blob
        assert '"best_variant"' not in blob
        forbidden = {"winner", "best_variant", "recommended_variant"}
        assert forbidden.isdisjoint(SearchRankingExperimentResult.model_fields.keys())

    def test_deterministic_artifact_checksum(self, tmp_path: Path) -> None:
        benchmark = _mini_benchmark()
        pool = _pool(benchmark)
        definition = _definition(benchmark)
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1", "P2", "P3", "P4", "P5"),
            baseline_config=BaselineRankingConfig(),
        )
        result = run_search_ranking_experiment(
            definition,
            pool,
            ranking_context=context,
            benchmark=benchmark,
        )
        payload = build_ranking_experiment_artifact_dict(definition, result)
        validate_ranking_experiment_artifact(payload)
        again = json.dumps(payload, sort_keys=True)
        assert again == json.dumps(payload, sort_keys=True)


@pytest.fixture
def trained_ltr_artifact(tmp_path: Path):
    dataset = _fixture_dataset()
    config = LTRTrainingConfig(
        num_boost_round=10,
        early_stopping_rounds=3,
        split=LTRQuerySplitConfig(split_seed=42),
    )
    _, artifact = train_ltr_model(dataset, config, artifact_directory=tmp_path / "ltr")
    return artifact


class TestLtrIntegration:
    def test_ltr_executor_with_trained_artifact(
        self,
        trained_ltr_artifact,
    ) -> None:
        benchmark = _mini_benchmark()
        pool = _pool(benchmark)
        definition = _definition(benchmark, include_ltr=True)
        context = SearchRankingExecutionContext(
            ranking_top_k=5,
            product_context_provider=_context_provider("P1", "P2", "P3", "P4", "P5"),
            baseline_config=BaselineRankingConfig(),
            ltr_artifact=trained_ltr_artifact,
        )
        result = run_search_ranking_experiment(
            definition,
            pool,
            ranking_context=context,
            benchmark=benchmark,
        )
        assert len(result.variant_evaluation_results) == 3


class TestCanonicalIntegration:
    def test_rrf_baseline_candidate_pool(self) -> None:
        from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
            default_search_benchmark_path,
            load_search_evaluation_benchmark,
        )

        path = default_search_benchmark_path(Path("."))
        if not path.is_file():
            pytest.skip("canonical search benchmark missing")
        rrf_path = Path("resources/evaluation") / SEARCH_BASELINE_RRF_RUN_FILENAME
        if not rrf_path.is_file():
            pytest.skip("RRF baseline artifact missing")
        benchmark = load_search_evaluation_benchmark(path)
        pool = candidate_pool_from_rrf_baseline_artifact(
            benchmark,
            rrf_path,
            candidate_pool_top_k=50,
        )
        assert len(pool.query_candidate_sets) == len(benchmark.queries)

    def test_default_definition(self) -> None:
        from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
            default_search_benchmark_path,
            load_search_evaluation_benchmark,
        )

        path = default_search_benchmark_path(Path("."))
        if not path.is_file():
            pytest.skip("canonical search benchmark missing")
        benchmark = load_search_evaluation_benchmark(path)
        definition = build_default_search_ranking_experiment_definition(
            benchmark, include_ltr=False
        )
        assert definition.reference_ranking_variant_name == SEARCH_RANKING_VARIANT_RETRIEVAL_ORDER
