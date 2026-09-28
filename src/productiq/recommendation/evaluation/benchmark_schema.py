"""Recommendation evaluation contracts (Phase 11.7)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

RECOMMENDATION_BENCHMARK_NAME = "productiq_recommendation_v1"
RECOMMENDATION_BENCHMARK_VERSION = "1.0.0"
RECOMMENDATION_BENCHMARK_FILENAME = "productiq_recommendation_v1.json"
RECOMMENDATION_EVALUATION_VERSION = "11.7.0"

RECOMMENDATION_VARIANT_BASELINE_11_5 = "baseline_ranker_11_5"
RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6 = (
    "baseline_ranker_11_5_plus_selection_11_6"
)

MIN_RELEVANCE_GRADE = 0
MAX_RELEVANCE_GRADE = 3


class RelevanceJudgment(BaseModel):
    """Curated offline grade for one candidate product (not user behavior)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str = Field(min_length=1)
    grade: int = Field(ge=MIN_RELEVANCE_GRADE, le=MAX_RELEVANCE_GRADE)

    @field_validator("product_id")
    @classmethod
    def strip_product_id(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "product_id must not be empty"
            raise ValueError(msg)
        return stripped


class RecommendationBenchmarkCase(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    seed_product_id: str = Field(min_length=1)
    seed_category: str = Field(min_length=1)
    methodology_note: str = Field(min_length=1)
    relevance_judgments: tuple[RelevanceJudgment, ...] = Field(min_length=1)

    @field_validator("seed_product_id")
    @classmethod
    def strip_seed(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            msg = "seed_product_id must not be empty"
            raise ValueError(msg)
        return stripped

    @model_validator(mode="after")
    def validate_judgments(self) -> RecommendationBenchmarkCase:
        if self.seed_product_id in {row.product_id for row in self.relevance_judgments}:
            msg = "seed_product_id must not appear in relevance_judgments"
            raise ValueError(msg)
        product_ids = [row.product_id for row in self.relevance_judgments]
        if len(product_ids) != len(set(product_ids)):
            msg = "relevance_judgments must not duplicate product_id"
            raise ValueError(msg)
        return self


class RecommendationBenchmarkMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    benchmark_name: str = Field(default=RECOMMENDATION_BENCHMARK_NAME, min_length=1)
    benchmark_version: str = Field(default=RECOMMENDATION_BENCHMARK_VERSION, min_length=1)
    catalog_artifact: str = Field(min_length=1)
    source_representation_checksum: str | None = None
    eligible_catalog_product_count: int | None = Field(default=None, ge=1)
    methodology: str = Field(min_length=1)
    labeling_methodology: str = Field(min_length=1)
    limitations: str = Field(min_length=1)
    seed_selection_methodology: str = Field(min_length=1)


class RecommendationBenchmark(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    metadata: RecommendationBenchmarkMetadata
    cases: tuple[RecommendationBenchmarkCase, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_unique_seeds(self) -> RecommendationBenchmark:
        seeds = [case.seed_product_id for case in self.cases]
        if len(seeds) != len(set(seeds)):
            msg = "benchmark cases must have unique seed_product_id values"
            raise ValueError(msg)
        return self


def benchmark_to_dict(benchmark: RecommendationBenchmark) -> dict[str, Any]:
    return benchmark.model_dump(mode="json")


__all__ = [
    "MAX_RELEVANCE_GRADE",
    "MIN_RELEVANCE_GRADE",
    "RECOMMENDATION_BENCHMARK_FILENAME",
    "RECOMMENDATION_BENCHMARK_NAME",
    "RECOMMENDATION_BENCHMARK_VERSION",
    "RECOMMENDATION_EVALUATION_VERSION",
    "RECOMMENDATION_VARIANT_BASELINE_11_5",
    "RECOMMENDATION_VARIANT_BASELINE_11_5_PLUS_SELECTION_11_6",
    "RecommendationBenchmark",
    "RecommendationBenchmarkCase",
    "RecommendationBenchmarkMetadata",
    "RelevanceJudgment",
    "benchmark_to_dict",
]
