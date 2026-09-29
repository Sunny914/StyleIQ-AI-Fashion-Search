"""Aggregate search failure analysis records (Phase 12.8)."""

from __future__ import annotations

from collections import Counter

from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SearchFailureAggregateRow,
    SearchFailureAnalysisRecord,
    SearchFailureCategory,
    SearchRetrievalRelationshipAggregate,
)


def aggregate_failure_records(
    records: tuple[SearchFailureAnalysisRecord, ...],
) -> tuple[SearchFailureAggregateRow, ...]:
    counter: Counter[tuple[str, int, SearchFailureCategory, int | None, str | None]] = Counter()
    for row in records:
        counter[(row.variant_name, row.analysis_k, row.failure_category, row.relevance_grade, row.query_id)] += 1
    rows: list[SearchFailureAggregateRow] = []
    for (variant_name, analysis_k, category, grade, query_id), count in sorted(counter.items()):
        rows.append(
            SearchFailureAggregateRow(
                variant_name=variant_name,
                analysis_k=analysis_k,
                failure_category=category,
                record_count=count,
                relevance_grade=grade,
                query_id=query_id,
            )
        )
    return tuple(rows)


def aggregate_by_variant_and_k(
    records: tuple[SearchFailureAnalysisRecord, ...],
) -> tuple[SearchFailureAggregateRow, ...]:
    counter: Counter[tuple[str, int, SearchFailureCategory]] = Counter()
    for row in records:
        counter[(row.variant_name, row.analysis_k, row.failure_category)] += 1
    return tuple(
        SearchFailureAggregateRow(
            variant_name=variant_name,
            analysis_k=analysis_k,
            failure_category=category,
            record_count=count,
        )
        for (variant_name, analysis_k, category), count in sorted(counter.items())
    )


def aggregate_retrieval_relationships(
    pattern_counts: dict[str, int],
) -> tuple[SearchRetrievalRelationshipAggregate, ...]:
    return tuple(
        SearchRetrievalRelationshipAggregate(pattern=pattern, product_count=count)
        for pattern, count in sorted(pattern_counts.items())
    )


__all__ = [
    "aggregate_by_variant_and_k",
    "aggregate_failure_records",
    "aggregate_retrieval_relationships",
]
