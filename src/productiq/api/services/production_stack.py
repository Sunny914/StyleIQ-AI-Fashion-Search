"""Assemble production HTTP services from PostgreSQL + runtime artifacts (Phase 15C).

Called from ``create_app`` only when ``PRODUCTIQ_ENABLE_PRODUCTION_SERVING`` is set.
Does not run at module import time.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from productiq.api.services.application_services import ApplicationServices
from productiq.api.services.product_wiring import create_product_serving_service_from_catalog
from productiq.api.services.recommendation_wiring import (
    create_recommendation_serving_service_from_pipeline,
)
from productiq.api.services.search_wiring import create_search_serving_service_from_pipeline
from productiq.config.runtime_artifacts import resolve_runtime_artifact_paths
from productiq.config.settings import Settings, get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.database.load_runtime_catalog import (
    CatalogRuntimeStatus,
    inspect_catalog_runtime_status,
)
from productiq.database.models.product import Product
from productiq.database.session import create_session_factory
from productiq.exceptions.base import ConfigurationError
from productiq.logging import get_logger
from productiq.ranking.product_context import RankingProductContext
from productiq.ranking.product_context_provider import PostgresRankingProductContextProvider
from productiq.representation.query_contract import QueryRepresentation
from productiq.retrieval.bm25_retriever import (
    create_bm25_retriever,
    create_bm25_retriever_from_index_path,
)
from productiq.retrieval.catalog_candidate_filter import PostgresCatalogCandidateFilter
from productiq.retrieval.contracts import Retriever
from productiq.retrieval.embedding_encoder import (
    DocumentEmbeddingEncoder,
    create_bge_small_en_v15_encoder,
)
from productiq.retrieval.lexical import LexicalIndexDocument, build_inverted_lexical_index
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_pipeline import create_production_retrieval_pipeline
from productiq.retrieval.production_ranking_config import ProductionRankingStageConfig
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.rrf_hybrid_retriever import create_rrf_hybrid_retriever
from productiq.retrieval.semantic_retriever import (
    SemanticRetriever,
    create_semantic_retriever_from_engine,
)
from productiq.serving.config import ServingConfig
from productiq.serving.performance.recommendation_production_wiring import (
    build_production_recommendation_pipeline,
)
from productiq.serving.postgres_catalog_provider import PostgresProductCatalogReadProvider
from productiq.serving.protocols import RecommendationServingService
from productiq.serving.recommendation_schema import (
    RecommendationApiRequest,
    RecommendationApiResponse,
)


class _SessionFactoryCatalogFilter:
    """Open a short-lived session for each hard-filter call (request-safe)."""

    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def filter_candidate_ids(
        self,
        *,
        query: QueryRepresentation,
        candidate_product_ids: tuple[str, ...],
    ) -> tuple[str, ...]:
        session = self._session_factory()
        try:
            return PostgresCatalogCandidateFilter(session).filter_candidate_ids(
                query=query,
                candidate_product_ids=candidate_product_ids,
            )
        finally:
            session.close()


class _SessionFactoryRankingContextProvider:
    def __init__(self, session_factory: sessionmaker[Session]) -> None:
        self._session_factory = session_factory

    def load_contexts(self, *, product_ids: tuple[str, ...]) -> Mapping[str, RankingProductContext]:
        session = self._session_factory()
        try:
            return PostgresRankingProductContextProvider(session).load_contexts(
                product_ids=product_ids,
            )
        finally:
            session.close()


class _PerRequestRecommendationServingService:
    """Build a recommendation pipeline per request so SQLAlchemy sessions are not shared."""

    def __init__(
        self,
        *,
        engine: Engine,
        session_factory: sessionmaker[Session],
        lexical_retriever: Retriever,
        semantic_retriever: SemanticRetriever,
    ) -> None:
        self._engine = engine
        self._session_factory = session_factory
        self._lexical = lexical_retriever
        self._semantic = semantic_retriever

    def recommend(self, request: RecommendationApiRequest, *, request_id: str) -> RecommendationApiResponse:
        session = self._session_factory()
        try:
            pipeline = build_production_recommendation_pipeline(
                engine=self._engine,
                session=session,
                lexical_retriever=self._lexical,
                semantic_retriever=self._semantic,
            )
            service = create_recommendation_serving_service_from_pipeline(pipeline)
            return service.recommend(request, request_id=request_id)
        finally:
            session.close()


@dataclass(frozen=True)
class ProductionServingRuntime:
    """Handles held for shutdown (engine dispose)."""

    engine: Engine
    catalog_status: CatalogRuntimeStatus
    lexical_source: str


def _bm25_from_postgres_descriptions(
    engine: Engine,
    session_factory: sessionmaker[Session],
) -> Retriever:
    session = session_factory()
    try:
        rows = list(session.scalars(select(Product)))
        documents = [
            LexicalIndexDocument(
                product_id=row.product_id,
                lexical_text=" ".join(
                    part
                    for part in (row.brand, row.product_type, row.description, row.color_raw)
                    if part
                ),
            )
            for row in rows
        ]
    finally:
        session.close()
    return create_bm25_retriever(build_inverted_lexical_index(documents))


def _resolve_lexical_retriever(
    *,
    bm25_path: Path,
    catalog_status: CatalogRuntimeStatus,
    engine: Engine,
    session_factory: sessionmaker[Session],
) -> tuple[Retriever, str]:
    if catalog_status.mode == "fixture":
        return _bm25_from_postgres_descriptions(engine, session_factory), "fixture_from_catalog"
    if bm25_path.is_file():
        return create_bm25_retriever_from_index_path(bm25_path), "persisted_artifact"
    msg = (
        "BM25 artifact is required for production serving when the catalog is not "
        "the labeled compose-demo fixture"
    )
    raise ConfigurationError(msg)


def build_production_application_services(
    *,
    settings: Settings | None = None,
    serving_config: ServingConfig | None = None,
    encoder: DocumentEmbeddingEncoder | None = None,
    engine: Engine | None = None,
) -> tuple[ApplicationServices, ProductionServingRuntime]:
    """Wire search, product, and recommendation services from live dependencies."""
    logger = get_logger(__name__)
    resolved_settings = settings or get_settings()
    resolved_engine = engine or create_engine_from_settings(resolved_settings)
    paths = resolve_runtime_artifact_paths(resolved_settings)
    catalog_status = inspect_catalog_runtime_status(resolved_engine)
    if catalog_status.mode == "empty":
        msg = "catalog is empty; run python -m productiq.database.load_runtime_catalog --mode fixture (or --mode full)"
        raise ConfigurationError(msg)
    session_factory = create_session_factory(resolved_engine)

    lexical, lexical_source = _resolve_lexical_retriever(
        bm25_path=paths.bm25_index,
        catalog_status=catalog_status,
        engine=resolved_engine,
        session_factory=session_factory,
    )
    resolved_encoder = encoder or create_bge_small_en_v15_encoder(
        device="cpu",
        allow_cpu_fallback=True,
    )
    semantic = create_semantic_retriever_from_engine(resolved_engine, resolved_encoder)
    rrf_retriever = create_rrf_hybrid_retriever(lexical, semantic, config=RRFConfig(rank_constant=60))
    pipeline = create_production_retrieval_pipeline(
        rrf_retriever=rrf_retriever,
        catalog_filter=_SessionFactoryCatalogFilter(session_factory),
        config=ProductionRetrievalConfig(),
        product_context_provider=_SessionFactoryRankingContextProvider(session_factory),
        ranking_stage=ProductionRankingStageConfig(enabled=True),
    )
    search_service = create_search_serving_service_from_pipeline(pipeline)
    product_service = create_product_serving_service_from_catalog(
        PostgresProductCatalogReadProvider(session_factory),
    )
    recommendation_service: RecommendationServingService = _PerRequestRecommendationServingService(
        engine=resolved_engine,
        session_factory=session_factory,
        lexical_retriever=lexical,
        semantic_retriever=semantic,
    )
    logger.info(
        "Production serving wired (catalog_mode=%s, products=%s, embeddings=%s, bm25=%s)",
        catalog_status.mode,
        catalog_status.product_count,
        catalog_status.embedding_count,
        lexical_source,
    )
    services = ApplicationServices(
        serving_config=serving_config or ServingConfig(),
        search_service=search_service,
        recommendation_service=recommendation_service,
        product_service=product_service,
        catalog_mode=catalog_status.mode,
        catalog_product_count=catalog_status.product_count,
        catalog_embedding_count=catalog_status.embedding_count,
    )
    runtime = ProductionServingRuntime(
        engine=resolved_engine,
        catalog_status=catalog_status,
        lexical_source=lexical_source,
    )
    return services, runtime


__all__ = [
    "ProductionServingRuntime",
    "build_production_application_services",
]
