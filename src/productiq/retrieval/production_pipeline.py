"""Production retrieval orchestration (Phase 4.19)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.retrieval.catalog_candidate_filter import CatalogCandidateFilter
from productiq.retrieval.catalog_constraint_match import constraints_are_active
from productiq.retrieval.contracts import (
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
from productiq.retrieval.query_for_retrieval import query_has_usable_retrieval_intent

PRODUCTION_PIPELINE_VERSION = "4.19.0"


@dataclass(frozen=True)
class ProductionRetrievalPipeline:
    """Orchestrate RRF candidate pool retrieval, hard filtering, and final top_k."""

    rrf_retriever: Retriever
    catalog_filter: CatalogCandidateFilter
    config: ProductionRetrievalConfig

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        validate_pool_against_request(
            candidate_pool_top_k=self.config.candidate_pool_top_k,
            requested_top_k=request.top_k,
        )
        if not query_has_usable_retrieval_intent(request.query):
            return self._empty_response(request, fused_metadata=None)

        pool_request = request.model_copy(
            update={"top_k": self.config.candidate_pool_top_k},
        )
        fused_response = self.rrf_retriever.retrieve(pool_request)
        fused_metadata = fused_response.metadata

        if fused_response.candidate_count == 0:
            return self._empty_response(request, fused_metadata=fused_metadata)

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
        final_candidates = filtered_candidates[: request.top_k]

        metadata = self._build_metadata(
            request=request,
            fused_metadata=fused_metadata,
            fused_candidate_count=fused_response.candidate_count,
            filtered_count=len(filtered_candidates),
            returned_count=len(final_candidates),
        )
        return RetrievalResponse(candidates=final_candidates, metadata=metadata)

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
) -> ProductionRetrievalPipeline:
    if not isinstance(rrf_retriever, Retriever):
        msg = "rrf_retriever must satisfy Retriever protocol"
        raise RetrievalError(msg)
    return ProductionRetrievalPipeline(
        rrf_retriever=rrf_retriever,
        catalog_filter=catalog_filter,
        config=config or ProductionRetrievalConfig(),
    )


__all__ = [
    "PRODUCTION_PIPELINE_VERSION",
    "ProductionRetrievalPipeline",
    "create_production_retrieval_pipeline",
]
