"""Production retrieval orchestration (Phase 4.19, ranking integration Phase 10.5)."""

from __future__ import annotations

import time
from dataclasses import dataclass

from productiq.exceptions.base import RankingError
from productiq.ranking.feature_schema import RANKING_FEATURE_SCHEMA_VERSION
from productiq.ranking.hardening.production_safety import assert_retrieve_ranked_uses_baseline_path
from productiq.ranking.normalization_schema import NORMALIZATION_SCHEMA_VERSION
from productiq.ranking.product_context_provider import RankingProductContextProvider
from productiq.retrieval.catalog_candidate_filter import CatalogCandidateFilter
from productiq.retrieval.catalog_constraint_match import constraints_are_active
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
)
from productiq.retrieval.exceptions import RetrievalError
from productiq.retrieval.production_config import (
    ProductionRetrievalConfig,
    validate_pool_against_request,
)
from productiq.retrieval.production_ranking_config import (
    RANKING_PIPELINE_INTEGRATION_VERSION,
    ProductionRankingStageConfig,
)
from productiq.retrieval.query_for_retrieval import query_has_usable_retrieval_intent
from productiq.retrieval.ranked_search import (
    RankedSearchEvaluationBundle,
    RankedSearchResponse,
    RankedSearchTimingsMs,
)
from productiq.retrieval.ranking_integration import (
    retrieval_order_ranking_response,
    run_baseline_ranking_stage,
)

PRODUCTION_PIPELINE_VERSION = "4.19.0"


@dataclass(frozen=True)
class _FilteredPoolResult:
    filtered_candidates: tuple[RetrievalCandidate, ...]
    fused_metadata: RetrievalResponseMetadata | None
    fused_candidate_count: int | None


@dataclass(frozen=True)
class ProductionRetrievalPipeline:
    """Orchestrate RRF candidate pool retrieval, hard filtering, and optional baseline ranking."""

    rrf_retriever: Retriever
    catalog_filter: CatalogCandidateFilter
    config: ProductionRetrievalConfig
    product_context_provider: RankingProductContextProvider | None = None
    ranking_stage: ProductionRankingStageConfig | None = None

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        validate_pool_against_request(
            candidate_pool_top_k=self.config.candidate_pool_top_k,
            requested_top_k=request.top_k,
        )
        pool = self._retrieve_filtered_pool(request)
        if pool is None:
            return self._empty_response(request, fused_metadata=None)
        final_candidates = pool.filtered_candidates[: request.top_k]
        metadata = self._build_metadata(
            request=request,
            fused_metadata=pool.fused_metadata,
            fused_candidate_count=pool.fused_candidate_count,
            filtered_count=len(pool.filtered_candidates),
            returned_count=len(final_candidates),
        )
        return RetrievalResponse(candidates=final_candidates, metadata=metadata)

    def retrieve_ranked(self, request: RetrievalRequest) -> RankedSearchResponse:
        validate_pool_against_request(
            candidate_pool_top_k=self.config.candidate_pool_top_k,
            requested_top_k=request.top_k,
        )
        total_start = time.perf_counter()
        pool = self._retrieve_filtered_pool(request)
        return self._ranked_search_from_pool(
            request,
            pool,
            total_start=total_start,
        )

    def retrieve_ranked_evaluation_bundle(
        self,
        request: RetrievalRequest,
    ) -> RankedSearchEvaluationBundle:
        """Single-pass ranked search plus filtered-pool IDs for offline ranking evaluation."""
        validate_pool_against_request(
            candidate_pool_top_k=self.config.candidate_pool_top_k,
            requested_top_k=request.top_k,
        )
        total_start = time.perf_counter()
        pool = self._retrieve_filtered_pool(request)
        ranked_search = self._ranked_search_from_pool(
            request,
            pool,
            total_start=total_start,
        )
        filtered = pool.filtered_candidates if pool is not None else ()
        pool_ids = tuple(candidate.product_id for candidate in filtered)
        return RankedSearchEvaluationBundle(
            ranked_search=ranked_search,
            filtered_pool_product_ids=pool_ids,
            rrf_ordered_product_ids=pool_ids,
        )

    def _ranked_search_from_pool(
        self,
        request: RetrievalRequest,
        pool: _FilteredPoolResult | None,
        *,
        total_start: float,
    ) -> RankedSearchResponse:
        retrieval_ms = (time.perf_counter() - total_start) * 1000.0
        stage = self.ranking_stage or ProductionRankingStageConfig()
        assert_retrieve_ranked_uses_baseline_path(stage)
        ranking_applied = stage.enabled

        if pool is None:
            empty_ranking = retrieval_order_ranking_response(
                query=request.query,
                filtered_candidates=(),
                top_k=request.top_k,
            )
            metadata = self._build_metadata(
                request=request,
                fused_metadata=None,
                fused_candidate_count=None,
                filtered_count=0,
                returned_count=0,
            )
            total_ms = (time.perf_counter() - total_start) * 1000.0
            return RankedSearchResponse(
                ranking=empty_ranking,
                retrieval_metadata=metadata,
                ranking_pipeline_version=RANKING_PIPELINE_INTEGRATION_VERSION,
                ranking_applied=False,
                candidate_count_before_filter=None,
                candidate_count_after_filter=0,
                candidate_count_entering_ranking=0,
                timings_ms=RankedSearchTimingsMs(
                    retrieval_ms=retrieval_ms,
                    total_ms=total_ms,
                ),
            )

        filtered = pool.filtered_candidates
        metadata = self._build_metadata(
            request=request,
            fused_metadata=pool.fused_metadata,
            fused_candidate_count=pool.fused_candidate_count,
            filtered_count=len(filtered),
            returned_count=min(len(filtered), request.top_k),
        )

        if not filtered:
            empty_ranking = retrieval_order_ranking_response(
                query=request.query,
                filtered_candidates=(),
                top_k=request.top_k,
            )
            total_ms = (time.perf_counter() - total_start) * 1000.0
            return RankedSearchResponse(
                ranking=empty_ranking,
                retrieval_metadata=metadata,
                ranking_pipeline_version=RANKING_PIPELINE_INTEGRATION_VERSION,
                ranking_applied=False,
                candidate_count_before_filter=pool.fused_candidate_count,
                candidate_count_after_filter=0,
                candidate_count_entering_ranking=0,
                timings_ms=RankedSearchTimingsMs(
                    retrieval_ms=retrieval_ms,
                    total_ms=total_ms,
                ),
            )

        feature_ms: float | None = None
        normalization_ms: float | None = None
        ranking_ms: float | None = None
        feature_schema_version: str | None = None
        normalization_schema_version: str | None = None

        if ranking_applied:
            if self.product_context_provider is None:
                msg = "product_context_provider is required when baseline ranking is enabled"
                raise RankingError(msg)
            stage_result = run_baseline_ranking_stage(
                query=request.query,
                filtered_candidates=filtered,
                top_k=request.top_k,
                product_context_provider=self.product_context_provider,
                baseline_config=stage.baseline_config,
            )
            ranking_response = stage_result.response
            feature_ms = stage_result.timings_ms.feature_extraction_ms
            normalization_ms = stage_result.timings_ms.normalization_ms
            ranking_ms = stage_result.timings_ms.ranking_ms
            feature_schema_version = RANKING_FEATURE_SCHEMA_VERSION
            normalization_schema_version = NORMALIZATION_SCHEMA_VERSION
        else:
            ranking_start = time.perf_counter()
            ranking_response = retrieval_order_ranking_response(
                query=request.query,
                filtered_candidates=filtered,
                top_k=request.top_k,
            )
            ranking_ms = (time.perf_counter() - ranking_start) * 1000.0

        total_ms = (time.perf_counter() - total_start) * 1000.0
        return RankedSearchResponse(
            ranking=ranking_response,
            retrieval_metadata=metadata,
            ranking_pipeline_version=RANKING_PIPELINE_INTEGRATION_VERSION,
            ranking_applied=ranking_applied,
            candidate_count_before_filter=pool.fused_candidate_count,
            candidate_count_after_filter=len(filtered),
            candidate_count_entering_ranking=len(filtered),
            feature_schema_version=feature_schema_version,
            normalization_schema_version=normalization_schema_version,
            timings_ms=RankedSearchTimingsMs(
                retrieval_ms=retrieval_ms,
                feature_extraction_ms=feature_ms,
                normalization_ms=normalization_ms,
                ranking_ms=ranking_ms,
                total_ms=total_ms,
            ),
        )

    def _retrieve_filtered_pool(self, request: RetrievalRequest) -> _FilteredPoolResult | None:
        if not query_has_usable_retrieval_intent(request.query):
            return None

        pool_request = request.model_copy(
            update={"top_k": self.config.candidate_pool_top_k},
        )
        fused_response = self.rrf_retriever.retrieve(pool_request)
        fused_metadata = fused_response.metadata

        if fused_response.candidate_count == 0:
            return _FilteredPoolResult((), fused_metadata, 0)

        candidate_ids = tuple(candidate.product_id for candidate in fused_response.candidates)
        if constraints_are_active(request.query.constraints):
            filtered_ids = self.catalog_filter.filter_candidate_ids(
                query=request.query,
                candidate_product_ids=candidate_ids,
            )
        else:
            filtered_ids = candidate_ids

        by_id = {candidate.product_id: candidate for candidate in fused_response.candidates}
        filtered_candidates = tuple(
            by_id[product_id] for product_id in filtered_ids if product_id in by_id
        )
        fused_count = (
            fused_metadata.fused_candidate_count
            if fused_metadata is not None and fused_metadata.fused_candidate_count is not None
            else fused_response.candidate_count
        )
        return _FilteredPoolResult(filtered_candidates, fused_metadata, fused_count)

    def _empty_response(
        self,
        request: RetrievalRequest,
        *,
        fused_metadata: RetrievalResponseMetadata | None,
    ) -> RetrievalResponse:
        metadata = self._build_metadata(
            request=request,
            fused_metadata=fused_metadata,
            fused_candidate_count=None,
            filtered_count=0,
            returned_count=0,
        )
        return RetrievalResponse(candidates=(), metadata=metadata)

    def _build_metadata(
        self,
        *,
        request: RetrievalRequest,
        fused_metadata: RetrievalResponseMetadata | None,
        fused_candidate_count: int | None,
        filtered_count: int,
        returned_count: int,
    ) -> RetrievalResponseMetadata:
        if fused_metadata is None:
            return RetrievalResponseMetadata(
                requested_top_k=request.top_k,
                candidate_pool_top_k=self.config.candidate_pool_top_k,
                filtered_candidate_count=filtered_count,
                returned_candidate_count=returned_count,
                production_pipeline_version=PRODUCTION_PIPELINE_VERSION,
            )
        fused_count = (
            fused_metadata.fused_candidate_count
            if fused_metadata.fused_candidate_count is not None
            else fused_candidate_count
        )
        return fused_metadata.model_copy(
            update={
                "requested_top_k": request.top_k,
                "candidate_pool_top_k": self.config.candidate_pool_top_k,
                "fused_candidate_count": fused_count,
                "filtered_candidate_count": filtered_count,
                "returned_candidate_count": returned_count,
                "production_pipeline_version": PRODUCTION_PIPELINE_VERSION,
            }
        )


def create_production_retrieval_pipeline(
    *,
    rrf_retriever: Retriever,
    catalog_filter: CatalogCandidateFilter,
    config: ProductionRetrievalConfig | None = None,
    product_context_provider: RankingProductContextProvider | None = None,
    ranking_stage: ProductionRankingStageConfig | None = None,
) -> ProductionRetrievalPipeline:
    if not isinstance(rrf_retriever, Retriever):
        msg = "rrf_retriever must satisfy Retriever protocol"
        raise RetrievalError(msg)
    return ProductionRetrievalPipeline(
        rrf_retriever=rrf_retriever,
        catalog_filter=catalog_filter,
        config=config or ProductionRetrievalConfig(),
        product_context_provider=product_context_provider,
        ranking_stage=ranking_stage,
    )


__all__ = [
    "PRODUCTION_PIPELINE_VERSION",
    "ProductionRetrievalPipeline",
    "create_production_retrieval_pipeline",
]