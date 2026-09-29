"""Validate shared ranking experiment envelope (Phase 12.7)."""

from __future__ import annotations

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SearchRankingCandidatePool,
    SearchRankingExperimentDefinition,
    SearchRankingExperimentEnvelope,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)


def build_ranking_experiment_envelope(
    definition: SearchRankingExperimentDefinition,
    candidate_pool: SearchRankingCandidatePool,
) -> SearchRankingExperimentEnvelope:
    if candidate_pool.benchmark_name != definition.benchmark_name:
        msg = "candidate pool benchmark_name does not match experiment definition"
        raise RetrievalError(msg)
    if candidate_pool.benchmark_version != definition.benchmark_version:
        msg = "candidate pool benchmark_version does not match experiment definition"
        raise RetrievalError(msg)
    if candidate_pool.candidate_pool_configuration != definition.candidate_pool_configuration:
        msg = "candidate pool configuration does not match experiment definition"
        raise RetrievalError(msg)
    if candidate_pool.retrieval_provenance != definition.retrieval_provenance:
        msg = "candidate pool retrieval provenance does not match experiment definition"
        raise RetrievalError(msg)
    return SearchRankingExperimentEnvelope(
        benchmark_name=definition.benchmark_name,
        benchmark_version=definition.benchmark_version,
        metric_configuration=definition.metric_configuration,
        candidate_pool_configuration=definition.candidate_pool_configuration,
        retrieval_provenance=definition.retrieval_provenance,
        catalog_artifact=definition.catalog_artifact,
        source_representation_checksum=definition.source_representation_checksum,
    )


def validate_ranking_variant_envelope(
    results: tuple[SearchVariantEvaluationResult, ...],
    envelope: SearchRankingExperimentEnvelope,
) -> None:
    validate_shared_evaluation_envelope(results)
    reference = results[0].lineage
    if reference.benchmark_name != envelope.benchmark_name:
        msg = "variant result benchmark_name does not match ranking envelope"
        raise RetrievalError(msg)
    if reference.metric_configuration != envelope.metric_configuration:
        msg = "variant result metric_configuration does not match ranking envelope"
        raise RetrievalError(msg)


__all__ = [
    "build_ranking_experiment_envelope",
    "validate_ranking_variant_envelope",
]
