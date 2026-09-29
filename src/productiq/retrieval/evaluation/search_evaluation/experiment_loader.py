"""Load variant evaluation results from baseline artifacts (Phase 12.6)."""

from __future__ import annotations

from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SearchBaselineArtifactReference,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
)


def evaluation_result_from_baseline_artifact(
    payload: dict[str, object],
) -> SearchVariantEvaluationResult:
    raw = payload.get("evaluation_result")
    if not isinstance(raw, dict):
        msg = "baseline artifact must contain evaluation_result object"
        raise RetrievalError(msg)
    try:
        return SearchVariantEvaluationResult.model_validate(raw)
    except Exception as exc:
        msg = f"invalid evaluation_result in baseline artifact: {exc}"
        raise RetrievalError(msg) from exc


def load_variant_evaluation_from_baseline_artifact(
    path: Path,
    *,
    reference: SearchBaselineArtifactReference | None = None,
    validate_checksum: bool = True,
) -> tuple[SearchVariantEvaluationResult, dict[str, object]]:
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"baseline evaluation artifact not found: {resolved}"
        raise RetrievalError(msg)
    payload = load_baseline_run_artifact(resolved)
    if validate_checksum:
        validate_baseline_run_artifact(payload)
    if reference is not None:
        if payload.get("variant_name") != reference.variant_name:
            msg = (
                f"artifact variant_name {payload.get('variant_name')!r} "
                f"does not match reference {reference.variant_name!r}"
            )
            raise RetrievalError(msg)
        expected_checksum = reference.deterministic_checksum_sha256
        if expected_checksum is not None:
            actual = payload.get("deterministic_checksum_sha256")
            if actual != expected_checksum:
                msg = (
                    f"checksum mismatch for {reference.variant_name!r} "
                    f"at {reference.artifact_path!r}"
                )
                raise RetrievalError(msg)
    result = evaluation_result_from_baseline_artifact(payload)
    return result, payload


def artifact_reference_from_baseline_payload(
    *,
    artifact_path: str,
    payload: dict[str, object],
) -> SearchBaselineArtifactReference:
    provenance = payload.get("retrieval_provenance")
    index_mode = None
    if isinstance(provenance, dict):
        raw_mode = provenance.get("index_mode") or provenance.get("bm25_index_mode")
        if isinstance(raw_mode, str):
            index_mode = raw_mode
    checksum = payload.get("deterministic_checksum_sha256")
    return SearchBaselineArtifactReference(
        variant_name=str(payload.get("variant_name", "")),
        variant_version=str(payload.get("variant_version", "")),
        artifact_path=artifact_path,
        deterministic_checksum_sha256=str(checksum) if checksum is not None else None,
        retrieval_index_mode=index_mode,
    )


__all__ = [
    "artifact_reference_from_baseline_payload",
    "evaluation_result_from_baseline_artifact",
    "load_variant_evaluation_from_baseline_artifact",
]
