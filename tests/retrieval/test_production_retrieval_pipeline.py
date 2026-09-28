"""Unit tests for Phase 4.19 production retrieval pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from productiq.exceptions.base import CatalogValidationError, LexicalRetrievalError
from productiq.representation.filtering import build_filtering_representation_from_canonical
from productiq.representation.query_contract import (
    QueryFilterConstraints,
    QueryLexicalIntent,
    QueryRepresentation,
    QuerySemanticIntent,
    build_query_representation,
)
from productiq.retrieval.catalog_candidate_filter import InMemoryCatalogCandidateFilter
from productiq.retrieval.contracts import (
    RetrievalCandidate,
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
)
from productiq.retrieval.exceptions import RetrievalError
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_pipeline import (
    PRODUCTION_PIPELINE_VERSION,
    ProductionRetrievalPipeline,
    create_production_retrieval_pipeline,
)
from productiq.retrieval.rrf_fusion import fused_candidate_from_rrf
from tests.database.catalog_fixtures import make_product_record

EXECUTION_METADATA_FIELDS = set(RetrievalResponseMetadata.model_fields)


def _fused_candidate(
    product_id: str,
    *,
    fusion: float,
    bm25_rank: int | None = None,
    vector_rank: int | None = None,
) -> RetrievalCandidate:
    return fused_candidate_from_rrf(
        product_id,
        fusion_score=fusion,
        bm25_rank=bm25_rank,
        vector_rank=vector_rank,
        bm25_score=1.0 if bm25_rank else None,
        vector_score=0.5 if vector_rank else None,
    )


def _rrf_response(
    candidates: tuple[RetrievalCandidate, ...],
    *,
    pool_top_k: int,
) -> RetrievalResponse:
    return RetrievalResponse(
        candidates=candidates,
        metadata=RetrievalResponseMetadata(
            requested_top_k=pool_top_k,
            lexical_candidate_count=len(candidates),
            semantic_candidate_count=len(candidates),
            unique_candidate_count=len(candidates),
            overlap_count=0,
            hybrid_pool_count=len(candidates),
            fused_candidate_count=len(candidates),
            rrf_rank_constant=60,
        ),
    )


@dataclass
class FakeRRFRetriever:
    ranking: tuple[str, ...]
    calls: list[RetrievalRequest] = field(default_factory=list)
    fail_with: Exception | None = None

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        self.calls.append(request)
        if self.fail_with is not None:
            raise self.fail_with
        fusion_scores = [0.9 - index * 0.01 for index in range(len(self.ranking))]
        candidates = tuple(
            _fused_candidate(
                product_id,
                fusion=score,
                bm25_rank=index + 1,
                vector_rank=index + 1,
            )
            for index, (product_id, score) in enumerate(zip(self.ranking, fusion_scores, strict=True))
        )
        top = candidates[: request.top_k]
        return _rrf_response(top, pool_top_k=request.top_k)


@dataclass
class RecordingCatalogFilter:
    delegate: InMemoryCatalogCandidateFilter | None
    calls: list[tuple[QueryRepresentation, tuple[str, ...]]] = field(default_factory=list)
    fail_with: Exception | None = None
    passthrough: bool = False

    def filter_candidate_ids(
        self,
        *,
        query: QueryRepresentation,
        candidate_product_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        self.calls.append((query, candidate_product_ids))
        if self.fail_with is not None:
            raise self.fail_with
        if self.passthrough:
            return candidate_product_ids
        assert self.delegate is not None
        return self.delegate.filter_candidate_ids(
            query=query,
            candidate_product_ids=candidate_product_ids,
        )


def _filtering_map(**product_overrides: dict[str, object]) -> dict[str, object]:
    mapping: dict[str, object] = {}
    for product_id, overrides in product_overrides.items():
        record = make_product_record(product_id=product_id, **overrides)
        mapping[product_id] = build_filtering_representation_from_canonical(record)
    return mapping


def _pipeline(
    *,
    ranking: tuple[str, ...],
    pool_top_k: int = 50,
    filtering_map: dict | None = None,
    rrf: FakeRRFRetriever | None = None,
) -> tuple[ProductionRetrievalPipeline, FakeRRFRetriever, RecordingCatalogFilter]:
    retriever = rrf or FakeRRFRetriever(ranking=ranking)
    if filtering_map is None:
        filtering_map = _filtering_map(**{product_id: {} for product_id in ranking})
    catalog = RecordingCatalogFilter(delegate=InMemoryCatalogCandidateFilter(filtering_map))
    pipeline = ProductionRetrievalPipeline(
        rrf_retriever=retriever,
        catalog_filter=catalog,
        config=ProductionRetrievalConfig(candidate_pool_top_k=pool_top_k),
    )
    return pipeline, retriever, catalog


def test_successful_retrieval_without_constraints() -> None:
    pipeline, rrf, catalog = _pipeline(ranking=("P1", "P2", "P3"), pool_top_k=10)
    request = RetrievalRequest(query=build_query_representation("nike shoes"), top_k=3)
    response = pipeline.retrieve(request)
    assert [candidate.product_id for candidate in response.candidates] == ["P1", "P2", "P3"]
    assert response.metadata is not None
    assert response.metadata.returned_candidate_count == 3
    assert rrf.calls[0].top_k == 10
    assert catalog.calls == []


def test_candidate_over_retrieval_uses_pool_top_k() -> None:
    pipeline, rrf, _catalog = _pipeline(
        ranking=tuple(f"P{index}" for index in range(1, 12)),
        pool_top_k=10,
    )
    request = RetrievalRequest(query=build_query_representation("shoes"), top_k=3)
    pipeline.retrieve(request)
    assert rrf.calls[0].top_k == 10


def test_hard_constraint_filtering_and_ordering_edge_case() -> None:
    ranking = ("P1", "P2", "P3", "P4", "P5", "P6")
    filtering_map = _filtering_map(
        P1={"brand_normalized": "adidas"},
        P2={"brand_normalized": "nike"},
        P3={"brand_normalized": "adidas"},
        P4={"brand_normalized": "nike"},
        P5={"brand_normalized": "puma"},
        P6={"brand_normalized": "nike"},
    )
    pipeline, _rrf, _catalog = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "running",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    request = RetrievalRequest(query=query, top_k=3)
    response = pipeline.retrieve(request)
    assert [candidate.product_id for candidate in response.candidates] == ["P2", "P4", "P6"]


def test_filtering_preserves_rrf_order_not_filter_sort() -> None:
    ranking = ("A", "B", "C", "D")
    filtering_map = _filtering_map(
        A={"brand_normalized": "nike"},
        B={"brand_normalized": "adidas"},
        C={"brand_normalized": "nike"},
        D={"brand_normalized": "nike"},
    )
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=10))
    assert [candidate.product_id for candidate in response.candidates] == ["A", "C", "D"]


def test_result_count_less_than_requested_when_pool_exhausted() -> None:
    pipeline, _, _ = _pipeline(ranking=("P1", "P2"), pool_top_k=10)
    response = pipeline.retrieve(
        RetrievalRequest(query=build_query_representation("x"), top_k=5),
    )
    assert response.candidate_count == 2
    assert response.metadata is not None
    assert response.metadata.returned_candidate_count == 2


def test_zero_result_retrieval() -> None:
    rrf = FakeRRFRetriever(ranking=())
    catalog = RecordingCatalogFilter(delegate=None, passthrough=True)
    pipeline = ProductionRetrievalPipeline(
        rrf_retriever=rrf,
        catalog_filter=catalog,
        config=ProductionRetrievalConfig(candidate_pool_top_k=10),
    )
    response = pipeline.retrieve(
        RetrievalRequest(query=build_query_representation("x"), top_k=5),
    )
    assert response.candidate_count == 0
    assert response.metadata is not None
    assert response.metadata.returned_candidate_count == 0


def test_zero_result_after_filtering() -> None:
    ranking = ("P1", "P2")
    filtering_map = _filtering_map(P1={"brand_normalized": "adidas"}, P2={"brand_normalized": "adidas"})
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=5))
    assert response.candidate_count == 0
    assert response.metadata is not None
    assert response.metadata.filtered_candidate_count == 0


def test_empty_lexical_and_semantic_intent_returns_empty_without_rrf_call() -> None:
    rrf = FakeRRFRetriever(ranking=("P1",))
    catalog = RecordingCatalogFilter(delegate=None, passthrough=True)
    pipeline = ProductionRetrievalPipeline(
        rrf_retriever=rrf,
        catalog_filter=catalog,
        config=ProductionRetrievalConfig(candidate_pool_top_k=10),
    )
    query = QueryRepresentation.model_construct(
        query_text="constraint-only",
        constraints=QueryFilterConstraints(brand="nike"),
        lexical_intent=QueryLexicalIntent.model_construct(text=""),
        semantic_intent=QuerySemanticIntent.model_construct(text=""),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=5))
    assert response.candidate_count == 0
    assert rrf.calls == []
    assert catalog.calls == []


def test_rrf_failure_propagates() -> None:
    rrf = FakeRRFRetriever(ranking=("P1",), fail_with=RetrievalError("rrf failed"))
    pipeline, _, _ = _pipeline(ranking=("P1",), pool_top_k=10, rrf=rrf)
    with pytest.raises(RetrievalError, match="rrf failed"):
        pipeline.retrieve(RetrievalRequest(query=build_query_representation("x"), top_k=3))


def test_semantic_failure_propagates_through_rrf() -> None:
    from productiq.exceptions.base import SemanticRetrievalError

    rrf = FakeRRFRetriever(
        ranking=("P1",),
        fail_with=SemanticRetrievalError("vector failed"),
    )
    pipeline, _, _ = _pipeline(ranking=("P1",), pool_top_k=10, rrf=rrf)
    with pytest.raises(SemanticRetrievalError, match="vector failed"):
        pipeline.retrieve(RetrievalRequest(query=build_query_representation("x"), top_k=3))


def test_lexical_failure_propagates_through_rrf() -> None:
    rrf = FakeRRFRetriever(
        ranking=("P1",),
        fail_with=LexicalRetrievalError("bm25 failed"),
    )
    pipeline, _, _ = _pipeline(ranking=("P1",), pool_top_k=10, rrf=rrf)
    with pytest.raises(LexicalRetrievalError, match="bm25 failed"):
        pipeline.retrieve(RetrievalRequest(query=build_query_representation("x"), top_k=3))


def test_catalog_filter_failure_propagates() -> None:
    pipeline, _, catalog = _pipeline(ranking=("P1",), pool_top_k=10)
    catalog.fail_with = CatalogValidationError("db filter failed")
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    with pytest.raises(CatalogValidationError, match="db filter failed"):
        pipeline.retrieve(RetrievalRequest(query=query, top_k=3))


def test_dependencies_are_injected_via_factory_helper() -> None:
    rrf = FakeRRFRetriever(ranking=("P1",))
    catalog = RecordingCatalogFilter(delegate=None, passthrough=True)
    pipeline = create_production_retrieval_pipeline(
        rrf_retriever=rrf,
        catalog_filter=catalog,
        config=ProductionRetrievalConfig(candidate_pool_top_k=5),
    )
    assert isinstance(pipeline, ProductionRetrievalPipeline)


def test_retrieve_does_not_construct_heavy_infrastructure(monkeypatch: pytest.MonkeyPatch) -> None:
    def _forbidden(*_args: object, **_kwargs: object) -> object:
        msg = "heavy init must not run inside retrieve()"
        raise AssertionError(msg)

    monkeypatch.setattr(
        "productiq.retrieval.production_pipeline.create_production_retrieval_pipeline",
        _forbidden,
    )
    pipeline, rrf, catalog = _pipeline(ranking=("P1",), pool_top_k=5)
    response = pipeline.retrieve(
        RetrievalRequest(query=build_query_representation("x"), top_k=1),
    )
    assert response.candidate_count == 1
    assert len(rrf.calls) == 1
    assert catalog.calls == []


def test_metadata_counts_and_pipeline_version() -> None:
    ranking = ("P1", "P2", "P3", "P4")
    filtering_map = _filtering_map(
        P1={"brand_normalized": "nike"},
        P2={"brand_normalized": "adidas"},
        P3={"brand_normalized": "nike"},
        P4={"brand_normalized": "nike"},
    )
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=2))
    metadata = response.metadata
    assert metadata is not None
    assert metadata.requested_top_k == 2
    assert metadata.candidate_pool_top_k == 10
    assert metadata.fused_candidate_count == 4
    assert metadata.filtered_candidate_count == 3
    assert metadata.returned_candidate_count == 2
    assert metadata.production_pipeline_version == PRODUCTION_PIPELINE_VERSION
    assert metadata.rrf_rank_constant == 60


def test_deterministic_repeated_output() -> None:
    pipeline, _, _ = _pipeline(ranking=("P1", "P2", "P3"), pool_top_k=10)
    request = RetrievalRequest(query=build_query_representation("stable"), top_k=2)
    first = pipeline.retrieve(request)
    second = pipeline.retrieve(request)
    assert first.model_dump() == second.model_dump()


def test_provenance_and_native_scores_preserved_after_filter() -> None:
    ranking = ("P1", "P2")
    filtering_map = _filtering_map(
        P1={"brand_normalized": "nike"},
        P2={"brand_normalized": "nike"},
    )
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    fused = pipeline.rrf_retriever.retrieve(RetrievalRequest(query=query, top_k=10))
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=2))
    for candidate in response.candidates:
        source = next(row for row in fused.candidates if row.product_id == candidate.product_id)
        assert candidate.bm25_score == source.bm25_score
        assert candidate.vector_score == source.vector_score
        assert candidate.fusion_score == source.fusion_score
        assert candidate.bm25_rank == source.bm25_rank
        assert candidate.vector_rank == source.vector_rank


def test_fusion_score_unchanged_by_filtering() -> None:
    ranking = ("P1", "P2", "P3")
    filtering_map = _filtering_map(
        P1={"brand_normalized": "nike"},
        P2={"brand_normalized": "adidas"},
        P3={"brand_normalized": "nike"},
    )
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=5))
    assert [candidate.fusion_score for candidate in response.candidates] == [
        pytest.approx(0.9),
        pytest.approx(0.88),
    ]


def test_execution_metadata_has_no_catalog_attribute_keys() -> None:
    pipeline, _, _ = _pipeline(ranking=("P1",), pool_top_k=5)
    response = pipeline.retrieve(
        RetrievalRequest(query=build_query_representation("x"), top_k=1),
    )
    assert response.metadata is not None
    dumped = response.metadata.model_dump()
    assert set(dumped) <= EXECUTION_METADATA_FIELDS
    for value in dumped.values():
        if isinstance(value, dict):
            pytest.fail("unexpected nested catalog payload in metadata")


def test_pool_smaller_than_requested_top_k_raises() -> None:
    pipeline, _, _ = _pipeline(ranking=("P1",), pool_top_k=5)
    with pytest.raises(ValueError, match="candidate_pool_top_k"):
        pipeline.retrieve(
            RetrievalRequest(query=build_query_representation("x"), top_k=10),
        )


def test_create_pipeline_rejects_non_retriever() -> None:
    class NotRetriever:
        pass

    with pytest.raises(RetrievalError, match="Retriever protocol"):
        create_production_retrieval_pipeline(
            rrf_retriever=NotRetriever(),  # type: ignore[arg-type]
            catalog_filter=RecordingCatalogFilter(delegate=None, passthrough=True),
        )


def test_filtered_candidates_removed() -> None:
    ranking = ("keep", "drop")
    filtering_map = _filtering_map(
        keep={"brand_normalized": "nike"},
        drop={"brand_normalized": "adidas"},
    )
    pipeline, _, _ = _pipeline(ranking=ranking, pool_top_k=10, filtering_map=filtering_map)
    query = build_query_representation(
        "x",
        constraints=QueryFilterConstraints(brand_normalized="nike"),
    )
    response = pipeline.retrieve(RetrievalRequest(query=query, top_k=5))
    assert [candidate.product_id for candidate in response.candidates] == ["keep"]
