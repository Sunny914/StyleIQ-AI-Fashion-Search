"""Persist search evaluation report artifacts (Phase 12.10)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    deterministic_artifact_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION,
    SearchEvaluationReport,
    search_evaluation_report_to_dict,
)


def build_search_evaluation_report_artifact_dict(report: SearchEvaluationReport) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_schema_version": SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION,
        "report": search_evaluation_report_to_dict(report),
    }
    body["deterministic_checksum_sha256"] = deterministic_artifact_checksum(body)
    return body


def write_search_evaluation_report_artifact(path: Path, payload: dict[str, Any]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_search_evaluation_report_artifact(payload: dict[str, object]) -> None:
    version = payload.get("artifact_schema_version")
    if version != SEARCH_EVALUATION_REPORT_ARTIFACT_SCHEMA_VERSION:
        msg = f"unsupported search evaluation report artifact schema version: {version!r}"
        raise RetrievalError(msg)
    expected = payload.get("deterministic_checksum_sha256")
    if not isinstance(expected, str):
        msg = "report artifact missing deterministic_checksum_sha256"
        raise RetrievalError(msg)
    body = {key: value for key, value in payload.items() if key != "deterministic_checksum_sha256"}
    actual = deterministic_artifact_checksum(body)
    if actual != expected:
        msg = "search evaluation report artifact checksum mismatch"
        raise RetrievalError(msg)
    raw = payload.get("report")
    if not isinstance(raw, dict):
        msg = "report artifact must contain report object"
        raise RetrievalError(msg)
    SearchEvaluationReport.model_validate(raw)


__all__ = [
    "build_search_evaluation_report_artifact_dict",
    "validate_search_evaluation_report_artifact",
    "write_search_evaluation_report_artifact",
]
