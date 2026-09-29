"""Validate statistical analysis inputs (Phase 12.9)."""

from __future__ import annotations

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SearchStatisticalMetricName,
)


def validate_metric_name(raw: str) -> SearchStatisticalMetricName:
    try:
        return SearchStatisticalMetricName(raw)
    except ValueError as exc:
        msg = f"invalid statistical metric_name: {raw!r}"
        raise RetrievalError(msg) from exc


def validate_k_for_metric(
    metric_name: SearchStatisticalMetricName,
    k: int | None,
    metric_configuration: SearchMetricConfiguration,
) -> None:
    if metric_name is SearchStatisticalMetricName.MRR:
        if k is not None:
            msg = "MRR statistical comparisons must not specify k"
            raise RetrievalError(msg)
        return
    if k is None:
        msg = f"{metric_name.value} requires a positive k"
        raise RetrievalError(msg)
    if k not in metric_configuration.k_values:
        msg = f"k={k} is not in metric_configuration.k_values {metric_configuration.k_values!r}"
        raise RetrievalError(msg)


def validate_shared_metric_configuration(
    left: SearchMetricConfiguration,
    right: SearchMetricConfiguration,
) -> None:
    if left.model_dump() != right.model_dump():
        msg = "reference and candidate metric_configuration must match for paired analysis"
        raise RetrievalError(msg)


def benjamini_hochberg_adjusted_p_values(
    raw_p_values: tuple[float | None, ...],
) -> tuple[float | None, ...]:
    output: list[float | None] = list(raw_p_values)
    indexed = [(index, value) for index, value in enumerate(raw_p_values) if value is not None]
    if not indexed:
        return tuple(output)
    m = len(indexed)
    sorted_rows = sorted(indexed, key=lambda row: row[1])
    cumulative_min = 1.0
    adjusted_for_sorted: list[float] = []
    for rank in range(m, 0, -1):
        _index, p_value = sorted_rows[rank - 1]
        scaled = min(1.0, p_value * m / rank)
        cumulative_min = min(scaled, cumulative_min)
        adjusted_for_sorted.insert(0, cumulative_min)
    for (index, _p_value), adjusted in zip(sorted_rows, adjusted_for_sorted, strict=True):
        output[index] = adjusted
    return tuple(output)


__all__ = [
    "benjamini_hochberg_adjusted_p_values",
    "validate_k_for_metric",
    "validate_metric_name",
    "validate_shared_metric_configuration",
]
