"""Documented concurrency assumptions for production serving stacks (Phase 13.8.6).

Read-only audit notes for benchmark reporting — not production code changes.
"""

from __future__ import annotations

SEARCH_CONCURRENCY_AUDIT_NOTES: tuple[str, ...] = (
    "ProductionRetrievalPipeline and wired retrievers are treated as immutable after startup.",
    "BM25 inverted index lookups are read-only; concurrent lexical reads are expected to be safe.",
    "pgvector/SQLAlchemy access uses per-operation connections; pool contention may appear under load.",
    "BGE query encoding may serialize internally; concurrent semantic retrieval is not assumed linearly scalable.",
    "No explicit synchronization was added for this benchmark phase.",
)

RECOMMENDATION_CONCURRENCY_AUDIT_NOTES: tuple[str, ...] = (
    "RecommendationPipeline components are wired once; generators and ranker state are not mutated per request.",
    "PostgresRecommendationCatalog.list_catalog_products() performs full-catalog reads; concurrent calls may contend.",
    (
        "Lazy filtering maps used in production benchmark wiring cache rows in a shared dict "
        "without locks; concurrent first-seen product_ids may race (documented limitation, "
        "not altered for 13.8.6)."
    ),
    "Postgres sessions for seed/context loads are not shared across threads by the pipeline.",
    "Vector/BM25 generators reuse read-only retrieval artifacts similar to search.",
)

PRODUCT_CONCURRENCY_AUDIT_NOTES: tuple[str, ...] = (
    "ProcessedParquetProductCatalogReadProvider builds an immutable in-memory index at startup.",
    "get_product is a dict lookup; concurrent reads are expected to be safe after initialization.",
    "Parquet load occurs once; not included in per-request latency samples.",
)

GENERAL_CONCURRENCY_AUDIT_NOTES: tuple[str, ...] = (
    "FastAPI TestClient drives concurrent requests from worker threads in the 13.8.2 runner.",
    "Thread safety was reviewed but not proven; failures at higher concurrency are reported, not hidden.",
    "This phase measures behavior; it does not add locks, pools, or caches to production code.",
)


def audit_notes_for_endpoint(endpoint: str) -> tuple[str, ...]:
    mapping = {
        "search": SEARCH_CONCURRENCY_AUDIT_NOTES,
        "recommendation": RECOMMENDATION_CONCURRENCY_AUDIT_NOTES,
        "product": PRODUCT_CONCURRENCY_AUDIT_NOTES,
    }
    return mapping.get(endpoint, GENERAL_CONCURRENCY_AUDIT_NOTES)


__all__ = [
    "GENERAL_CONCURRENCY_AUDIT_NOTES",
    "PRODUCT_CONCURRENCY_AUDIT_NOTES",
    "RECOMMENDATION_CONCURRENCY_AUDIT_NOTES",
    "SEARCH_CONCURRENCY_AUDIT_NOTES",
    "audit_notes_for_endpoint",
]
