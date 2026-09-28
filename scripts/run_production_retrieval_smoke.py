"""Smoke-test production retrieval against live infrastructure (Phase 4.20)."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.database.session import create_session_factory
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import create_bm25_retriever_from_index_path, retrieval_response_to_dict
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.production_config import ProductionRetrievalConfig
from productiq.retrieval.production_factory import (
    create_production_retrieval_pipeline_from_retrievers,
)
from productiq.retrieval.rrf_config import RRFConfig
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine

BM25_INDEX_PATH = _ROOT / "resources" / "processed" / "bm25_lexical_index.pkl"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Production retrieval integration smoke (Phase 4.20).")
    parser.add_argument("query", nargs="?", default="Nike running shoes")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument("--pool-top-k", type=int, default=50)
    args = parser.parse_args(argv)

    if os.getenv("PRODUCTIQ_RUN_INTEGRATION_TESTS") != "1":
        print("Set PRODUCTIQ_RUN_INTEGRATION_TESTS=1", file=sys.stderr)
        return 2

    if not BM25_INDEX_PATH.is_file():
        print(f"BM25 artifact missing: {BM25_INDEX_PATH}", file=sys.stderr)
        return 2

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    session_factory = create_session_factory(engine)
    filter_session = session_factory()
    try:
        lexical = create_bm25_retriever_from_index_path(BM25_INDEX_PATH)
        encoder = create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)
        semantic = create_semantic_retriever_from_engine(engine, encoder)
        pipeline = create_production_retrieval_pipeline_from_retrievers(
            lexical_retriever=lexical,
            semantic_retriever=semantic,
            catalog_filter_session=filter_session,
            production_config=ProductionRetrievalConfig(candidate_pool_top_k=args.pool_top_k),
            rrf_config=RRFConfig(rank_constant=60),
        )
        request = RetrievalRequest(
            query=build_query_representation(args.query),
            top_k=args.top_k,
        )
        response = pipeline.retrieve(request)
        print(json.dumps(retrieval_response_to_dict(response), indent=2))
    finally:
        filter_session.close()
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
