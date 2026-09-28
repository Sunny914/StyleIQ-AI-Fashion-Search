"""Fixtures for Phase 4.20 production retrieval integration tests."""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.config.settings import Settings, get_settings
from productiq.database.session import create_session_factory
from productiq.database.vector_catalog import count_products_with_embeddings
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_factory import (
    create_production_retrieval_pipeline_from_retrievers,
)
from productiq.retrieval.production_pipeline import ProductionRetrievalPipeline
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON
from tests.retrieval.integration.live_dependencies import (
    BM25_INDEX_PATH,
    load_lexical_retriever_for_integration,
)

pytest_plugins = ["tests.database.conftest"]

PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR = "PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE"
PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON = (
    f"Set {PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR}=1 to run production retrieval integration smoke."
)

MIN_LIVE_EMBEDDING_ROWS = 1_000
DEFAULT_REQUEST_TOP_K = 10
DEFAULT_CANDIDATE_POOL_TOP_K = 50


def production_retrieval_integration_enabled() -> bool:
    import os

    return os.getenv(INTEGRATION_ENV_VAR) == "1" and os.getenv(PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR) == "1"


def require_production_retrieval_integration() -> None:
    import os

    if os.getenv(INTEGRATION_ENV_VAR) != "1":
        pytest.skip(INTEGRATION_SKIP_REASON)
    if os.getenv(PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR) != "1":
        pytest.skip(PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON)


production_retrieval_pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        not production_retrieval_integration_enabled(),
        reason=f"{INTEGRATION_SKIP_REASON} Also {PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON}",
    ),
]


@pytest.fixture(scope="session")
def integration_settings_session() -> Settings:
    get_settings.cache_clear()
    return get_settings()


@pytest.fixture(scope="session")
def live_retrieval_engine(integration_settings_session: Settings) -> Iterator[Engine]:
    from productiq.database.engine import create_engine_from_settings

    engine = create_engine_from_settings(integration_settings_session)
    yield engine
    engine.dispose()


@dataclass(frozen=True)
class LiveProductionRetrievalContext:
    pipeline: ProductionRetrievalPipeline
    engine: Engine
    filter_session: Session
    production_config: ProductionRetrievalConfig
    used_full_bm25_index: bool


@pytest.fixture(scope="session")
def live_production_retrieval(live_retrieval_engine: Engine) -> Iterator[LiveProductionRetrievalContext]:
    require_production_retrieval_integration()
    embedding_rows = count_products_with_embeddings(live_retrieval_engine)
    if embedding_rows < MIN_LIVE_EMBEDDING_ROWS:
        pytest.skip(
            f"PostgreSQL has fewer than {MIN_LIVE_EMBEDDING_ROWS} embeddings; "
            "load the catalog vector index before production retrieval integration."
        )
    used_full_bm25 = BM25_INDEX_PATH.is_file()
    lexical = load_lexical_retriever_for_integration()
    encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
    semantic = create_semantic_retriever_from_engine(live_retrieval_engine, encoder)
    session_factory = create_session_factory(live_retrieval_engine)
    filter_session = session_factory()
    production_config = ProductionRetrievalConfig(candidate_pool_top_k=DEFAULT_CANDIDATE_POOL_TOP_K)
    pipeline = create_production_retrieval_pipeline_from_retrievers(
        lexical_retriever=lexical,
        semantic_retriever=semantic,
        catalog_filter_session=filter_session,
        production_config=production_config,
        rrf_config=RRFConfig(rank_constant=60),
    )
    try:
        yield LiveProductionRetrievalContext(
            pipeline=pipeline,
            engine=live_retrieval_engine,
            filter_session=filter_session,
            production_config=production_config,
            used_full_bm25_index=used_full_bm25,
        )
    finally:
        filter_session.close()


__all__ = [
    "DEFAULT_CANDIDATE_POOL_TOP_K",
    "DEFAULT_REQUEST_TOP_K",
    "INTEGRATION_ENV_VAR",
    "PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR",
    "PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON",
    "LiveProductionRetrievalContext",
    "live_production_retrieval",
    "live_retrieval_engine",
    "production_retrieval_integration_enabled",
    "production_retrieval_pytestmark",
    "require_production_retrieval_integration",
]
