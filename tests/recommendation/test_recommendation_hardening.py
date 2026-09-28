"""Tests for Phase 11.9 recommendation hardening and failure analysis."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass

import pytest

from productiq.exceptions import (
    CatalogValidationError,
    RecommendationError,
    SemanticRetrievalError,
)
from productiq.recommendation.candidate_generation import generate_recommendation_candidates
from productiq.recommendation.config import (
    RecommendationCandidateGenerationConfig,
    RecommendationConfig,
)
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
    RecommendationType,
    recommendation_response_to_dict,
)
from productiq.recommendation.generators.attribute import AttributeRecommendationCandidateGenerator
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.hardening import (
    RecommendationPipelineObservation,
    assert_production_recommendation_configuration,
    assert_production_recommendation_request,
    observe_pipeline_execution,
    validate_candidate_generation_invariants,
    validate_pipeline_guardrail_response,
)
from productiq.recommendation.provenance import single_source_candidate
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.recommendation.recommendation_pipeline_config import (
    RecommendationPipelineExecutionMetadata,
)
from productiq.recommendation.recommendation_selection import select_recommendations
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.schema import ProductRepresentation
from tests.recommendation.test_recommendation_pipeline import (
    _build_catalog,
    _build_pipeline,
    _request,
)


class TestProductionGuardrails:
    def test_unsupported_type_blocked(self) -> None:
        with pytest.raises(RecommendationError, match="production recommendation"):
            assert_production_recommendation_request(
                RecommendationRequest(
                    seed_product_id="P1",
                    recommendation_type=RecommendationType.PERSONALIZED,
                    top_k=3,
                )
            )

    def test_partial_generator_config_rejected_in_production(self) -> None:
        config = RecommendationConfig(
            candidate_generation=RecommendationCandidateGenerationConfig(
                continue_on_generator_failure=True,
            )
        )
        with pytest.raises(RecommendationError, match="continue_on_generator_failure"):
            assert_production_recommendation_configuration(config)


class TestPartialGeneratorFailure:
    @dataclass(frozen=True)
    class _FailGenerator(RecommendationCandidateGenerator):
        def generate(
            self,
            request: RecommendationRequest,
            seed_product: ProductRepresentation,
        ) -> tuple[RecommendationCandidate, ...]:
            _ = request, seed_product
            raise SemanticRetrievalError("vector index unavailable")

    def test_partial_generation_records_failures(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        config = RecommendationConfig(
            candidate_generation=RecommendationCandidateGenerationConfig(
                continue_on_generator_failure=True,
                candidate_pool_top_k=5,
            )
        )
        request = RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=2,
            config=config,
        )
        result = generate_recommendation_candidates(
            request,
            catalog=catalog,
            generators=(
                self._FailGenerator(),
                AttributeRecommendationCandidateGenerator(catalog=catalog),
            ),
            filtering_by_product_id=filtering,
        )
        assert result.generator_failures
        assert result.generator_failures[0].generator_name.endswith("_FailGenerator")
        assert result.candidates
        validate_candidate_generation_invariants(result)

    def test_production_pipeline_rejects_continue_on(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        pipeline = _build_pipeline(catalog, filtering)
        config = RecommendationConfig(
            candidate_generation=RecommendationCandidateGenerationConfig(
                continue_on_generator_failure=True,
            )
        )
        request = RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=2,
            config=config,
        )
        with pytest.raises(RecommendationError, match="continue_on_generator_failure"):
            pipeline.recommend(request)


class TestSeedLeakageAndDuplicates:
    def test_pipeline_never_returns_seed(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        pipeline = _build_pipeline(catalog, filtering)
        response = pipeline.recommend(_request(seed="P1", top_k=3))
        assert "P1" not in {row.product_id for row in response.recommendations}

    def test_selection_rejects_duplicate_ranked_rows(self) -> None:
        candidate = single_source_candidate(
            product_id="P2",
            source=RecommendationCandidateSource.VECTOR,
            candidate_generation_score=0.5,
        )
        from productiq.recommendation.contracts import RankedRecommendation

        rows = (
            RankedRecommendation(product_id="P2", rank=1, recommendation_score=0.9, candidate=candidate),
            RankedRecommendation(product_id="P2", rank=2, recommendation_score=0.8, candidate=candidate),
        )
        selected = select_recommendations(rows, top_k=5, context=RecommendationSelectionContext())
        assert len(selected) == 1


class TestEmptyAndShortfall:
    def test_zero_candidates_valid_response(self) -> None:
        catalog, filtering = _build_catalog("P1")
        pipeline = _build_pipeline(catalog, filtering)
        result = pipeline.recommend_with_metadata(_request(seed="P1", top_k=5))
        assert result.response.recommendations == ()
        assert RecommendationPipelineObservation.NO_CANDIDATES.value in result.execution.observations

    def test_shortfall_observation(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        selection = RecommendationSelectionConfig(max_per_brand=1)
        pipeline = _build_pipeline(catalog, filtering, selection_config=selection)
        result = pipeline.recommend_with_metadata(_request(seed="P1", top_k=4, pool_top_k=4))
        assert result.execution.selected_count < 4
        assert RecommendationPipelineObservation.SHORTFALL.value in result.execution.observations

    def test_all_rejected_by_selection_observation(self) -> None:
        execution = RecommendationPipelineExecutionMetadata(
            candidate_count=3,
            ranked_count=3,
            selected_count=0,
        )
        observations = observe_pipeline_execution(
            request=_request(top_k=3),
            execution=execution,
        )
        assert RecommendationPipelineObservation.ALL_OUTPUT_REJECTED_BY_SELECTION in observations


class TestDeterminismStress:
    def test_serialized_response_stable(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4", "P5")
        pipeline = _build_pipeline(catalog, filtering)
        request = _request(seed="P1", top_k=3, pool_top_k=5)
        payloads = [
            json.dumps(recommendation_response_to_dict(pipeline.recommend(request)), sort_keys=True)
            for _ in range(5)
        ]
        assert len(set(payloads)) == 1


class TestPipelineGuardrail:
    def test_end_to_end_invariant_guardrail(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        pipeline = _build_pipeline(
            catalog,
            filtering,
            selection_config=RecommendationSelectionConfig(max_per_brand=2),
        )
        request = _request(seed="P1", top_k=2, pool_top_k=4)
        response = pipeline.recommend(request)
        validate_pipeline_guardrail_response(request=request, response=response)
        assert response.recommendation_type is RecommendationType.SIMILAR
        ranks = [row.rank for row in response.recommendations]
        assert ranks == list(range(1, len(ranks) + 1))
        for row in response.recommendations:
            assert math.isfinite(row.recommendation_score)


class TestFailurePropagation:
    def test_missing_seed_preserves_catalog_error(self) -> None:
        catalog, filtering = _build_catalog("P2")
        pipeline = _build_pipeline(catalog, filtering)
        with pytest.raises(CatalogValidationError):
            pipeline.recommend(_request(seed="P1"))

    def test_observe_pipeline_execution(self) -> None:
        execution = RecommendationPipelineExecutionMetadata(
            candidate_count=0,
            ranked_count=0,
            selected_count=0,
        )
        observations = observe_pipeline_execution(
            request=_request(),
            execution=execution,
        )
        assert RecommendationPipelineObservation.NO_CANDIDATES in observations


class TestImmutability:
    def test_request_unchanged_after_pipeline(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        pipeline = _build_pipeline(catalog, filtering)
        request = _request(seed="P1", top_k=2)
        before = request.model_dump(mode="json")
        pipeline.recommend(request)
        assert request.model_dump(mode="json") == before


class TestRealIntegrationPreserved:
    def test_real_chain_still_passes(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4", "P5")
        pipeline = _build_pipeline(catalog, filtering)
        result = pipeline.recommend_with_metadata(_request(seed="P1", top_k=3, pool_top_k=5))
        assert result.execution.selected_count > 0
