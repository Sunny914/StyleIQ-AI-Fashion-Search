"""Semantic candidate retrieval implementing the Phase 4.2 ``Retriever`` protocol (Phase 4.13)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.engine import Engine

from productiq.exceptions.base import SemanticRetrievalError
from productiq.retrieval.contracts import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResponseMetadata,
    Retriever,
)
from productiq.retrieval.embedding_encoder import DocumentEmbeddingEncoder
from productiq.retrieval.embedding_schema import PRODUCTIQ_EMBEDDING_DIMENSION
from productiq.retrieval.pgvector_vector_index import create_pgvector_product_vector_index
from productiq.retrieval.query_for_retrieval import build_retrieval_query_view
from productiq.retrieval.semantic import (
    VectorIndex,
    semantic_hits_to_retrieval_response,
    validate_semantic_retrieval_top_k,
)


def _semantic_retrieval_text_from_request(request: RetrievalRequest) -> str:
    view = build_retrieval_query_view(request.query)
    return view.semantic_retrieval_text.strip()


def _validate_encoder_query_vector(encoder: DocumentEmbeddingEncoder, query_vector_dimension: int) -> None:
    if query_vector_dimension != PRODUCTIQ_EMBEDDING_DIMENSION:
        msg = (
            f"query embedding dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}, "
            f"encoder returned {query_vector_dimension}"
        )
        raise SemanticRetrievalError(msg)
    if encoder.embedding_dimension != PRODUCTIQ_EMBEDDING_DIMENSION:
        msg = (
            f"encoder embedding dimension must be {PRODUCTIQ_EMBEDDING_DIMENSION}, "
            f"found {encoder.embedding_dimension}"
        )
        raise SemanticRetrievalError(msg)


@dataclass(frozen=True)
class SemanticRetriever:
    """Vector retrieval: ``semantic_intent`` → BGE query vector → pgvector HNSW → ``RetrievalResponse``."""

    encoder: DocumentEmbeddingEncoder
    vector_index: VectorIndex

    def retrieve(self, request: RetrievalRequest) -> RetrievalResponse:
        top_k = validate_semantic_retrieval_top_k(request.top_k)
        response_metadata = RetrievalResponseMetadata(requested_top_k=top_k)
        semantic_text = _semantic_retrieval_text_from_request(request)
        if not semantic_text:
            return RetrievalResponse(candidates=(), metadata=response_metadata)

        query_vector = self.encoder.encode_query(semantic_text)
        _validate_encoder_query_vector(self.encoder, query_vector.dimension)

        hits = self.vector_index.search(query_vector, top_k=top_k)
        return semantic_hits_to_retrieval_response(hits, requested_top_k=top_k)


def create_semantic_retriever(
    encoder: DocumentEmbeddingEncoder,
    vector_index: VectorIndex,
) -> SemanticRetriever:
    """Construct a semantic retriever from an injected encoder and vector index."""
    return SemanticRetriever(encoder=encoder, vector_index=vector_index)


def create_semantic_retriever_from_engine(
    engine: Engine,
    encoder: DocumentEmbeddingEncoder,
) -> SemanticRetriever:
    """Construct a semantic retriever using the Phase 4.12 PostgreSQL vector index."""
    return create_semantic_retriever(
        encoder,
        create_pgvector_product_vector_index(engine),
    )


def semantic_retriever_satisfies_protocol(retriever: SemanticRetriever) -> bool:
    """Return whether ``retriever`` implements the ``Retriever`` protocol."""
    return isinstance(retriever, Retriever)


__all__ = [
    "SemanticRetriever",
    "create_semantic_retriever",
    "create_semantic_retriever_from_engine",
    "semantic_retriever_satisfies_protocol",
]
