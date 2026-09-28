"""Retrieval failure-analysis contracts (Phase 4.17)."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from productiq.retrieval.evaluation.schema import DEFAULT_EVALUATION_K_VALUES

RETRIEVAL_FAILURE_ANALYSIS_VERSION = "1.0.0"
RETRIEVAL_FAILURE_ANALYSIS_FILENAME = "retrieval_failure_analysis_v1.json"
RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME = "retrieval_failure_analysis_v1.jsonl"
RETRIEVAL_FAILURE_SUMMARY_FILENAME = "retrieval_failure_summary_v1.json"

RELEVANCE_JUDGMENT_JUDGED_RELEVANT = "judged_relevant"
RELEVANCE_JUDGMENT_UNJUDGED = "unjudged"

REPRESENTATION_EVIDENCE_FIELD_NAMES: tuple[str, ...] = (
    "brand",
    "category_gender",
    "product_type",
    "color",
    "pattern",
    "material",
    "fit",
    "sleeve",
    "neckline",
    "product_features",
    "style_attributes",
    "description",
    "lexical_text",
    "semantic_text",
)


class Bm25ObservedClassification(StrEnum):
    NOT_RETRIEVED_BY_BM25 = "NOT_RETRIEVED_BY_BM25"
    RETRIEVED_BY_BM25 = "RETRIEVED_BY_BM25"


class SemanticObservedClassification(StrEnum):
    NOT_RETRIEVED_BY_SEMANTIC = "NOT_RETRIEVED_BY_SEMANTIC"
    RETRIEVED_BY_SEMANTIC = "RETRIEVED_BY_SEMANTIC"


class RetrievalPatternClassification(StrEnum):
    RETRIEVED_BY_BOTH = "RETRIEVED_BY_BOTH"
    BM25_ONLY = "BM25_ONLY"
    SEMANTIC_ONLY = "SEMANTIC_ONLY"
    NOT_RETRIEVED_BY_EITHER = "NOT_RETRIEVED_BY_EITHER"
    RETRIEVED_BUT_RRF_LOW_RANK = "RETRIEVED_BUT_RRF_LOW_RANK"
    DEPTH_LIMITED = "DEPTH_LIMITED"


class RetrievalDepthSnapshot(BaseModel):
    """Whether a judged relevant product appears within each evaluation depth."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    at_1: bool
    at_5: bool
    at_10: bool
    at_20: bool
    at_50: bool


class MethodRetrievalSnapshot(BaseModel):
    """Observed retrieval outcome for one method at configured top_k."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieved: bool
    rank: int | None = Field(
        default=None,
        ge=1,
        description="1-based rank in the method's retrieved list; None when not retrieved.",
    )
    native_score: float | None = Field(
        default=None,
        description="Native BM25 score or vector similarity when recorded in source artifacts.",
    )
    depth: RetrievalDepthSnapshot


class RrfRetrievalSnapshot(BaseModel):
    """Observed RRF fused-list outcome (from Phase 4.16 benchmark run artifact)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    retrieved: bool
    rank: int | None = Field(default=None, ge=1)
    fusion_score: float | None = Field(
        default=None,
        description="RRF score computed from source ranks and recorded rank_constant.",
    )
    bm25_rank: int | None = Field(default=None, ge=1)
    vector_rank: int | None = Field(default=None, ge=1)
    bm25_native_score: float | None = None
    vector_native_score: float | None = None
    depth: RetrievalDepthSnapshot


class ProductRepresentationEvidence(BaseModel):
    """Catalog representation fields for representation-review diagnostics (no inference)."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    product_id: str
    catalog_row_present: bool
    fields: dict[str, Any] = Field(default_factory=dict)


class QueryProductDiagnosticRecord(BaseModel):
    """One judged relevant product under one benchmark query."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    query_id: str
    query_text: str
    query_category: str
    product_id: str
    relevance_judgment: str = Field(
        description="judged_relevant for benchmark ground truth; unjudged is not used for judged rows."
    )
    retrieval_top_k: int = Field(gt=0)
    bm25: MethodRetrievalSnapshot
    semantic: MethodRetrievalSnapshot
    rrf: RrfRetrievalSnapshot
    bm25_observed_classification: Bm25ObservedClassification
    semantic_observed_classification: SemanticObservedClassification
    retrieval_pattern_classifications: tuple[RetrievalPatternClassification, ...]
    observations: tuple[str, ...]
    interpretive_diagnostics: tuple[str, ...]
    representation_evidence: ProductRepresentationEvidence | None = None
    representation_review_candidate: bool = False


class FailureAnalysisLineage(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    analysis_version: str = RETRIEVAL_FAILURE_ANALYSIS_VERSION
    lexical_benchmark_name: str
    lexical_benchmark_version: str
    lexical_run_artifact: str
    lexical_index_mode: str | None = None
    semantic_run_artifact: str
    semantic_analysis_artifact: str
    hybrid_rrf_run_artifact: str
    rrf_bm25_index_mode: str | None = None
    rrf_rank_constant: int = Field(gt=0)
    retrieval_top_k: int = Field(gt=0)
    k_values: tuple[int, ...] = DEFAULT_EVALUATION_K_VALUES
    incomplete_judgment_warning: str
    rrf_scoped_bm25_limitation: str | None = None
    bm25_native_score_limitation: str | None = None


class RetrievalFailureAnalysisReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    productiq_version: str
    lineage: FailureAnalysisLineage
    query_count: int = Field(ge=0)
    judged_relevant_product_count: int = Field(ge=0)
    diagnostics: tuple[QueryProductDiagnosticRecord, ...]


class CategoryAggregationRow(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    query_category: str
    query_count: int = Field(ge=0)
    judged_relevant_product_count: int = Field(ge=0)
    retrieval_pattern_counts: dict[str, int]
    bm25_not_retrieved_count: int = Field(ge=0)
    semantic_not_retrieved_count: int = Field(ge=0)
    rrf_not_retrieved_count: int = Field(ge=0)
    depth_limited_count: int = Field(ge=0)
    representation_review_candidate_count: int = Field(ge=0)


class RetrievalFailureSummaryReport(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    productiq_version: str
    analysis_version: str = RETRIEVAL_FAILURE_ANALYSIS_VERSION
    lineage: FailureAnalysisLineage
    query_count: int
    judged_relevant_product_count: int
    retrieval_pattern_counts: dict[str, int]
    bm25_observed_classification_counts: dict[str, int]
    semantic_observed_classification_counts: dict[str, int]
    depth_limited_count: int
    representation_review_candidate_count: int
    by_query_category: tuple[CategoryAggregationRow, ...]
    limitations: tuple[str, ...]


__all__ = [
    "RELEVANCE_JUDGMENT_JUDGED_RELEVANT",
    "RELEVANCE_JUDGMENT_UNJUDGED",
    "REPRESENTATION_EVIDENCE_FIELD_NAMES",
    "RETRIEVAL_FAILURE_ANALYSIS_FILENAME",
    "RETRIEVAL_FAILURE_ANALYSIS_JSONL_FILENAME",
    "RETRIEVAL_FAILURE_ANALYSIS_VERSION",
    "RETRIEVAL_FAILURE_SUMMARY_FILENAME",
    "Bm25ObservedClassification",
    "CategoryAggregationRow",
    "FailureAnalysisLineage",
    "MethodRetrievalSnapshot",
    "ProductRepresentationEvidence",
    "QueryProductDiagnosticRecord",
    "RetrievalDepthSnapshot",
    "RetrievalFailureAnalysisReport",
    "RetrievalFailureSummaryReport",
    "RetrievalPatternClassification",
    "RrfRetrievalSnapshot",
    "SemanticObservedClassification",
]
