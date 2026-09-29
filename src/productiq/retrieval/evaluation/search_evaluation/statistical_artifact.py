"""Persisted search statistical analysis artifacts (Phase 12.9)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    deterministic_artifact_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
    SearchStatisticalAnalysisResult,
    search_statistical_analysis_result_to_dict,
)


def build_search_statistical_analysis_artifact_dict(
    result: SearchStatisticalAnalysisResult,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_schema_version": SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION,
        "analysis_result": search_statistical_analysis_result_to_dict(result),
    }
    body["deterministic_checksum_sha256"] = deterministic_artifact_checksum(body)
    return body


def write_search_statistical_analysis_artifact(path: Path, payload: dict[str, Any]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_search_statistical_analysis_artifact(payload: dict[str, object]) -> None:
    version = payload.get("artifact_schema_version")
    if version != SEARCH_STATISTICAL_ANALYSIS_ARTIFACT_SCHEMA_VERSION:
        msg = f"unsupported search statistical analysis artifact schema version: {version!r}"
        raise RetrievalError(msg)
    expected = payload.get("deterministic_checksum_sha256")
    if not isinstance(expected, str):
        msg = "statistical analysis artifact missing deterministic_checksum_sha256"
        raise RetrievalError(msg)
    body = {key: value for key, value in payload.items() if key != "deterministic_checksum_sha256"}
    actual = deterministic_artifact_checksum(body)
    if actual != expected:
        msg = "statistical analysis artifact checksum mismatch"
        raise RetrievalError(msg)
    raw = payload.get("analysis_result")
    if not isinstance(raw, dict):
        msg = "statistical analysis artifact must contain analysis_result"
        raise RetrievalError(msg)
    SearchStatisticalAnalysisResult.model_validate(raw)


__all__ = [
    "build_search_statistical_analysis_artifact_dict",
    "validate_search_statistical_analysis_artifact",
    "write_search_statistical_analysis_artifact",
]
