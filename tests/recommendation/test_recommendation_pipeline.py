"""Tests for Phase 11.8 recommendation pipeline orchestration."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import pytest

from productiq.exceptions import CatalogValidationError, RecommendationError, SemanticRetrievalError
from productiq.recommendation.baseline_ranker import BaselineRecommendationRanker
from productiq.recommendation.catalog_embeddings import InMemoryProductEmbeddingProvider
from productiq.recommendation.config import (
    DEFAULT_CANDIDATE_POOL_TOP_K,
    RecommendationCandidateGenerationConfig,
    RecommendationConfig,
)
from productiq.recommendation.content_similarity_engine import ContentSimilarityEngine
from productiq.recommendation.contracts import (
    RecommendationCandidate,
    RecommendationCandidateSource,
    RecommendationRequest,
    RecommendationType,
)
from productiq.recommendation.generators.attribute import AttributeRecommendationCandidateGenerator
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.provenance import single_source_candidate
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.recommendation.recommendation_product_context_provider import (
    InMemoryRecommendationProductContextProvider,
)
from productiq.recommendation.seed_product import InMemoryRecommendationCatalog
from productiq.recommendation.selection_config import RecommendationSelectionConfig
from productiq.representation.filtering import FilteringRepresentation
from productiq.representation.query_contract import QueryFilterConstraints
from productiq.representation.schema import ProductRepresentation
from productiq.retrieval.semantic import SemanticVector

RECOMMENDATION_PIPELINE_SMOKE_ENV = "PRODUCTIQ_RECOMMENDATION_PIPELINE_SMOKE"


def _product(
    product_id: str,
    *,
    brand: str = "nike",
    product_type: str = "t_shirt",
    category_gender: str = "Women",
) -> ProductRepresentation:
    return ProductRepresentation(
        product_id=product_id,
        brand=brand,
        brand_normalized=brand,
        category_gender=category_gender,
        product_type=product_type,
        color=["black"],
    )


def _filtering(
    product_id: str,
    *,
    brand: str = "nike",
    product_type: str = "t_shirt",
    category_gender: str = "Women",
) -> FilteringRepresentation:
    return FilteringRepresentation(
        product_id=product_id,
        source="ajio",
        brand=brand,
        brand_normalized=brand,
        category_gender=category_gender,
        product_type=product_type,
        color_raw="black",
        color_is_coded=True,
        color=["black"],
        pattern=None,
        material=None,
        fit=None,
        sleeve=None,
        neckline=None,
        product_features=None,
        style_attributes=None,
        discount_price_inr=1000,
        original_price_inr=1200,
        price_anomaly=False,
    )


def _unit_vector(axis: int, dim: int = 3) -> SemanticVector:
    values = [0.0] * dim
    values[axis] = 1.0
    return SemanticVector(values=tuple(values))


def _request(
    seed: str = "P1",
    *,
    top_k: int = 3,
    pool_top_k: int = DEFAULT_CANDIDATE_POOL_TOP_K,
    recommendation_type: RecommendationType = RecommendationType.SIMILAR,
    filters: QueryFilterConstraints | None = None,
) -> RecommendationRequest:
    config = RecommendationConfig(
        candidate_generation=RecommendationCandidateGenerationConfig(candidate_pool_top_k=pool_top_k)
    )
    return RecommendationRequest(
        seed_product_id=seed,
        recommendation_type=recommendation_type,
        top_k=top_k,
        filters=filters,
        config=config,
    )


def _build_catalog(*product_ids: str) -> tuple[InMemoryRecommendationCatalog, dict[str, FilteringRepresentation]]:
    products = [_product(product_id) for product_id in product_ids]
    filtering = {product_id: _filtering(product_id) for product_id in product_ids}
    return InMemoryRecommendationCatalog(products), filtering


def _build_pipeline(
    catalog: InMemoryRecommendationCatalog,
    filtering_by_product_id: dict[str, FilteringRepresentation],
    *,
    generators: tuple[RecommendationCandidateGenerator, ...] | None = None,
    selection_config: RecommendationSelectionConfig | None = None,
) -> RecommendationPipeline:
    product_ids = [product.product_id for product in catalog.list_catalog_products()]
    embeddings = {
        product_id: _unit_vector(index % 3)
        for index, product_id in enumerate(sorted(product_ids))
    }
    embedding_provider = InMemoryProductEmbeddingProvider(embeddings)
    similarity_engine = ContentSimilarityEngine(embedding_provider=embedding_provider)
    context_provider = InMemoryRecommendationProductContextProvider(
        products_by_id={product.product_id: product for product in catalog.list_catalog_products()},
        filtering_by_product_id=filtering_by_product_id,
    )
    resolved_generators = generators or (
        AttributeRecommendationCandidateGenerator(catalog=catalog),
    )
    return RecommendationPipeline(
        catalog=catalog,
        generators=resolved_generators,
        similarity_engine=similarity_engine,
        ranker=BaselineRecommendationRanker(),
        product_context_provider=context_provider,
        filtering_by_product_id=filtering_by_product_id,
        selection_config=selection_config,
    )


class TestRecommendationTypeEnforcement:
    def test_unsupported_type_raises(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2")
        pipeline = _build_pipeline(catalog, filtering)
        request = _request(recommendation_type=RecommendationType.PERSONALIZED)
        with pytest.raises(RecommendationError, match="not implemented"):
            pipeline.recommend(request)


class TestSeedResolution:
    def test_missing_seed_raises_catalog_error(self) -> None:
        catalog, filtering = _build_catalog("P2")
        pipeline = _build_pipeline(catalog, filtering)
        with pytest.raises(CatalogValidationError, match="missing"):
            pipeline.recommend(_request(seed="P1"))


class TestEmptyCandidates:
    def test_valid_empty_response(self) -> None:
        catalog, filtering = _build_catalog("P1")
        pipeline = _build_pipeline(catalog, filtering)
        response = pipeline.recommend(_request(seed="P1", top_k=5))
        assert response.recommendations == ()
        assert response.requested_top_k == 5
        assert response.seed_product_id == "P1"


class TestPoolVsFinalTopK:
    def test_ranks_deeper_pool_than_final_response(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4", "P5", "P6")
        pipeline = _build_pipeline(catalog, filtering)
        result = pipeline.recommend_with_metadata(_request(seed="P1", top_k=2, pool_top_k=5))
        assert result.execution.candidate_count <= 5
        assert result.execution.ranked_count <= 5
        assert result.execution.selected_count <= 2
        assert len(result.response.recommendations) <= 2


class TestShortfall:
    def test_selection_constraint_shortfall(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        selection = RecommendationSelectionConfig(max_per_brand=1)
        pipeline = _build_pipeline(catalog, filtering, selection_config=selection)
        response = pipeline.recommend(_request(seed="P1", top_k=4, pool_top_k=4))
        assert len(response.recommendations) < 4


class TestSeedExclusion:
    def test_seed_not_in_response(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        pipeline = _build_pipeline(catalog, filtering)
        response = pipeline.recommend(_request(seed="P1", top_k=2))
        assert all(row.product_id != "P1" for row in response.recommendations)


class TestDeterminism:
    def test_identical_responses(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        pipeline = _build_pipeline(catalog, filtering)
        request = _request(seed="P1", top_k=3, pool_top_k=4)
        first = pipeline.recommend(request)
        second = pipeline.recommend(request)
        assert first == second


class TestConfigurationPropagation:
    def test_request_config_on_response(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        config = RecommendationConfig(
            max_top_k=25,
            candidate_generation=RecommendationCandidateGenerationConfig(candidate_pool_top_k=10),
        )
        request = RecommendationRequest(
            seed_product_id="P1",
            recommendation_type=RecommendationType.SIMILAR,
            top_k=2,
            config=config,
        )
        pipeline = _build_pipeline(catalog, filtering)
        response = pipeline.recommend(request)
        assert response.config == config
        assert response.requested_top_k == 2


class TestBatchContextLoading:
    def test_single_batch_load_for_candidates(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        pipeline = _build_pipeline(catalog, filtering)
        provider = pipeline.product_context_provider
        assert isinstance(provider, InMemoryRecommendationProductContextProvider)
        pipeline.recommend(_request(seed="P1", top_k=2, pool_top_k=4))
        assert provider.load_call_count == 1


@dataclass(frozen=True)
class _FailingGenerator(RecommendationCandidateGenerator):
    error: Exception

    def generate(
        self,
        request: RecommendationRequest,
        seed_product: ProductRepresentation,
    ) -> tuple[RecommendationCandidate, ...]:
        _ = request, seed_product
        raise self.error


class _FailingSimilarityEngine(ContentSimilarityEngine):
    def compute_for_candidates(self, *args: Any, **kwargs: Any) -> tuple[Any, ...]:
        _ = args, kwargs
        raise SemanticRetrievalError("similarity failed")


class TestDependencyErrors:
    def test_candidate_generation_error_preserved(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2")
        pipeline = _build_pipeline(
            catalog,
            filtering,
            generators=(_FailingGenerator(error=RecommendationError("gen failed")),),
        )
        with pytest.raises(RecommendationError, match="gen failed"):
            pipeline.recommend(_request())

    def test_similarity_error_preserved(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")
        base = _build_pipeline(catalog, filtering)
        failing = RecommendationPipeline(
            catalog=base.catalog,
            generators=base.generators,
            similarity_engine=_FailingSimilarityEngine(embedding_provider=InMemoryProductEmbeddingProvider({})),
            ranker=base.ranker,
            product_context_provider=base.product_context_provider,
            filtering_by_product_id=filtering,
        )
        with pytest.raises(SemanticRetrievalError, match="similarity failed"):
            failing.recommend(_request())


class TestHappyPath:
    def test_full_orchestration_response_contract(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4")
        pipeline = _build_pipeline(catalog, filtering)
        response = pipeline.recommend(_request(seed="P1", top_k=2, pool_top_k=4))
        assert response.recommendation_type is RecommendationType.SIMILAR
        assert response.returned_recommendation_count <= 2
        ranks = [row.rank for row in response.recommendations]
        assert ranks == list(range(1, len(ranks) + 1))
        for row in response.recommendations:
            assert row.candidate is not None
            assert row.recommendation_score == row.recommendation_score


class TestRealEndToEndIntegration:
    """Real component chain (no mocked stages)."""

    def test_real_pipeline_chain(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3", "P4", "P5")
        pipeline = _build_pipeline(catalog, filtering)
        result = pipeline.recommend_with_metadata(_request(seed="P1", top_k=3, pool_top_k=5))
        assert result.execution.candidate_count > 0
        assert result.execution.ranked_count > 0
        assert result.execution.selected_count > 0


@pytest.mark.skipif(
    os.environ.get(RECOMMENDATION_PIPELINE_SMOKE_ENV) != "1",
    reason=f"Set {RECOMMENDATION_PIPELINE_SMOKE_ENV}=1 for optional smoke marker",
)
class TestOptionalSmokeMarker:
    def test_smoke_env_flag_documented(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2")
        pipeline = _build_pipeline(catalog, filtering)
        assert pipeline.recommend(_request()).seed_product_id == "P1"


class TestPoolValidation:
    def test_pool_shorter_than_top_k_raises(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2")
        pipeline = _build_pipeline(catalog, filtering)
        with pytest.raises(RecommendationError, match="candidate_pool_top_k"):
            pipeline.recommend(_request(top_k=10, pool_top_k=5))


class TestStubCandidateImmutability:
    def test_upstream_candidate_tuple_unchanged(self) -> None:
        catalog, filtering = _build_catalog("P1", "P2", "P3")

        @dataclass(frozen=True)
        class _StaticGenerator(RecommendationCandidateGenerator):
            rows: tuple[RecommendationCandidate, ...]

            def generate(
                self,
                request: RecommendationRequest,
                seed_product: ProductRepresentation,
            ) -> tuple[RecommendationCandidate, ...]:
                _ = request, seed_product
                return self.rows

        rows = (
            single_source_candidate(
                product_id="P2",
                source=RecommendationCandidateSource.ATTRIBUTE,
                candidate_generation_score=0.9,
            ),
            single_source_candidate(
                product_id="P3",
                source=RecommendationCandidateSource.ATTRIBUTE,
                candidate_generation_score=0.8,
            ),
        )
        snapshot = tuple(rows)
        pipeline = _build_pipeline(
            catalog,
            filtering,
            generators=(_StaticGenerator(rows=rows),),
        )
        pipeline.recommend(_request(seed="P1", top_k=2, pool_top_k=2))
        assert rows == snapshot
