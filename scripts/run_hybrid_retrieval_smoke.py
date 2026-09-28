"""Smoke-test hybrid candidate retrieval (Phase 4.15)."""

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
from productiq.retrieval import create_bm25_retriever_from_index_path, retrieval_response_to_dict
from productiq.retrieval.contracts import RetrievalRequest
from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder
from productiq.retrieval.hybrid_retriever import create_hybrid_retriever
from productiq.retrieval.semantic_retriever import create_semantic_retriever_from_engine


def _serialize_candidate(candidate: dict) -> dict:
    methods = candidate.get("retrieval_methods") or [candidate.get("method")]
    return {
        "product_id": candidate["product_id"],
        "retrieval_methods": methods,
        "bm25_score": candidate.get("bm25_score"),
        "vector_score": candidate.get("vector_score"),
        "score_field_note": (
            "score=0.0 when both native scores present; not a fused hybrid score"
            if candidate.get("bm25_score") is not None and candidate.get("vector_score") is not None
            else "score mirrors sole native score"
        ),
        "score": candidate["score"],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run hybrid retrieval smoke test (Phase 4.15).")
    parser.add_argument("query", help="Natural-language query text")
    parser.add_argument("--top-k", type=int, default=20, help="Retrieval depth passed to both retrievers")
    parser.add_argument("--device", default="cpu", help="Torch device for BGE encoder")
    args = parser.parse_args(argv)

    root = _ROOT
    index_path = root / "resources" / "processed" / "bm25_lexical_index.pkl"
    settings = get_settings()
    engine = create_engine_from_settings(settings)
    try:
        lexical = create_bm25_retriever_from_index_path(index_path)
        encoder = create_bge_small_en_v15_encoder(device=args.device, allow_cpu_fallback=True)
        semantic = create_semantic_retriever_from_engine(engine, encoder)
        hybrid = create_hybrid_retriever(lexical, semantic)
        request = RetrievalRequest(
            query=build_query_representation(args.query),
            top_k=args.top_k,
        )
        response = hybrid.retrieve(request)
        payload = retrieval_response_to_dict(response)
        output = {
            "metadata": payload.get("metadata"),
            "candidates": [
                _serialize_candidate(dict(row))
                for row in payload.get("candidates", [])
            ],
        }
        print(json.dumps(output, indent=2))
    finally:
        engine.dispose()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
