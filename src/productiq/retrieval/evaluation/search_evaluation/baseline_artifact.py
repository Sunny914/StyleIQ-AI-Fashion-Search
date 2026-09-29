"""Baseline search evaluation artifact persistence (Phase 12.5)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchMetricConfiguration,
)
from productiq.retrieval.evaluation.search_evaluation.result_schema import (
    SearchVariantEvaluationResult,
    search_variant_evaluation_result_to_dict,
)


def default_baseline_metric_configuration() -> SearchMetricConfiguration:
    from productiq.retrieval.evaluation.schema import (
        DEFAULT_EVALUATION_K_VALUES,
        DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
    )

    return SearchMetricConfiguration(
        k_values=DEFAULT_EVALUATION_K_VALUES,
        evaluation_top_k=DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
        execution_top_k=DEFAULT_RETRIEVAL_EVALUATION_TOP_K,
        min_relevant_grade=2,
        compute_ndcg=True,
    )


def execution_configuration_dict(
    metric_configuration: SearchMetricConfiguration,
) -> dict[str, Any]:
    return {
        "execution_top_k": metric_configuration.execution_top_k,
        "evaluation_top_k": metric_configuration.evaluation_top_k,
        "metric_configuration": metric_configuration.model_dump(mode="json"),
    }


def build_baseline_run_artifact(
    result: SearchVariantEvaluationResult,
    *,
    retrieval_provenance: dict[str, Any],
    runtime_metadata: dict[str, Any],
    historical_reference: dict[str, Any] | None = None,
    artifact_schema_version: str = SEARCH_BASELINE_ARTIFACT_SCHEMA_VERSION,
) -> dict[str, Any]:
    """Build a persisted baseline artifact (runtime metadata separate from deterministic body)."""
    evaluation_result = search_variant_evaluation_result_to_dict(result)
    artifact: dict[str, Any] = {
        "artifact_schema_version": artifact_schema_version,
        "benchmark_name": result.lineage.benchmark_name,
        "benchmark_version": result.lineage.benchmark_version,
        "variant_name": result.lineage.variant_name,
        "variant_version": result.lineage.variant_version,
        "execution_configuration": execution_configuration_dict(result.lineage.metric_configuration),
        "retrieval_provenance": retrieval_provenance,
        "evaluation_result": evaluation_result,
        "query_count": len(result.per_query),
        "successful_query_count": len(result.per_query),
    }
    if historical_reference is not None:
        artifact["historical_reference"] = historical_reference
    artifact["deterministic_checksum_sha256"] = deterministic_artifact_checksum(artifact)
    artifact["runtime_metadata"] = runtime_metadata
    return artifact


def deterministic_artifact_checksum(payload: dict[str, Any]) -> str:
    serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def write_baseline_run_artifact(path: Path, artifact: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(artifact, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_baseline_run_artifact(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        msg = f"baseline run artifact must be a JSON object: {path}"
        raise TypeError(msg)
    return payload


def validate_baseline_run_artifact(payload: dict[str, Any]) -> None:
    required = (
        "artifact_schema_version",
        "benchmark_name",
        "benchmark_version",
        "variant_name",
        "variant_version",
        "execution_configuration",
        "evaluation_result",
        "deterministic_checksum_sha256",
    )
    for key in required:
        if key not in payload:
            msg = f"baseline artifact missing required field {key!r}"
            raise ValueError(msg)
    body = {k: v for k, v in payload.items() if k not in {"runtime_metadata", "deterministic_checksum_sha256"}}
    expected = payload["deterministic_checksum_sha256"]
    actual = deterministic_artifact_checksum(body)
    if actual != expected:
        msg = "baseline artifact deterministic_checksum_sha256 mismatch"
        raise ValueError(msg)


__all__ = [
    "build_baseline_run_artifact",
    "default_baseline_metric_configuration",
    "deterministic_artifact_checksum",
    "execution_configuration_dict",
    "load_baseline_run_artifact",
    "validate_baseline_run_artifact",
    "write_baseline_run_artifact",
]
