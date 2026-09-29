"""Validate shared evaluation envelope across experiment variants (Phase 12.6)."""

from __future__ import annotations

from collections.abc import Sequence

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SearchEvaluationExperimentEnvelope,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)


def validate_shared_evaluation_envelope(
    results: Sequence[SearchVariantEvaluationResult],
) -> SearchEvaluationExperimentEnvelope:
    if not results:
        msg = "experiment requires at least one variant evaluation result"
        raise RetrievalError(msg)
    reference = results[0]
    lineage = reference.lineage
    for row in results[1:]:
        other = row.lineage
        if (
            other.benchmark_name != lineage.benchmark_name
            or other.benchmark_version != lineage.benchmark_version
        ):
            msg = "experiment variants must share benchmark name and version"
            raise RetrievalError(msg)
        if other.metric_configuration != lineage.metric_configuration:
            msg = "experiment variants must share identical metric_configuration"
            raise RetrievalError(msg)
        if other.catalog_artifact != lineage.catalog_artifact:
            msg = "experiment variants must share catalog_artifact provenance"
            raise RetrievalError(msg)
        if other.source_representation_checksum != lineage.source_representation_checksum:
            msg = "experiment variants must share source_representation_checksum"
            raise RetrievalError(msg)
    return SearchEvaluationExperimentEnvelope(
        benchmark_name=lineage.benchmark_name,
        benchmark_version=lineage.benchmark_version,
        metric_configuration=lineage.metric_configuration,
        catalog_artifact=lineage.catalog_artifact,
        source_representation_checksum=lineage.source_representation_checksum,
    )


__all__ = ["validate_shared_evaluation_envelope"]
