"""Opt-in production recommendation serving performance benchmark (Phase 13.8.4)."""

from __future__ import annotations

import os
from collections.abc import Iterator

import pytest
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from productiq.database.session import create_session_factory
from productiq.database.vector_catalog import count_products_with_embeddings
from productiq.recommendation.config import DEFAULT_CANDIDATE_POOL_TOP_K
from productiq.recommendation.recommendation_pipeline import RecommendationPipeline
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from productiq.serving.performance.recommendation_benchmark import (
    RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV,
    run_recommendation_serving_performance_suite,
    write_recommendation_serving_benchmark_artifacts,
)
from productiq.serving.performance.recommendation_benchmark_config import (
    RecommendationServingBenchmarkSettings,
)
from productiq.serving.performance.recommendation_production_wiring import (
    build_production_recommendation_pipeline,
)
from productiq.serving.performance.recommendation_workloads import (
    validate_recommendation_serving_performance_seed_embeddings,
    validate_recommendation_serving_performance_seeds_in_catalog,
)
from tests.database.test_integration import INTEGRATION_ENV_VAR, INTEGRATION_SKIP_REASON
from tests.retrieval.integration.conftest import (
    MIN_LIVE_EMBEDDING_ROWS,
    PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR,
    PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON,
    production_retrieval_pytestmark,
)
from tests.retrieval.integration.live_dependencies import (
    BM25_INDEX_PATH,
    load_lexical_retriever_for_integration,
)

pytest_plugins = ["tests.retrieval.integration.conftest"]

RECOMMENDATION_SERVING_PERF_SKIP_REASON = (
    f"Set {RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV}=1 with PostgreSQL production "
    f"retrieval enabled ({INTEGRATION_ENV_VAR}=1 and {PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR}=1)."
)

pytestmark = [
    *production_retrieval_pytestmark,
    pytest.mark.skipif(
        os.getenv(RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV) != "1",
        reason=RECOMMENDATION_SERVING_PERF_SKIP_REASON,
    ),
]


@pytest.fixture(scope="session")
def live_production_recommendation_pipeline(
    live_retrieval_engine: Engine,
) -> Iterator[tuple[RecommendationPipeline, Session, bool]]:
    if os.getenv(INTEGRATION_ENV_VAR) != "1":
        pytest.skip(INTEGRATION_SKIP_REASON)
    if os.getenv(PRODUCTION_RETRIEVAL_SMOKE_ENV_VAR) != "1":
        pytest.skip(PRODUCTION_RETRIEVAL_SMOKE_SKIP_REASON)
    if count_products_with_embeddings(live_retrieval_engine) < MIN_LIVE_EMBEDDING_ROWS:
        pytest.skip(
            f"PostgreSQL has fewer than {MIN_LIVE_EMBEDDING_ROWS} embeddings; "
            "load the catalog vector index before recommendation performance benchmarks.",
        )
    session_factory = create_session_factory(live_retrieval_engine)
    session = session_factory()
    try:
        validate_recommendation_serving_performance_seeds_in_catalog(session)
        validate_recommendation_serving_performance_seed_embeddings(live_retrieval_engine)
        lexical = load_lexical_retriever_for_integration()
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        semantic = create_semantic_retriever_from_engine(live_retrieval_engine, encoder)
        pipeline = build_production_recommendation_pipeline(
            engine=live_retrieval_engine,
            session=session,
            lexical_retriever=lexical,
            semantic_retriever=semantic,
        )
        used_full_bm25 = BM25_INDEX_PATH.is_file()
        yield pipeline, session, used_full_bm25
    finally:
        session.close()


def test_production_recommendation_serving_performance_benchmark(
    live_production_recommendation_pipeline: tuple[RecommendationPipeline, Session, bool],
) -> None:
    pipeline, _session, used_full_bm25 = live_production_recommendation_pipeline
    settings = RecommendationServingBenchmarkSettings(warmups=3, iterations=10, concurrency=1)
    suite = run_recommendation_serving_performance_suite(
        pipeline,
        used_full_bm25_index=used_full_bm25,
        candidate_pool_top_k=DEFAULT_CANDIDATE_POOL_TOP_K,
        settings=settings,
    )
    for result in (*suite.api_results, *suite.service_results):
        assert result.errors.error_count == 0, result.workload.workload_id
        assert result.latency is not None
    write_recommendation_serving_benchmark_artifacts(suite)
