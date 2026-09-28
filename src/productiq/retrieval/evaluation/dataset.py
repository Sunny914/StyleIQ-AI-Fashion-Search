"""Evaluation dataset models and loading (Phase 4.8)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from productiq.exceptions.base import LexicalRetrievalError
from productiq.retrieval.evaluation.schema import LEXICAL_RETRIEVAL_BENCHMARK_FILENAME


class LexicalEvaluationQuery(BaseModel):
    """One benchmark query with manually judged relevant product IDs."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    category: str = Field(min_length=1)
    relevant_product_ids: tuple[str, ...]

    @field_validator("query_id", "query_text", "category")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "evaluation query fields must not be empty"
            raise ValueError(msg)
        return stripped

    @field_validator("relevant_product_ids", mode="before")
    @classmethod
    def normalize_relevant_product_ids(cls, value: object) -> tuple[str, ...]:
        if isinstance(value, (tuple, list)):
            items: tuple[object, ...] | list[object] = value
        else:
            msg = "relevant_product_ids must be a list or tuple of product IDs"
            raise TypeError(msg)
        seen: set[str] = set()
        normalized: list[str] = []
        for raw in items:
            product_id = str(raw).strip()
            if not product_id:
                msg = "relevant product_id must not be empty"
                raise ValueError(msg)
            if product_id in seen:
                continue
            seen.add(product_id)
            normalized.append(product_id)
        if not normalized:
            msg = "relevant_product_ids must contain at least one product ID"
            raise ValueError(msg)
        return tuple(normalized)


class LexicalRetrievalBenchmark(BaseModel):
    """Versioned lexical retrieval evaluation benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    catalog_artifact: str = Field(min_length=1)
    source_representation_checksum: str | None = None
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


def load_lexical_retrieval_benchmark(path: Path) -> LexicalRetrievalBenchmark:
    """Load a lexical retrieval benchmark JSON file."""
    resolved = Path(path)
    if not resolved.is_file():
        msg = f"lexical retrieval benchmark not found: {resolved}"
        raise LexicalRetrievalError(msg)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        msg = f"lexical retrieval benchmark is not valid JSON: {resolved}"
        raise LexicalRetrievalError(msg) from exc
    if not isinstance(payload, dict):
        msg = "lexical retrieval benchmark must be a JSON object"
        raise LexicalRetrievalError(msg)
    return LexicalRetrievalBenchmark.model_validate(payload)


def default_benchmark_path(repo_root: Path | None = None) -> Path:
    """Default path to the v1 lexical retrieval benchmark."""
    root = repo_root or Path.cwd()
    return root / "resources" / "evaluation" / LEXICAL_RETRIEVAL_BENCHMARK_FILENAME


def lexical_retrieval_benchmark_to_dict(benchmark: LexicalRetrievalBenchmark) -> dict[str, Any]:
    return benchmark.model_dump(mode="json")


__all__ = [
    "LexicalEvaluationQuery",
    "LexicalRetrievalBenchmark",
    "lexical_retrieval_benchmark_to_dict",
    "load_lexical_retrieval_benchmark",
]
