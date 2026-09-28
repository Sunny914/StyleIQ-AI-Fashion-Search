"""Smoke-test semantic candidate retrieval (Phase 4.13)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_SRC = _ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from productiq.config.settings import get_settings
from productiq.database.engine import create_engine_from_settings
from productiq.representation.query_contract import build_query_representation
from productiq.retrieval import retrieval_response_to_dict
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run semantic retrieval smoke test (Phase 4.13).")
    parser.add_argument("query", help="Natural-language query text (mapped to semantic_intent)")
    parser.add_argument("--top-k", type=int, default=10, help="Number of semantic candidates")
    parser.add_argument("--device", default="cpu", help="Torch device for BGE encoder")
    args = parser.parse_args(argv)

    settings = get_settings()
    engine = create_engine_from_settings(settings)
    try:
        encoder = create_bge_small_en_v15_encoder(device=args.device, allow_cpu_fallback=True)
        retriever = create_semantic_retriever_from_engine(engine, encoder)
        request = RetrievalRequest(
            query=build_query_representation(args.query),
            top_k=args.top_k,
        )
        response = retriever.retrieve(request)
        print(json.dumps(retrieval_response_to_dict(response), indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
