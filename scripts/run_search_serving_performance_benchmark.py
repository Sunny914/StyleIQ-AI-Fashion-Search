"""Run opt-in production search serving performance benchmarks."""

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
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_factory import create_production_retrieval_pipeline_from_retrievers
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine
from productiq.serving.performance.search_benchmark import (
    SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV,
    run_search_serving_performance_suite,
    write_search_serving_benchmark_artifacts,
)
from productiq.serving.performance.search_benchmark_config import SearchServingBenchmarkSettings

MIN_LIVE_EMBEDDING_ROWS = 1_000

# Reuse integration lexical loader (lives under tests but is importable).
from tests.retrieval.integration.live_dependencies import (  # noqa: PLC0415
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
    if os.getenv(SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV) != "1":
        print(f"Set {SEARCH_SERVING_PERFORMANCE_BENCHMARK_ENV}=1", file=sys.stderr)
        return 2

    get_settings.cache_clear()
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    filter_session = None
    try:
        if count_products_with_embeddings(engine) < MIN_LIVE_EMBEDDING_ROWS:
            print(
                f"PostgreSQL has fewer than {MIN_LIVE_EMBEDDING_ROWS} embeddings; aborting.",
                file=sys.stderr,
            )
            return 3
        used_full_bm25 = BM25_INDEX_PATH.is_file()
        lexical = load_lexical_retriever_for_integration()
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        semantic = create_semantic_retriever_from_engine(engine, encoder)
        session_factory = create_session_factory(engine)
        filter_session = session_factory()
        production_config = ProductionRetrievalConfig(candidate_pool_top_k=50)
        pipeline = create_production_retrieval_pipeline_from_retrievers(
            lexical_retriever=lexical,
            semantic_retriever=semantic,
            catalog_filter_session=filter_session,
            production_config=production_config,
            rrf_config=RRFConfig(rank_constant=60),
        )
        suite = run_search_serving_performance_suite(
            pipeline,
            used_full_bm25_index=used_full_bm25,
            candidate_pool_top_k=production_config.candidate_pool_top_k,
            settings=SearchServingBenchmarkSettings(),
        )
        output = write_search_serving_benchmark_artifacts(suite)
        print(f"Wrote benchmark artifacts to {output}")
        return 0
    finally:
        if filter_session is not None:
            filter_session.close()
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
