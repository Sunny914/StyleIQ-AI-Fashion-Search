"""Phase 12.5 search baseline evaluation artifact constants."""

from __future__ import annotations

SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION = "12.5.0"

SEARCH_BASELINE_BM25_VARIANT_NAME = "productiq_search_baseline_bm25"
SEARCH_BASELINE_SEMANTIC_VARIANT_NAME = "productiq_search_baseline_semantic"
SEARCH_BASELINE_RRF_VARIANT_NAME = "productiq_search_baseline_rrf"

SEARCH_BASELINE_BM25_RUN_FILENAME = "productiq_search_benchmark_v1_baseline_bm25_run.json"
SEARCH_BASELINE_SEMANTIC_RUN_FILENAME = "productiq_search_benchmark_v1_baseline_semantic_run.json"
SEARCH_BASELINE_RRF_RUN_FILENAME = "productiq_search_benchmark_v1_baseline_rrf_run.json"

SUPPORTED_SEARCH_BASELINE_VARIANTS: tuple[str, ...] = ("bm25", "semantic", "rrf")

__all__ = [
    "SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION",
    "SEARCH_BASELINE_BM25_RUN_FILENAME",
    "SEARCH_BASELINE_BM25_VARIANT_NAME",
    "SEARCH_BASELINE_RRF_RUN_FILENAME",
    "SEARCH_BASELINE_RRF_VARIANT_NAME",
    "SEARCH_BASELINE_SEMANTIC_RUN_FILENAME",
    "SEARCH_BASELINE_SEMANTIC_VARIANT_NAME",
    "SUPPORTED_SEARCH_BASELINE_VARIANTS",
]
