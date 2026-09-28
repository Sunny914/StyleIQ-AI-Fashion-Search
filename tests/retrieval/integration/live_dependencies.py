"""Load live retrieval dependencies for integration tests (Phase 4.20)."""

from __future__ import annotations

from pathlib import Path

import pytest

from productiq.retrieval.contracts import Retriever

PROJECT_ROOT = Path(__file__).resolve().parents[3]
BM25_INDEX_PATH = PROJECT_ROOT / "resources" / "processed" / "bm25_lexical_index.pkl"
REPRESENTATIONS_PARQUET_PATH = PROJECT_ROOT / "resources" / "processed" / "product_representations.parquet"
BENCHMARK_PATH = PROJECT_ROOT / "resources" / "evaluation" / "lexical_retrieval_benchmark_v1.json"


def load_lexical_retriever_for_integration() -> Retriever:
    from productiq.retrieval import create_bm25_retriever_from_index_path
    from productiq.retrieval.evaluation import (
        build_benchmark_scoped_bm25_retriever,
        load_lexical_retrieval_benchmark,
    )

    if not BENCHMARK_PATH.is_file():
        pytest.skip(f"missing lexical benchmark artifact: {BENCHMARK_PATH}")
    benchmark = load_lexical_retrieval_benchmark(BENCHMARK_PATH)
    if BM25_INDEX_PATH.is_file():
        try:
            return create_bm25_retriever_from_index_path(BM25_INDEX_PATH)
        except MemoryError:
            if not REPRESENTATIONS_PARQUET_PATH.is_file():
                pytest.skip("BM25 index too large for memory and representations parquet missing")
            lexical, _ = build_benchmark_scoped_bm25_retriever(
                REPRESENTATIONS_PARQUET_PATH,
                benchmark,
                max_docs_per_term=500,
                max_total_docs=8_000,
            )
            return lexical
    if REPRESENTATIONS_PARQUET_PATH.is_file():
        lexical, _ = build_benchmark_scoped_bm25_retriever(
            REPRESENTATIONS_PARQUET_PATH,
            benchmark,
            max_docs_per_term=500,
            max_total_docs=8_000,
        )
        return lexical
    pytest.skip(f"missing BM25 artifact: {BM25_INDEX_PATH}")


__all__ = [
    "BENCHMARK_PATH",
    "BM25_INDEX_PATH",
    "REPRESENTATIONS_PARQUET_PATH",
    "load_lexical_retriever_for_integration",
]
