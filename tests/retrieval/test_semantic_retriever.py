"""Unit tests for Phase 4.13 semantic candidate retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from productiq.exceptions.base import SemanticRetrievalError
from productiq.representation.query_contract import (
    QueryLexicalIntent,
    QueryRepresentation,
    QuerySemanticIntent,
    build_query_representation,
)
from productiq.retrieval.contracts import (
    RetrievalMethod,
    RetrievalRequest,
    Retriever,
)
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.semantic import SemanticSearchHit, SemanticVector
from productiq.retrieval.semantic_retriever import (
    SemanticRetriever,
    create_semantic_retriever,
    semantic_retriever_satisfies_protocol,
)


def _unit_vector(first: float = 1.0) -> SemanticVector:
    values = [0.0] * PRODUCTIQ_EMBEDDING_DIMENSION
    values[0] = first
    return SemanticVector(values=tuple(values))


@dataclass
class FakeQueryEncoder:
    embedding_dimension: int = PRODUCTIQ_EMBEDDING_DIMENSION
    model_id: str = "fake/bge"
    model_revision: str = "test"
    library_version: str = "0"
    device: str = "cpu"
    calls: list[str] = field(default_factory=list)

    def encode_documents(self, texts: list[str]):
        raise NotImplementedError

    def encode_query(self, query_text: str) -> SemanticVector:
        self.calls.append(query_text)
        return _unit_vector()


@dataclass
class FakeVectorIndex:
    calls: list[tuple[SemanticVector, int]] = field(default_factory=list)
    hits: tuple[SemanticSearchHit, ...] = (
        SemanticSearchHit(product_id="P2", similarity=0.88),
        SemanticSearchHit(product_id="P1", similarity=0.91),
    )
    error: Exception | None = None

    def search(self, query_vector: SemanticVector, *, top_k: int) -> tuple[SemanticSearchHit, ...]:
        self.calls.append((query_vector, top_k))
        if self.error is not None:
            raise self.error
        return self.hits[:top_k]


def _request(query_text: str = "black running shoes", *, top_k: int = 10) -> RetrievalRequest:
    return RetrievalRequest(
        query=build_query_representation(query_text),
        top_k=top_k,
    )


def test_semantic_retriever_satisfies_retriever_protocol() -> None:
    retriever = create_semantic_retriever(FakeQueryEncoder(), FakeVectorIndex())
    assert isinstance(retriever, Retriever)
    assert semantic_retriever_satisfies_protocol(retriever)


def test_semantic_intent_reaches_encoder_via_encode_query() -> None:
    encoder = FakeQueryEncoder()
    index = FakeVectorIndex()
    retriever = SemanticRetriever(encoder=encoder, vector_index=index)
    retriever.retrieve(_request("nike trail shoes"))
    assert encoder.calls == ["nike trail shoes"]


def test_encoder_vector_and_top_k_reach_vector_index() -> None:
    encoder = FakeQueryEncoder()
    index = FakeVectorIndex()
    retriever = SemanticRetriever(encoder=encoder, vector_index=index)
    retriever.retrieve(_request("shoes", top_k=3))
    assert len(index.calls) == 1
    query_vector, top_k = index.calls[0]
    assert top_k == 3
    assert query_vector.dimension == PRODUCTIQ_EMBEDDING_DIMENSION


def test_hits_map_to_vector_candidates_with_similarity_scores() -> None:
    retriever = create_semantic_retriever(
        FakeQueryEncoder(),
        FakeVectorIndex(hits=(SemanticSearchHit(product_id="A", similarity=0.75),)),
    )
    response = retriever.retrieve(_request(top_k=5))
    assert len(response.candidates) == 1
    candidate = response.candidates[0]
    assert candidate.product_id == "A"
    assert candidate.score == pytest.approx(0.75)
    assert candidate.method is RetrievalMethod.VECTOR


def test_result_order_preserved_from_vector_index() -> None:
    hits = (
        SemanticSearchHit(product_id="P1", similarity=0.95),
        SemanticSearchHit(product_id="P2", similarity=0.90),
        SemanticSearchHit(product_id="P3", similarity=0.85),
    )
    retriever = create_semantic_retriever(FakeQueryEncoder(), FakeVectorIndex(hits=hits))
    response = retriever.retrieve(_request(top_k=3))
    assert [candidate.product_id for candidate in response.candidates] == ["P1", "P2", "P3"]
    assert [candidate.score for candidate in response.candidates] == pytest.approx([0.95, 0.90, 0.85])


def test_requested_top_k_metadata_and_candidate_cap() -> None:
    hits = tuple(
        SemanticSearchHit(product_id=f"P{i}", similarity=1.0 - i * 0.01)
        for i in range(5)
    )
    retriever = create_semantic_retriever(FakeQueryEncoder(), FakeVectorIndex(hits=hits))
    response = retriever.retrieve(_request(top_k=2))
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 2
    assert len(response.candidates) == 2


def test_whitespace_only_semantic_intent_returns_empty_response() -> None:
    encoder = FakeQueryEncoder()
    index = FakeVectorIndex()
    retriever = SemanticRetriever(encoder=encoder, vector_index=index)
    request = RetrievalRequest(
        query=QueryRepresentation(
            query_text="placeholder",
            lexical_intent=QueryLexicalIntent(text="nike"),
            semantic_intent=QuerySemanticIntent(text="   "),
        ),
        top_k=5,
    )
    response = retriever.retrieve(request)
    assert response.candidates == ()
    assert response.metadata is not None
    assert response.metadata.requested_top_k == 5
    assert encoder.calls == []
    assert index.calls == []


def test_vector_index_errors_are_not_swallowed() -> None:
    retriever = create_semantic_retriever(
        FakeQueryEncoder(),
        FakeVectorIndex(error=RuntimeError("pgvector unavailable")),
    )
    with pytest.raises(RuntimeError, match="pgvector unavailable"):
        retriever.retrieve(_request())


def test_encoder_dimension_mismatch_fails() -> None:
    @dataclass
    class WrongDimEncoder(FakeQueryEncoder):
        embedding_dimension: int = PRODUCTIQ_EMBEDDING_DIMENSION

        def encode_query(self, query_text: str) -> SemanticVector:
            return SemanticVector(values=(1.0, 0.0))

    retriever = create_semantic_retriever(WrongDimEncoder(), FakeVectorIndex())
    with pytest.raises(SemanticRetrievalError, match="query embedding dimension"):
        retriever.retrieve(_request())


def test_encoder_reused_across_retrieve_calls() -> None:
    encoder = FakeQueryEncoder()
    index = FakeVectorIndex()
    retriever = SemanticRetriever(encoder=encoder, vector_index=index)
    retriever.retrieve(_request("first query"))
    retriever.retrieve(_request("second query"))
    assert encoder.calls == ["first query", "second query"]


def test_uses_semantic_not_lexical_intent() -> None:
    encoder = FakeQueryEncoder()
    index = FakeVectorIndex()
    retriever = SemanticRetriever(encoder=encoder, vector_index=index)
    request = RetrievalRequest(
        query=build_query_representation(
            "visible query",
            lexical_text="lexical only",
            semantic_text="semantic target",
        ),
        top_k=4,
    )
    retriever.retrieve(request)
    assert encoder.calls == ["semantic target"]
