"""Validate semantic benchmark ground truth against the ProductIQ catalog."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.engine import Engine

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.evaluation.semantic_dataset import SemanticRetrievalBenchmark


def collect_benchmark_product_ids(benchmark: SemanticRetrievalBenchmark) -> frozenset[str]:
    seen: set[str] = set()
    for query in benchmark.queries:
        for product_id in query.relevant_product_ids:
            if product_id in seen:
                continue
            seen.add(product_id)
    return frozenset(seen)


def validate_benchmark_product_ids_in_catalog(
    benchmark: SemanticRetrievalBenchmark,
    engine: Engine,
    *,
    batch_size: int = 5_000,
) -> int:
    """Ensure every judged relevant product ID exists in ``products``."""
    product_ids = sorted(collect_benchmark_product_ids(benchmark))
    if not product_ids:
        msg = "benchmark contains no relevant product IDs"
        raise LexicalRetrievalError(msg)
    found: set[str] = set()
    for start in range(0, len(product_ids), batch_size):
        batch = product_ids[start : start + batch_size]
        with engine.connect() as connection:
            rows = connection.execute(
                text("SELECT product_id FROM products WHERE product_id = ANY(:product_ids)"),
                {"product_ids": batch},
            )
            found.update(str(row[0]) for row in rows)
    missing = set(product_ids) - found
    if missing:
        sample = sorted(missing)[:8]
        msg = (
            f"{len(missing)} benchmark product_id values are missing from products; "
            f"examples: {sample}"
        )
        raise LexicalRetrievalError(msg)
    return len(product_ids)


__all__ = [
    "collect_benchmark_product_ids",
    "validate_benchmark_product_ids_in_catalog",
]
