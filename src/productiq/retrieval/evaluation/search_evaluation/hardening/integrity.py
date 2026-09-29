"""Artifact integrity checks for Phase 12 evaluation hardening (12.11)."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    load_baseline_run_artifact,
    validate_baseline_run_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_artifact import (
    validate_search_failure_analysis_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_artifact import (
    validate_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_artifact import (
    validate_search_evaluation_report_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_artifact import (
    validate_search_statistical_analysis_artifact,
)


def load_json_object(path: Path) -> dict[str, object]:
    if not path.is_file():
        msg = f"artifact not found: {path}"
        raise RetrievalError(msg)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"invalid JSON in artifact {path}: {exc}"
        raise RetrievalError(msg) from exc
    if not isinstance(raw, dict):
        msg = f"artifact must be a JSON object: {path}"
        raise RetrievalError(msg)
    return raw


def validate_artifact_integrity(
    path: Path,
    *,
    validator: Callable[[dict[str, object]], None],
    loader: Callable[[Path], dict[str, object]] | None = None,
) -> dict[str, object]:
    """Load artifact and run schema/checksum validation. Fail closed."""
    if loader is not None:
        payload = loader(path)
    else:
        payload = load_json_object(path)
    validator(payload)
    return payload


def validate_baseline_artifact_file(path: Path) -> dict[str, object]:
    return validate_artifact_integrity(
        path,
        validator=validate_baseline_run_artifact,
        loader=load_baseline_run_artifact,
    )


def validate_ranking_experiment_artifact_file(path: Path) -> dict[str, object]:
    return validate_artifact_integrity(path, validator=validate_ranking_experiment_artifact)


def validate_failure_analysis_artifact_file(path: Path) -> dict[str, object]:
    return validate_artifact_integrity(path, validator=validate_search_failure_analysis_artifact)


def validate_statistical_analysis_artifact_file(path: Path) -> dict[str, object]:
    return validate_artifact_integrity(
        path, validator=validate_search_statistical_analysis_artifact
    )


def validate_evaluation_report_artifact_file(path: Path) -> dict[str, object]:
    return validate_artifact_integrity(path, validator=validate_search_evaluation_report_artifact)


def verify_declared_checksum(payload: dict[str, object], *, label: str) -> None:
    from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
        deterministic_artifact_checksum,
    )

    expected = payload.get("deterministic_checksum_sha256")
    if not isinstance(expected, str):
        msg = f"{label} missing deterministic_checksum_sha256"
        raise RetrievalError(msg)
    body = {key: value for key, value in payload.items() if key != "deterministic_checksum_sha256"}
    actual = deterministic_artifact_checksum(body)
    if actual != expected:
        msg = f"{label} checksum mismatch"
        raise RetrievalError(msg)


__all__ = [
    "load_json_object",
    "validate_artifact_integrity",
    "validate_baseline_artifact_file",
    "validate_evaluation_report_artifact_file",
    "validate_failure_analysis_artifact_file",
    "validate_ranking_experiment_artifact_file",
    "validate_statistical_analysis_artifact_file",
    "verify_declared_checksum",
]
