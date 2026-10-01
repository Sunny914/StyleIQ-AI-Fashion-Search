"""Assemble the production RecommendationPipeline for serving benchmarks (Phase 13.8.4)."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from typing import cast

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.database.models.product import Product
from productiq.exceptions.base import CatalogValidationError, RecommendationError
from productiq.recommendation.baseline_ranker import BaselineRecommendationRanker
from productiq.recommendation.catalog_embeddings import PostgresProductEmbeddingProvider
from productiq.recommendation.config import DEFAULT_CANDIDATE_POOL_TOP_K
from productiq.recommendation.content_similarity_engine import ContentSimilarityEngine
from productiq.recommendation.generators.attribute import AttributeRecommendationCandidateGenerator
from productiq.recommendation.generators.bm25 import BM25RecommendationCandidateGenerator
from productiq.recommendation.generators.protocol import RecommendationCandidateGenerator
from productiq.recommendation.generators.vector import VectorRecommendationCandidateGenerator
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.recommendation.recommendation_product_context_provider import (
    PostgresRecommendationProductContextProvider,
)
from productiq.recommendation.seed_embedding import PostgresSeedEmbeddingProvider
from productiq.recommendation.seed_product import PostgresRecommendationCatalog
from productiq.representation.filtering import FilteringRepresentation
from productiq.retrieval.bm25_retriever import BM25Retriever
from productiq.retrieval.catalog_candidate_filter import filtering_representation_from_product
from productiq.retrieval.contracts import Retriever
from productiq.retrieval.lexical import InvertedLexicalIndex
from productiq.retrieval.semantic_retriever import SemanticRetriever


class _LazyPostgresFilteringMap:
    """On-demand filtering rows for candidate constraint checks (no full-catalog preload)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._cache: dict[str, FilteringRepresentation] = {}

    def __getitem__(self, product_id: str) -> FilteringRepresentation:
        if product_id not in self._cache:
            stmt = select(Product).where(Product.product_id == product_id)
            row = self._session.scalar(stmt)
            if row is None:
                msg = f"filtering metadata missing for product_id {product_id!r}"
                raise CatalogValidationError(msg)
            filtering_row = filtering_representation_from_product(row)
            self._cache[product_id] = filtering_row
        cached = self._cache[product_id]
        return cached

    def __delitem__(self, product_id: str) -> None:
        del self._cache[product_id]

    def __setitem__(self, product_id: str, value: FilteringRepresentation) -> None:
        self._cache[product_id] = value

    def get(
        self,
        key: str,
        default: FilteringRepresentation | None = None,
    ) -> FilteringRepresentation | None:
        try:
            return self[key]
        except CatalogValidationError:
            return default

    def __contains__(self, product_id: object) -> bool:
        if not isinstance(product_id, str):
            return False
        try:
            self[product_id]
        except CatalogValidationError:
            return False
        return True

    def __iter__(self) -> Iterator[str]:
        return iter(self._cache)

    def __len__(self) -> int:
        return len(self._cache)


def _lexical_index_from_retriever(lexical_retriever: Retriever) -> InvertedLexicalIndex:
    if isinstance(lexical_retriever, BM25Retriever):
        return lexical_retriever.index
    msg = "lexical retriever must be BM25Retriever with an InvertedLexicalIndex"
    raise RecommendationError(msg)


def build_production_recommendation_generators(
    *,
    catalog: PostgresRecommendationCatalog,
    lexical_retriever: Retriever,
    semantic_retriever: SemanticRetriever,
    engine: Engine,
) -> tuple[RecommendationCandidateGenerator, ...]:
    lexical_index = _lexical_index_from_retriever(lexical_retriever)
    seed_embeddings = PostgresSeedEmbeddingProvider(engine)
    generators: list[RecommendationCandidateGenerator] = [
        VectorRecommendationCandidateGenerator(
            vector_index=semantic_retriever.vector_index,
            seed_embeddings=seed_embeddings,
        ),
        AttributeRecommendationCandidateGenerator(catalog=catalog),
        BM25RecommendationCandidateGenerator(lexical_index),
    ]
    return tuple(generators)


def build_production_recommendation_pipeline(
    *,
    engine: Engine,
    session: Session,
    lexical_retriever: Retriever,
    semantic_retriever: SemanticRetriever,
) -> RecommendationPipeline:
    """Single production RecommendationPipeline using existing PostgreSQL and retrieval artifacts."""
    catalog = PostgresRecommendationCatalog(session)
    generators = build_production_recommendation_generators(
        catalog=catalog,
        lexical_retriever=lexical_retriever,
        semantic_retriever=semantic_retriever,
        engine=engine,
    )
    embedding_provider = PostgresProductEmbeddingProvider(engine)
    similarity_engine = ContentSimilarityEngine(embedding_provider=embedding_provider)
    context_provider = PostgresRecommendationProductContextProvider(session)
    lazy_filtering = _LazyPostgresFilteringMap(session)
    return RecommendationPipeline(
        catalog=catalog,
        generators=generators,
        similarity_engine=similarity_engine,
        ranker=BaselineRecommendationRanker(),
        product_context_provider=context_provider,
        filtering_by_product_id=cast(Mapping[str, FilteringRepresentation], lazy_filtering),
    )


__all__ = [
    "DEFAULT_CANDIDATE_POOL_TOP_K",
    "build_production_recommendation_generators",
    "build_production_recommendation_pipeline",
]
