"""Semantic retrieval benchmark models and loading (Phase 4.14)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.evaluation.dataset import LexicalEvaluationQuery
from productiq.retrieval.evaluation.semantic_schema import (
    SEMANTIC_RETRIEVAL_BENCHMARK_FILENAME,
    SEMANTIC_RETRIEVAL_METHOD,
)

DEFAULT_RELEVANCE_POLICY = (
    "Binary relevance (1=relevant, 0=not judged). A product is relevant only when "
    "inspectable catalog fields (brand, category, color, material, product type, and "
    "description-aligned attributes) support the query's explicit product intent. "
    "Judgments are human-curated and independent of embedding similarity or retriever output."
)


class SemanticRetrievalBenchmark(BaseModel):
    """Versioned semantic retrieval evaluation benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    catalog_artifact: str = Field(min_length=1)
    source_representation_checksum: str | None = None
    source_embedding_artifact_checksum: str | None = None
    embedding_model_id: str = Field(min_length=1)
    embedding_model_revision: str | None = None
    embedding_dimension: int = Field(gt=0)
    similarity_metric: str = Field(min_length=1)
    retrieval_method: str = Field(min_length=1)
    relevance_policy: str = Field(min_length=1)
    methodology: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    queries: tuple[LexicalEvaluationQuery, ...]

    @field_validator("queries")
    @classmethod
    def validate_unique_query_ids(
        cls, value: tuple[LexicalEvaluationQuery, ...]
    ) -> tuple[LexicalEvaluationQuery, ...]:
        if not value:
            msg = "benchmark must contain at least one query"
            raise ValueError(msg)
        ids = [query.query_id for query in value]
        if len(set(ids)) != len(ids):
            msg = "benchmark query_id values must be unique"
            raise ValueError(msg)
        return value

    @field_validator("retrieval_method")
    @classmethod
    def validate_retrieval_method(cls, value: str) -> str:
        if value.strip().lower() != SEMANTIC_RETRIEVAL_METHOD:
            msg = f"semantic benchmark retrieval_method must be {SEMANTIC_RETRIEVAL_METHOD}"
            raise ValueError(msg)
        return value.strip().lower()


def load_semantic_retrieval_benchmark(path: Path) -> SemanticRetrievalBenchmark:
    """Load a semantic retrieval benchmark JSON file."""
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"semantic retrieval benchmark not found: {resolved}"
        raise LexicalRetrievalError(msg)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"semantic retrieval benchmark is not valid JSON: {resolved}"
        raise LexicalRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "semantic retrieval benchmark must be a JSON object"
        raise LexicalRetrievalError(msg)
    return SemanticRetrievalBenchmark.model_validate(payload)


def default_semantic_benchmark_path(repo_root: Path | None = None) -> Path:
    root = repo_root or Path.cwd()
    return root / "resources" / "evaluation" / SEMANTIC_RETRIEVAL_BENCHMARK_FILENAME


def semantic_retrieval_benchmark_to_dict(benchmark: SemanticRetrievalBenchmark) -> dict[str, Any]:
    return benchmark.model_dump(mode="json")


def judged_relevant_product_count(benchmark: SemanticRetrievalBenchmark) -> int:
    return sum(len(query.relevant_product_ids) for query in benchmark.queries)


__all__ = [
    "DEFAULT_RELEVANCE_POLICY",
    "SemanticRetrievalBenchmark",
    "default_semantic_benchmark_path",
    "judged_relevant_product_count",
    "load_semantic_retrieval_benchmark",
    "semantic_retrieval_benchmark_to_dict",
]
