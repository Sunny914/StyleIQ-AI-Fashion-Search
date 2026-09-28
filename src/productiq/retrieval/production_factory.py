"""Construct production retrieval dependencies at application startup (Phase 4.19)."""

from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from productiq.retrieval.catalog_candidate_filter import PostgresCatalogCandidateFilter
from productiq.retrieval.contracts import Retriever
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_pipeline import (
    ProductionRetrievalPipeline,
    create_production_retrieval_pipeline,
)
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.rrf_hybrid_retriever import create_rrf_hybrid_retriever


def create_production_retrieval_pipeline_from_retrievers(
    *,
    lexical_retriever: Retriever,
    semantic_retriever: Retriever,
    catalog_filter_session: Session,
    production_config: ProductionRetrievalConfig | None = None,
    rrf_config: RRFConfig | None = None,
) -> ProductionRetrievalPipeline:
    """Wire RRF hybrid retrieval and PostgreSQL candidate filtering (no per-request heavy init)."""
    rrf_retriever = create_rrf_hybrid_retriever(
        lexical_retriever,
        semantic_retriever,
        config=rrf_config,
    )
    catalog_filter = PostgresCatalogCandidateFilter(catalog_filter_session)
    return create_production_retrieval_pipeline(
        rrf_retriever=rrf_retriever,
        catalog_filter=catalog_filter,
        config=production_config,
    )


def create_production_retrieval_session_factory(session_factory: sessionmaker[Session]) -> Session:
    """Open one SQLAlchemy session for catalog candidate filtering (caller owns lifecycle)."""
    return session_factory()


__all__ = [
    "create_production_retrieval_pipeline_from_retrievers",
    "create_production_retrieval_session_factory",
]
