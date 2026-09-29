"""Load canonical search evaluation benchmark artifacts (Phase 12.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, ValidationError, field_validator

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION,
    SEARCH_BENCHMARK_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_integrity import (
    validate_search_benchmark_integrity,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_schema import (
    SearchEvaluationBenchmark,
    SearchEvaluationBenchmarkMetadata,
    SearchEvaluationQuery,
)
from productiq.retrieval.evaluation.search_evaluation.request_schema import (
    SearchEvaluationRequest,
    SearchEvaluationVariant,
    SearchMetricConfiguration,
)


class SearchBenchmarkArtifactFile(BaseModel):
    """On-disk benchmark envelope (artifact schema version + 12.1 benchmark body)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    artifact_schema_version: str
    metadata: SearchEvaluationBenchmarkMetadata
    queries: tuple[SearchEvaluationQuery, ...]

    @field_validator("artifact_schema_version")
    @classmethod
    def strip_version(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "artifact_schema_version must not be empty"
            raise ValueError(msg)
        return stripped

    def to_benchmark(self) -> SearchEvaluationBenchmark:
        return SearchEvaluationBenchmark(metadata=self.metadata, queries=self.queries)


def _parse_benchmark_payload(raw: Any, *, source: str) -> SearchEvaluationBenchmark:
    if not isinstance(raw, dict):
        msg = f"search benchmark must be a JSON object: {source}"
        raise RetrievalError(msg)
    try:
        artifact = SearchBenchmarkArtifactFile.model_validate(raw)
    except ValidationError as exc:
        msg = f"invalid search benchmark JSON ({source}): {exc}"
        raise RetrievalError(msg) from exc
    if artifact.artifact_schema_version != SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION:
        msg = (
            f"unsupported search benchmark artifact_schema_version "
            f"{artifact.artifact_schema_version!r}; expected "
            f"{SEARCH_BENCHMARK_ARTIFACT_SCHEMA_VERSION!r}"
        )
        raise RetrievalError(msg)
    benchmark = artifact.to_benchmark()
    validate_search_benchmark_integrity(benchmark)
    return benchmark


def load_search_evaluation_benchmark(path: Path) -> SearchEvaluationBenchmark:
    """Load and validate the canonical search benchmark artifact."""
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"search evaluation benchmark not found: {resolved}"
        raise RetrievalError(msg)
    try:
        raw = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"search evaluation benchmark is not valid JSON: {resolved}"
        raise RetrievalError(msg) from exc
    return _parse_benchmark_payload(raw, source=str(resolved))


def default_search_benchmark_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "resources" / "evaluation" / SEARCH_BENCHMARK_FILENAME


def build_search_evaluation_request(
    benchmark: SearchEvaluationBenchmark,
    variant: SearchEvaluationVariant,
    *,
    metric_configuration: SearchMetricConfiguration | None = None,
) -> SearchEvaluationRequest:
    return SearchEvaluationRequest(
        benchmark=benchmark,
        variant=variant,
        metric_configuration=metric_configuration or SearchMetricConfiguration(),
    )


__all__ = [
    "SearchBenchmarkArtifactFile",
    "build_search_evaluation_request",
    "default_search_benchmark_path",
    "load_search_evaluation_benchmark",
]
