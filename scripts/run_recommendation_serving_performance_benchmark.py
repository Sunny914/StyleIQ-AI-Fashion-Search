"""Run opt-in production recommendation serving performance benchmarks."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "src"))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.database.session import create_session_factory
from productiq.database.vector_catalog import count_products_with_embeddings
from productiq.recommendation.config import DEFAULT_CANDIDATE_POOL_TOP_K
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
from tests.retrieval.integration.conftest import MIN_LIVE_EMBEDDING_ROWS
from tests.retrieval.integration.live_dependencies import (
    BM25_INDEX_PATH,
    load_lexical_retriever_for_integration,
)


def main() -> int:
    if os.getenv("PRODUCTIQ_RUN_INTEGRATION_TESTS") != "1":
        print("Set PRODUCTIQ_RUN_INTEGRATION_TESTS=1", file=sys.stderr)
        return 2
    if os.getenv("PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE") != "1":
        print("Set PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE=1", file=sys.stderr)
        return 2
    if os.getenv(RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV) != "1":
        print(f"Set {RECOMMENDATION_SERVING_PERFORMANCE_BENCHMARK_ENV}=1", file=sys.stderr)
        return 2

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    session = None
    try:
        if count_products_with_embeddings(engine) < MIN_LIVE_EMBEDDING_ROWS:
            print(
                f"PostgreSQL has fewer than {MIN_LIVE_EMBEDDING_ROWS} embeddings; aborting.",
                file=sys.stderr,
            )
            return 3
        session_factory = create_session_factory(engine)
        session = session_factory()
        validate_recommendation_serving_performance_seeds_in_catalog(session)
        validate_recommendation_serving_performance_seed_embeddings(engine)
        used_full_bm25 = BM25_INDEX_PATH.is_file()
        lexical = load_lexical_retriever_for_integration()
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        semantic = create_semantic_retriever_from_engine(engine, encoder)
        pipeline = build_production_recommendation_pipeline(
            engine=engine,
            session=session,
            lexical_retriever=lexical,
            semantic_retriever=semantic,
        )
        suite = run_recommendation_serving_performance_suite(
            pipeline,
            used_full_bm25_index=used_full_bm25,
            candidate_pool_top_k=DEFAULT_CANDIDATE_POOL_TOP_K,
            settings=RecommendationServingBenchmarkSettings(),
        )
        output = write_recommendation_serving_benchmark_artifacts(suite)
        print(f"Wrote benchmark artifacts to {output}")
        return 0
    finally:
        if session is not None:
            session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
