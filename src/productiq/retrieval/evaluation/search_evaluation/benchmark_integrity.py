"""Structural integrity helpers for search evaluation benchmarks (Phase 12.2)."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    search_evaluation_benchmark_to_dict,
)


@dataclass(frozen=True, slots=True)
class SearchBenchmarkCatalogProvenance:
    """Catalog lineage recorded on the benchmark (no live catalog lookup)."""

    catalog_artifact: str | None
    source_representation_checksum: str | None


@dataclass(frozen=True, slots=True)
class SearchBenchmarkIntegritySummary:
    query_count: int
    judgment_count: int
    grade_distribution: tuple[tuple[int, int], ...]
    unique_judged_product_ids: int


def catalog_provenance_from_benchmark(
    benchmark: SearchEvaluationBenchmark,
) -> SearchBenchmarkCatalogProvenance:
    return SearchBenchmarkCatalogProvenance(
        catalog_artifact=benchmark.metadata.catalog_artifact,
        source_representation_checksum=benchmark.metadata.source_representation_checksum,
    )


def summarize_search_benchmark_integrity(
    benchmark: SearchEvaluationBenchmark,
) -> SearchBenchmarkIntegritySummary:
    grade_counts: Counter[int] = Counter()
    product_ids: set[str] = set()
    judgment_count = 0
    for query in benchmark.queries:
        for judgment in query.relevance_judgments:
            grade_counts[judgment.grade] += 1
            product_ids.add(judgment.product_id)
            judgment_count += 1
    distribution = tuple(sorted(grade_counts.items()))
    return SearchBenchmarkIntegritySummary(
        query_count=len(benchmark.queries),
        judgment_count=judgment_count,
        grade_distribution=distribution,
        unique_judged_product_ids=len(product_ids),
    )


def validate_search_benchmark_integrity(benchmark: SearchEvaluationBenchmark) -> None:
    """Re-assert structural invariants beyond Pydantic (explicit failure messages)."""
    summary = summarize_search_benchmark_integrity(benchmark)
    if summary.query_count == 0:
        msg = "benchmark must contain at least one query"
        raise ValueError(msg)
    if summary.judgment_count == 0:
        msg = "benchmark must contain at least one relevance judgment"
        raise ValueError(msg)
    if not benchmark.metadata.benchmark_name.strip():
        msg = "benchmark metadata benchmark_name must not be empty"
        raise ValueError(msg)
    if not benchmark.metadata.benchmark_version.strip():
        msg = "benchmark metadata benchmark_version must not be empty"
        raise ValueError(msg)


def sort_benchmark_for_stable_serialization(
    benchmark: SearchEvaluationBenchmark,
) -> SearchEvaluationBenchmark:
    """Return a copy with queries and judgments sorted for deterministic JSON."""
    sorted_queries = tuple(
        query.model_copy(
            update={
                "relevance_judgments": tuple(
                    sorted(query.relevance_judgments, key=lambda row: row.product_id)
                )
            }
        )
        for query in sorted(benchmark.queries, key=lambda row: row.query_id)
    )
    return benchmark.model_copy(update={"queries": sorted_queries})


def stable_benchmark_artifact_dict(benchmark: SearchEvaluationBenchmark) -> dict[str, Any]:
    ordered = sort_benchmark_for_stable_serialization(benchmark)
    return search_evaluation_benchmark_to_dict(ordered)


__all__ = [
    "SearchBenchmarkCatalogProvenance",
    "SearchBenchmarkIntegritySummary",
    "catalog_provenance_from_benchmark",
    "sort_benchmark_for_stable_serialization",
    "stable_benchmark_artifact_dict",
    "summarize_search_benchmark_integrity",
    "validate_search_benchmark_integrity",
]
