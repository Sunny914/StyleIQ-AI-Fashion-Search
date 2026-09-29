"""Provenance integrity checks for Phase 12 evaluation hardening (12.11)."""

from __future__ import annotations

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.experiment_validation import (
    validate_shared_evaluation_envelope,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.reproducibility import (
    BM25_SCOPED_INDEX_MODE,
)


def validate_provenance_consistency(sources: SearchEvaluationReportSources) -> None:
    envelope = validate_shared_evaluation_envelope(
        [row.evaluation_result for row in sources.baselines]
    )
    for bundle in sources.baselines:
        lineage = bundle.evaluation_result.lineage
        if lineage.catalog_artifact != envelope.catalog_artifact:
            msg = f"baseline {lineage.variant_name!r} catalog_artifact mismatch"
            raise RetrievalError(msg)
        if lineage.source_representation_checksum != envelope.source_representation_checksum:
            msg = f"baseline {lineage.variant_name!r} source_representation_checksum mismatch"
            raise RetrievalError(msg)

    if sources.baseline_experiment is not None:
        exp_env = sources.baseline_experiment.envelope
        if exp_env.catalog_artifact != envelope.catalog_artifact:
            msg = "12.6 experiment catalog_artifact mismatch"
            raise RetrievalError(msg)
        if exp_env.source_representation_checksum != envelope.source_representation_checksum:
            msg = "12.6 experiment source_representation_checksum mismatch"
            raise RetrievalError(msg)

    if sources.ranking_experiment is not None:
        rank_env = sources.ranking_experiment.envelope
        if rank_env.catalog_artifact != envelope.catalog_artifact:
            msg = "12.7 ranking experiment catalog_artifact mismatch"
            raise RetrievalError(msg)
        if rank_env.source_representation_checksum != envelope.source_representation_checksum:
            msg = "12.7 ranking experiment source_representation_checksum mismatch"
            raise RetrievalError(msg)

    for bundle in sources.baselines:
        provenance = bundle.payload.get("retrieval_provenance")
        if not isinstance(provenance, dict):
            continue
        mode = provenance.get("index_mode") or provenance.get("bm25_index_mode")
        if (
            mode == BM25_SCOPED_INDEX_MODE
            and "bm25" in bundle.evaluation_result.lineage.variant_name
        ):
            continue


def validate_variant_identity_uniqueness(sources: SearchEvaluationReportSources) -> None:
    seen: set[tuple[str, str]] = set()
    for bundle in sources.baselines:
        key = (
            bundle.evaluation_result.lineage.variant_name,
            bundle.evaluation_result.lineage.variant_version,
        )
        if key in seen:
            msg = f"duplicate variant identity {key!r}"
            raise RetrievalError(msg)
        seen.add(key)


__all__ = [
    "validate_provenance_consistency",
    "validate_variant_identity_uniqueness",
]
