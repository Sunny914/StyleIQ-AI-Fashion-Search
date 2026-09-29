"""Persisted search ranking experiment artifacts (Phase 12.7)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.baseline_artifact import (
    deterministic_artifact_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_loader import (
    load_ranking_experiment_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
    SearchRankingExperimentDefinition,
    SearchRankingExperimentResult,
    search_ranking_experiment_result_to_dict,
)


def build_ranking_experiment_artifact_dict(
    definition: SearchRankingExperimentDefinition,
    result: SearchRankingExperimentResult,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "artifact_schema_version": SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
        "experiment_definition": definition.model_dump(mode="json"),
        "experiment_result": search_ranking_experiment_result_to_dict(result),
    }
    body["deterministic_checksum_sha256"] = deterministic_artifact_checksum(body)
    return body


def write_ranking_experiment_artifact(path: Path, payload: dict[str, Any]) -> None:
    resolved = Path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    resolved.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def validate_ranking_experiment_artifact(payload: dict[str, object]) -> None:
    version = payload.get("artifact_schema_version")
    if version != SEARCH_RANKING_EXPERIMENT_ARTIFACT_SCHEMA_VERSION:
        msg = f"unsupported ranking experiment artifact schema version: {version!r}"
        raise RetrievalError(msg)
    expected = payload.get("deterministic_checksum_sha256")
    if not isinstance(expected, str):
        msg = "ranking experiment artifact missing deterministic_checksum_sha256"
        raise RetrievalError(msg)
    body = {key: value for key, value in payload.items() if key != "deterministic_checksum_sha256"}
    actual = deterministic_artifact_checksum(body)
    if actual != expected:
        msg = "ranking experiment artifact checksum mismatch"
        raise RetrievalError(msg)
    definition_raw = payload.get("experiment_definition")
    result_raw = payload.get("experiment_result")
    if not isinstance(definition_raw, dict) or not isinstance(result_raw, dict):
        msg = "ranking experiment artifact must contain definition and result objects"
        raise RetrievalError(msg)
    SearchRankingExperimentDefinition.model_validate(definition_raw)
    SearchRankingExperimentResult.model_validate(result_raw)


def load_validated_ranking_experiment_artifact(path: Path) -> dict[str, object]:
    payload = load_ranking_experiment_artifact(path)
    validate_ranking_experiment_artifact(payload)
    return payload


__all__ = [
    "build_ranking_experiment_artifact_dict",
    "load_validated_ranking_experiment_artifact",
    "validate_ranking_experiment_artifact",
    "write_ranking_experiment_artifact",
]
