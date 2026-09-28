"""Ranking failure-analysis contracts (Phase 10.9)."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field

from productiq.ranking.hardening.config import RANKING_FAILURE_ANALYSIS_VERSION

RANKING_FAILURE_ANALYSIS_FILENAME = "ranking_failure_analysis_v10_9.json"


class RankingFailureCategory(StrEnum):
    RELEVANT_NOT_IN_CANDIDATE_POOL = "RELEVANT_NOT_IN_CANDIDATE_POOL"
    RELEVANT_RETRIEVED_BUT_RANKED_LOW = "RELEVANT_RETRIEVED_BUT_RANKED_LOW"
    RELEVANT_RANKED_HIGH = "RELEVANT_RANKED_HIGH"
    EMPTY_CANDIDATE_POOL = "EMPTY_CANDIDATE_POOL"
    EVALUATION_DEPTH_LIMITED = "EVALUATION_DEPTH_LIMITED"
    CANDIDATE_FEATURE_MISMATCH = "CANDIDATE_FEATURE_MISMATCH"
    MISSING_NORMALIZED_FEATURES = "MISSING_NORMALIZED_FEATURES"
    MISSING_CATALOG_CONTEXT = "MISSING_CATALOG_CONTEXT"
    NORMALIZATION_EDGE_CASE = "NORMALIZATION_EDGE_CASE"
    DETERMINISTIC_TIE_OBSERVED = "DETERMINISTIC_TIE_OBSERVED"
    LTR_ARTIFACT_INCOMPATIBLE = "LTR_ARTIFACT_INCOMPATIBLE"
    LTR_INFERENCE_FAILURE = "LTR_INFERENCE_FAILURE"


class RankingFailureRecord(BaseModel):
    """One structured failure/diagnostic row (observed facts separated from hypotheses)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str = Field(min_length=1)
    category: RankingFailureCategory
    affected_stage: str = Field(min_length=1)
    observed_facts: tuple[str, ...]
    diagnosis_hypotheses: tuple[str, ...] = Field(
        description="Interpretive hypotheses; not proven root causes.",
    )
    evidence: dict[str, str | int | float | bool | None] = Field(default_factory=dict)
    mitigation: str | None = None
    remaining_limitation: str | None = None


class RankingOperationalMeasurement(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    label: str = Field(min_length=1)
    value: float | int | str | None
    measurement_kind: str = Field(
        min_length=1,
        description="benchmark/test measurement | implementation property | not yet measured",
    )


class RankingFailureAnalysisReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_version: str = RANKING_FAILURE_ANALYSIS_VERSION
    benchmark_name: str = Field(min_length=1)
    benchmark_version: str = Field(min_length=1)
    query_count: int = Field(ge=0)
    judged_relevance_count: int = Field(ge=0)
    production_ranking_baseline_version: str = Field(min_length=1)
    records: tuple[RankingFailureRecord, ...]
    operational_measurements: tuple[RankingOperationalMeasurement, ...] = ()
    limitations: tuple[str, ...] = (
        "Incomplete ground truth on the 10-query lexical benchmark.",
        "Observed facts are artifact-derived; hypotheses are not causal proof.",
    )


__all__ = [
    "RANKING_FAILURE_ANALYSIS_FILENAME",
    "RANKING_FAILURE_ANALYSIS_VERSION",
    "RankingFailureAnalysisReport",
    "RankingFailureCategory",
    "RankingFailureRecord",
    "RankingOperationalMeasurement",
]
