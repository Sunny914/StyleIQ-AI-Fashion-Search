"""Search evaluation benchmark contracts (Phase 12.1)."""

from __future__ import annotations

from typing import Any, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from productiq.retrieval.evaluation.search_evaluation.schema import (
    MAX_SEARCH_RELEVANCE_GRADE,
    MIN_SEARCH_RELEVANCE_GRADE,
)


class SearchRelevanceJudgment(BaseModel):
    """Curated relevance grade for one query/product pair (not retriever scores)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    grade: int = Field(ge=MIN_SEARCH_RELEVANCE_GRADE, le=MAX_SEARCH_RELEVANCE_GRADE)

    @field_validator("product_id")
    @classmethod
    def strip_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped


class SearchEvaluationQuery(BaseModel):
    """One benchmark search query and its curated judgments."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    query_text: str = Field(min_length=1)
    query_category: str = Field(default="general", min_length=1)
    relevance_judgments: tuple[SearchRelevanceJudgment, ...] = Field(min_length=1)

    @field_validator("query_id", "query_text", "query_category")
    @classmethod
    def strip_text(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "query fields must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_judgments(self) -> Self:
        product_ids = [row.product_id for row in self.relevance_judgments]
        if len(product_ids) != len(set(product_ids)):
            msg = "relevance_judgments must not duplicate product_id within a query"
            raise ValueError(msg)
        return self


class SearchEvaluationBenchmarkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    catalog_artifact: str | None = None
    source_representation_checksum: str | None = None
    methodology: str = Field(min_length=1)
    labeling_methodology: str = Field(min_length=1)
    limitations: str = Field(min_length=1)


class SearchEvaluationBenchmark(BaseModel):
    """Versioned offline search evaluation benchmark."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: SearchEvaluationBenchmarkMetadata
    queries: tuple[SearchEvaluationQuery, ...]

    @property
    def benchmark_name(self) -> str:
        return self.metadata.benchmark_name

    @property
    def benchmark_version(self) -> str:
        return self.metadata.benchmark_version

    @model_validator(mode="after")
    def validate_queries(self) -> Self:
        if not self.queries:
            msg = "benchmark must contain at least one query"
            raise ValueError(msg)
        query_ids = [query.query_id for query in self.queries]
        if len(query_ids) != len(set(query_ids)):
            msg = "benchmark query_id values must be unique"
            raise ValueError(msg)
        return self


def search_evaluation_benchmark_to_dict(benchmark: SearchEvaluationBenchmark) -> dict[str, Any]:
    return benchmark.model_dump(mode="json")


def lexical_query_to_search_evaluation_query(
    *,
    query_id: str,
    query_text: str,
    category: str,
    relevant_product_ids: tuple[str, ...],
    binary_relevant_grade: int = 2,
) -> SearchEvaluationQuery:
    """Map legacy binary lexical benchmark rows to graded search evaluation queries."""
    if (
        binary_relevant_grade < MIN_SEARCH_RELEVANCE_GRADE
        or binary_relevant_grade > MAX_SEARCH_RELEVANCE_GRADE
    ):
        msg = "binary_relevant_grade out of supported range"
        raise ValueError(msg)
    return SearchEvaluationQuery(
        query_id=query_id,
        query_text=query_text,
        query_category=category,
        relevance_judgments=tuple(
            SearchRelevanceJudgment(product_id=product_id, grade=binary_relevant_grade)
            for product_id in relevant_product_ids
        ),
    )


__all__ = [
    "SearchEvaluationBenchmark",
    "SearchEvaluationBenchmarkMetadata",
    "SearchEvaluationQuery",
    "SearchRelevanceJudgment",
    "lexical_query_to_search_evaluation_query",
    "search_evaluation_benchmark_to_dict",
]
