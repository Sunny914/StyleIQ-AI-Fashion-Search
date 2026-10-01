"""Application-level recommendation orchestration (Phase 11.8)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import StrEnum

from productiq.observability.runtime.emitter import observe_stage
from productiq.observability.tracing import SpanKind
from productiq.recommendation.baseline_ranker import (
    BaselineRecommendationRanker,
    rank_recommendations,
)
from productiq.recommendation.baseline_ranker_config import BaselineRecommendationRankerConfig
from productiq.recommendation.candidate_generation import (
    apply_candidate_pool_top_k,
    generate_recommendation_candidates,
)
from productiq.recommendation.content_similarity_engine import ContentSimilarityEngine
from productiq.recommendation.contracts import (
    RecommendationRequest,
    RecommendationResponse,
)
from productiq.recommendation.feature_extractor import extract_features_for_candidates
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.hardening.failure_analysis import observe_pipeline_execution
from productiq.recommendation.hardening.pipeline_invariants import (
    validate_candidate_generation_invariants,
    validate_content_similarity_batch,
    validate_pipeline_guardrail_response,
    validate_ranked_recommendations_invariants,
    validate_recommendation_features_batch,
    validate_selection_output_constraints,
)
from productiq.recommendation.hardening.production_safety import (
    assert_production_recommendation_request,
)
from productiq.recommendation.invariants import (
    assert_recommendation_request_inputs_unchanged,
    validate_recommendation_request_for_pipeline,
    validate_recommendation_response_invariants,
    validate_recommendation_type_implemented,
)
from productiq.recommendation.recommendation_pipeline_config import (
    RECOMMENDATION_PIPELINE_VERSION,
    RecommendationPipelineExecutionMetadata,
    RecommendationPipelineResult,
    validate_recommendation_pool_against_request,
)
from productiq.recommendation.recommendation_product_context_provider import (
    RecommendationProductContextProvider,
)
from productiq.recommendation.recommendation_selection import select_recommendations_for_request
from productiq.recommendation.seed_product import RecommendationCatalogAccess
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.recommendation.selection_context import RecommendationSelectionContext
from productiq.representation.filtering import FilteringRepresentation


class RecommendationPipelineStage(StrEnum):
    """Identifies the failing orchestration stage for diagnostics."""

    REQUEST_VALIDATION = "request_validation"
    SEED_RESOLUTION = "seed_resolution"
    CANDIDATE_GENERATION = "candidate_generation"
    CONTEXT_LOADING = "context_loading"
    SIMILARITY = "similarity"
    FEATURE_ENGINEERING = "feature_engineering"
    RANKING = "ranking"
    SELECTION = "selection"


@dataclass(frozen=True)
class RecommendationPipeline:
    """Compose Phase 11.2–11.6 into one deterministic recommendation path."""

    catalog: RecommendationCatalogAccess
    generators: Sequence[RecommendationCandidateGenerator]
    similarity_engine: ContentSimilarityEngine
    ranker: BaselineRecommendationRanker
    product_context_provider: RecommendationProductContextProvider
    filtering_by_product_id: Mapping[str, FilteringRepresentation]
    selection_config: RecommendationSelectionConfig | None = None
    ranker_config: BaselineRecommendationRankerConfig | None = None

    def recommend(self, request: RecommendationRequest) -> RecommendationResponse:
        return self.recommend_with_metadata(request).response

    def recommend_with_metadata(
        self,
        request: RecommendationRequest,
    ) -> RecommendationPipelineResult:
        snapshot = request
        validate_recommendation_request_for_pipeline(request)
        validate_recommendation_type_implemented(request.recommendation_type)
        assert_production_recommendation_request(request)
        pool_top_k = request.config.candidate_generation.candidate_pool_top_k
        validate_recommendation_pool_against_request(
            candidate_pool_top_k=pool_top_k,
            requested_top_k=request.top_k,
        )

        with observe_stage(
            "recommendation.seed_resolution",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            seed_product = self.catalog.resolve_seed_product(request.seed_product_id)

        with observe_stage(
            "recommendation.candidate_generation",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            generation = generate_recommendation_candidates(
                request,
                catalog=self.catalog,
                generators=self.generators,
                filtering_by_product_id=self.filtering_by_product_id,
            )
        validate_candidate_generation_invariants(generation)
        candidates = apply_candidate_pool_top_k(
            generation.candidates,
            candidate_pool_top_k=pool_top_k,
        )

        if not candidates:
            response = self._empty_response(request)
            assert_recommendation_request_inputs_unchanged(snapshot, request)
            validate_recommendation_response_invariants(response)
            validate_pipeline_guardrail_response(request=request, response=response)
            execution = RecommendationPipelineExecutionMetadata(
                candidate_count=0,
                ranked_count=0,
                selected_count=0,
                generator_failures=tuple(
                    failure.generator_name for failure in generation.generator_failures
                ),
            )
            observations = observe_pipeline_execution(
                request=request,
                execution=execution,
                generation=generation,
            )
            execution = RecommendationPipelineExecutionMetadata(
                candidate_count=execution.candidate_count,
                ranked_count=execution.ranked_count,
                selected_count=execution.selected_count,
                generator_failures=execution.generator_failures,
                observations=tuple(item.value for item in observations),
            )
            return RecommendationPipelineResult(response=response, execution=execution)

        with observe_stage(
            "recommendation.context_loading",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            candidate_products, context_by_product_id = self.product_context_provider.load_candidate_context(
                product_ids=tuple(candidate.product_id for candidate in candidates),
            )
        seed_filtering = self.filtering_by_product_id.get(request.seed_product_id)

        with observe_stage(
            "recommendation.similarity",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            similarities = self.similarity_engine.compute_for_candidates(
                seed_product,
                candidates,
                candidate_products,
            )
        validate_content_similarity_batch(candidates=candidates, similarities=similarities)
        similarities_by_product_id = {row.product_id: row for row in similarities}

        with observe_stage(
            "recommendation.feature_engineering",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            features = extract_features_for_candidates(
                seed_product=seed_product,
                candidates=candidates,
                similarities_by_product_id=similarities_by_product_id,
                context_by_product_id=context_by_product_id,
                seed_filtering=seed_filtering,
            )
        validate_recommendation_features_batch(candidates=candidates, features=features)

        candidates_by_product_id = {candidate.product_id: candidate for candidate in candidates}
        with observe_stage(
            "recommendation.ranking",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            ranked = rank_recommendations(
                features,
                top_k=pool_top_k,
                config=self.ranker_config or self.ranker.config,
                candidates_by_product_id=candidates_by_product_id,
                seed_product_id=request.seed_product_id,
                recommendation_config=request.config,
            )
        validate_ranked_recommendations_invariants(
            ranked,
            seed_product_id=request.seed_product_id,
        )

        selection_context = RecommendationSelectionContext(
            seed_product_id=request.seed_product_id,
            query_constraints=request.filters,
            filtering_by_product_id={
                product_id: self.filtering_by_product_id[product_id]
                for product_id in (row.product_id for row in ranked)
                if product_id in self.filtering_by_product_id
            },
            product_by_product_id={
                product_id: candidate_products[product_id]
                for product_id in (row.product_id for row in ranked)
                if product_id in candidate_products
            },
        )
        with observe_stage(
            "recommendation.selection",
            kind=SpanKind.DOMAIN,
            operation="recommendation",
        ):
            response = select_recommendations_for_request(
                request,
                ranked,
                config=self.selection_config,
                context=selection_context,
            )
        validate_selection_output_constraints(
            response,
            ranked_input=ranked,
            selection_config=self.selection_config,
            selection_context=selection_context,
        )

        assert_recommendation_request_inputs_unchanged(snapshot, request)
        validate_recommendation_response_invariants(response)
        validate_pipeline_guardrail_response(request=request, response=response)
        execution = RecommendationPipelineExecutionMetadata(
            candidate_count=len(candidates),
            ranked_count=len(ranked),
            selected_count=response.returned_recommendation_count,
            generator_failures=tuple(failure.generator_name for failure in generation.generator_failures),
        )
        observations = observe_pipeline_execution(
            request=request,
            execution=execution,
            generation=generation,
        )
        execution = RecommendationPipelineExecutionMetadata(
            candidate_count=execution.candidate_count,
            ranked_count=execution.ranked_count,
            selected_count=execution.selected_count,
            generator_failures=execution.generator_failures,
            observations=tuple(item.value for item in observations),
        )
        return RecommendationPipelineResult(response=response, execution=execution)
    @staticmethod
    def _empty_response(request: RecommendationRequest) -> RecommendationResponse:
        return RecommendationResponse(
            seed_product_id=request.seed_product_id,
            recommendation_type=request.recommendation_type,
            recommendations=(),
            requested_top_k=request.top_k,
            config=request.config,
        )


__all__ = [
    "RECOMMENDATION_PIPELINE_VERSION",
    "RecommendationPipeline",
    "RecommendationPipelineStage",
]
