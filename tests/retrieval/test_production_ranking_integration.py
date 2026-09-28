"""Integration tests for Phase 10.5 ranking pipeline."""

from __future__ import annotations

from dataclasses import dataclass

import pytest

from productiq.exceptions import RankingError
from productiq.ranking.adapters import ranking_request_from_retrieval_response
from productiq.ranking.baseline_config import BaselineFeatureWeights, BaselineRankingConfig
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.product_context_provider import InMemoryRankingProductContextProvider
from productiq.representation.builder import build_product_representation
from productiq.representation.query_contract import (
    QueryFilterConstraints,
    QueryLexicalIntent,
    QueryRepresentation,
    QuerySemanticIntent,
    build_query_representation,
)
from productiq.retrieval.contracts import RetrievalRequest, RetrievalResponse
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.production_ranking_config import (
    RETRIEVAL_ORDER_RANKING_VERSION,
    ProductionRankingStageConfig,
)
from productiq.retrieval.ranked_search import RankedSearchResponse
from productiq.retrieval.ranking_integration import run_baseline_ranking_stage
from productiq.retrieval.rrf_fusion import fused_candidate_from_rrf
from tests.database.catalog_fixtures import make_product_record
from tests.retrieval.test_production_retrieval_pipeline import (
    FakeRRFRetriever,
    RecordingCatalogFilter,
    _filtering_map,
    _fused_candidate,
    _pipeline,
)


def _context_provider(**product_overrides: dict[str, object]) -> InMemoryRankingProductContextProvider:
    filtering_map = _filtering_map(**product_overrides)
    contexts: dict[str, RankingProductContext] = {}
    for product_id, filtering in filtering_map.items():
        overrides = product_overrides.get(product_id, {})
        record = make_product_record(product_id=product_id, **overrides)
        product = build_product_representation(record)
        contexts[product_id] = RankingProductContext(
            product_id=product_id,
            product=product,
            filtering=filtering,
        )
    return InMemoryRankingProductContextProvider(contexts)


def _ranked_pipeline(
    *,
    ranking: tuple[str, ...],
    pool_top_k: int = 50,
    product_overrides: dict[str, dict[str, object]] | None = None,
    ranking_stage: ProductionRankingStageConfig | None = None,
) -> tuple[ProductionRetrievalPipeline, FakeRRFRetriever, RecordingCatalogFilter]:
    overrides = product_overrides or {product_id: {} for product_id in ranking}
    filtering_map = _filtering_map(**overrides)
    pipeline, rrf, catalog = _pipeline(
        ranking=ranking,
        pool_top_k=pool_top_k,
        filtering_map=filtering_map,
    )
    provider = _context_provider(**overrides)
    ranked_pipeline = ProductionRetrievalPipeline(
        rrf_retriever=pipeline.rrf_retriever,
        catalog_filter=pipeline.catalog_filter,
        config=pipeline.config,
        product_context_provider=provider,
        ranking_stage=ranking_stage or ProductionRankingStageConfig(),
    )
    return ranked_pipeline, rrf, catalog


def test_retrieval_response_to_ranking_request_adapter() -> None:
    candidates = (
        _fused_candidate("P1", fusion=0.9, bm25_rank=1, vector_rank=1),
        _fused_candidate("P2", fusion=0.8, bm25_rank=2, vector_rank=2),
    )
    response = RetrievalResponse(candidates=candidates, metadata=None)
    query = build_query_representation("shoes")
    request = ranking_request_from_retrieval_response(query=query, response=response, top_k=5)
    assert [row.product_id for row in request.candidates] == ["P1", "P2"]
    assert request.top_k == 5


def test_retrieve_unchanged_without_ranking_dependencies() -> None:
    pipeline, rrf, catalog = _pipeline(ranking=("P1", "P2", "P3"), pool_top_k=10)
    request = RetrievalRequest(query=build_query_representation("nike shoes"), top_k=3)
    response = pipeline.retrieve(request)
    assert [candidate.product_id for candidate in response.candidates] == ["P1", "P2", "P3"]
    assert rrf.calls[0].top_k == 10
    assert catalog.calls == []


def test_ranking_operates_on_full_filtered_pool_before_top_k() -> None:
    ranking = tuple(f"P{index}" for index in range(1, 8))
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=ranking, pool_top_k=10)
    request = RetrievalRequest(query=build_query_representation("shoes"), top_k=2)
    ranked = pipeline.retrieve_ranked(request)
    assert ranked.candidate_count_entering_ranking == 7
    assert ranked.candidate_count_after_filter == 7
    assert len(ranked.ranking.ranked_candidates) == 2


def test_hard_filtering_before_ranking() -> None:
    ranking = ("P1", "P2", "P3", "P4")
    overrides = {
        "P1": {"brand_normalized": "nike"},
        "P2": {"brand_normalized": "adidas"},
        "P3": {"brand_normalized": "nike"},
        "P4": {"brand_normalized": "nike"},
    }
    pipeline, _rrf, catalog = _ranked_pipeline(ranking=ranking, pool_top_k=10, product_overrides=overrides)
    query = build_query_representation(
        "running",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    request = RetrievalRequest(query=query, top_k=10)
    ranked = pipeline.retrieve_ranked(request)
    assert ranked.candidate_count_after_filter == 3
    assert {row.product_id for row in ranked.ranking.ranked_candidates} == {"P1", "P3", "P4"}
    assert len(catalog.calls) == 1


def test_final_top_k_after_ranking_not_rrf_slice_only() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(
        ranking=("A", "B", "C", "D", "E"),
        pool_top_k=10,
    )
    request = RetrievalRequest(query=build_query_representation("shoes"), top_k=2)
    ranked = pipeline.retrieve_ranked(request)
    assert len(ranked.ranking.ranked_candidates) == 2
    assert ranked.ranking.ranked_candidates[0].rank == 1
    assert ranked.ranking.ranked_candidates[1].rank == 2


def test_baseline_ranking_can_change_order_vs_retrieval() -> None:
    weights = BaselineFeatureWeights(
        **{name: 0.0 for name in BaselineFeatureWeights.model_fields}
        | {"vector_similarity": 1.0}
    )
    stage = ProductionRankingStageConfig(
        baseline_config=BaselineRankingConfig(weights=weights),
    )

    @dataclass
    class VectorAwareRRF:
        def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
            candidates = (
                fused_candidate_from_rrf(
                    "HIGH_FUSION",
                    fusion_score=0.95,
                    bm25_rank=1,
                    vector_rank=2,
                    bm25_score=1.0,
                    vector_score=0.1,
                ),
                fused_candidate_from_rrf(
                    "LOW_FUSION",
                    fusion_score=0.5,
                    bm25_rank=2,
                    vector_rank=1,
                    bm25_score=0.5,
                    vector_score=0.95,
                ),
            )
            return RetrievalResponse(candidates=candidates[: request.top_k], metadata=None)

    overrides = {"HIGH_FUSION": {}, "LOW_FUSION": {}}
    provider = _context_provider(**overrides)
    catalog = RecordingCatalogFilter(delegate=None, passthrough=True)
    pipeline = ProductionRetrievalPipeline(
        rrf_retriever=VectorAwareRRF(),
        catalog_filter=catalog,
        config=ProductionRetrievalConfig(candidate_pool_top_k=10),
        product_context_provider=provider,
        ranking_stage=stage,
    )
    query = build_query_representation("shoes")
    request = RetrievalRequest(query=query, top_k=2)
    retrieval = pipeline.retrieve(request)
    ranked = pipeline.retrieve_ranked(request)
    assert [row.product_id for row in retrieval.candidates] == ["HIGH_FUSION", "LOW_FUSION"]
    assert ranked.ranking.ranked_candidates[0].product_id == "LOW_FUSION"


def test_empty_intent_skips_ranking_work() -> None:
    pipeline, rrf, catalog = _ranked_pipeline(ranking=("P1",))
    query = QueryRepresentation.model_construct(
        query_text="constraint-only",
        constraints=QueryFilterConstraints(brand="nike"),
        lexical_intent=QueryLexicalIntent.model_construct(text=""),
        semantic_intent=QuerySemanticIntent.model_construct(text=""),
    )
    request = RetrievalRequest(query=query, top_k=5)
    ranked = pipeline.retrieve_ranked(request)
    assert ranked.ranking.ranked_candidates == ()
    assert ranked.candidate_count_entering_ranking == 0
    assert rrf.calls == []
    assert catalog.calls == []


def test_impossible_constraints_empty_ranking() -> None:
    overrides = {"P1": {"brand_normalized": "adidas"}}
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",), product_overrides=overrides)
    query = build_query_representation(
        "shoes",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    ranked = pipeline.retrieve_ranked(RetrievalRequest(query=query, top_k=5))
    assert ranked.ranking.ranked_candidates == ()
    assert ranked.candidate_count_after_filter == 0


def test_missing_product_context_raises() -> None:
    pipeline, _rrf, _catalog = _pipeline(ranking=("P1", "P2"), pool_top_k=10)
    ranked_pipeline = ProductionRetrievalPipeline(
        rrf_retriever=pipeline.rrf_retriever,
        catalog_filter=pipeline.catalog_filter,
        config=pipeline.config,
        product_context_provider=InMemoryRankingProductContextProvider({}),
        ranking_stage=ProductionRankingStageConfig(),
    )
    with pytest.raises(RankingError, match="missing RankingProductContext"):
        ranked_pipeline.retrieve_ranked(
            RetrievalRequest(query=build_query_representation("shoes"), top_k=5),
        )


def test_ranking_disabled_preserves_retrieval_order() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(
        ranking=("P1", "P2", "P3"),
        ranking_stage=ProductionRankingStageConfig(enabled=False),
    )
    request = RetrievalRequest(query=build_query_representation("shoes"), top_k=2)
    ranked = pipeline.retrieve_ranked(request)
    assert ranked.ranking_applied is False
    assert [row.product_id for row in ranked.ranking.ranked_candidates] == ["P1", "P2"]
    assert ranked.ranking.config.ranking_version == RETRIEVAL_ORDER_RANKING_VERSION


def test_deterministic_repeated_ranked_requests() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2", "P3"))
    request = RetrievalRequest(query=build_query_representation("shoes"), top_k=3)
    first = pipeline.retrieve_ranked(request)
    second = pipeline.retrieve_ranked(request)
    assert first.model_copy(update={"timings_ms": None}) == second.model_copy(update={"timings_ms": None})
    assert first.ranking == second.ranking


def test_ranked_search_to_retrieval_response_projection() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1", "P2"))
    ranked = pipeline.retrieve_ranked(RetrievalRequest(query=build_query_representation("x"), top_k=2))
    projected = ranked.to_retrieval_response()
    assert len(projected.candidates) == len(ranked.ranking.ranked_candidates)


def test_version_metadata_on_ranked_response() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",))
    ranked = pipeline.retrieve_ranked(RetrievalRequest(query=build_query_representation("x"), top_k=1))
    assert ranked.feature_schema_version == "10.2.0"
    assert ranked.normalization_schema_version == "10.3.0"
    assert ranked.ranking.config.ranking_version == "10.4.0"


def test_performance_smoke_timings_populated() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=tuple(f"P{index}" for index in range(1, 6)))
    ranked = pipeline.retrieve_ranked(RetrievalRequest(query=build_query_representation("perf"), top_k=3))
    assert ranked.timings_ms is not None
    assert ranked.timings_ms.retrieval_ms is not None
    assert ranked.timings_ms.total_ms is not None
    assert ranked.timings_ms.feature_extraction_ms is not None


def test_run_baseline_ranking_stage_integration() -> None:
    candidates = (
        _fused_candidate("P1", fusion=0.2, bm25_rank=1, vector_rank=2),
        _fused_candidate("P2", fusion=0.9, bm25_rank=2, vector_rank=1),
    )
    provider = _context_provider(P1={}, P2={})
    result = run_baseline_ranking_stage(
        query=build_query_representation("demo"),
        filtered_candidates=candidates,
        top_k=2,
        product_context_provider=provider,
        baseline_config=BaselineRankingConfig(),
    )
    assert len(result.response.ranked_candidates) == 2


def test_rrf_still_uses_pool_top_k_with_ranked_path() -> None:
    pipeline, rrf, _catalog = _ranked_pipeline(
        ranking=tuple(f"P{index}" for index in range(1, 12)),
        pool_top_k=10,
    )
    pipeline.retrieve_ranked(RetrievalRequest(query=build_query_representation("shoes"), top_k=3))
    assert rrf.calls[0].top_k == 10


def test_isinstance_ranked_search_response() -> None:
    pipeline, _rrf, _catalog = _ranked_pipeline(ranking=("P1",))
    ranked = pipeline.retrieve_ranked(RetrievalRequest(query=build_query_representation("x"), top_k=1))
    assert isinstance(ranked, RankedSearchResponse)
