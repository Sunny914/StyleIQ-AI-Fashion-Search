"""Phase 12.11 search evaluation hardening."""

from __future__ import annotations

from productiq.retrieval.evaluation.search_evaluation.hardening.determinism import (
    DeterminismValidationResult,
    validate_persisted_report_markdown_matches_regeneration,
    validate_report_generation_determinism,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.failure_modes import (
    FORBIDDEN_EVALUATIVE_FIELD_NAMES,
    assert_no_hidden_ltr_fallback,
    ltr_artifact_status,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.validation import (
    SearchEvaluationHardeningAuditResult,
    run_search_evaluation_hardening_audit,
    validate_persisted_artifact_integrity,
    validate_search_evaluation_hardening_sources,
)

__all__ = [
    "FORBIDDEN_EVALUATIVE_FIELD_NAMES",
    "DeterminismValidationResult",
    "SearchEvaluationHardeningAuditResult",
    "assert_no_hidden_ltr_fallback",
    "ltr_artifact_status",
    "run_search_evaluation_hardening_audit",
    "validate_persisted_artifact_integrity",
    "validate_persisted_report_markdown_matches_regeneration",
    "validate_report_generation_determinism",
    "validate_search_evaluation_hardening_sources",
]
