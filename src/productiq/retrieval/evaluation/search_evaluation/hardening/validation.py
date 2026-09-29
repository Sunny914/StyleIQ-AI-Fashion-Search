"""Orchestrate Phase 12 evaluation hardening validation (12.11)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation.baseline_schema import (
    SEARCH_BASELINE_BM25_RUN_FILENAME,
    SEARCH_BASELINE_RRF_RUN_FILENAME,
    SEARCH_BASELINE_SEMANTIC_RUN_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_artifact_schema import (
    SEARCH_BENCHMARK_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.benchmark_loader import (
    load_search_evaluation_benchmark,
)
from productiq.retrieval.evaluation.search_evaluation.experiment_schema import (
    SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME,
    SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
)
from productiq.retrieval.evaluation.search_evaluation.failure_analysis_schema import (
    SEARCH_FAILURE_ANALYSIS_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.determinism import (
    DeterminismValidationResult,
    validate_persisted_report_markdown_matches_regeneration,
    validate_report_generation_determinism,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.failure_modes import (
    assert_no_hidden_ltr_fallback,
    ltr_artifact_status,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.integrity import (
    load_json_object,
    validate_baseline_artifact_file,
    validate_evaluation_report_artifact_file,
    validate_failure_analysis_artifact_file,
    validate_ranking_experiment_artifact_file,
    validate_statistical_analysis_artifact_file,
    verify_declared_checksum,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.invariants import (
    validate_cross_artifact_invariants,
)
from productiq.retrieval.evaluation.search_evaluation.hardening.provenance import (
    validate_provenance_consistency,
    validate_variant_identity_uniqueness,
)
from productiq.retrieval.evaluation.search_evaluation.ranking_experiment_schema import (
    SEARCH_RANKING_EXPERIMENT_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_loader import (
    SearchEvaluationReportSources,
    load_search_evaluation_report_sources,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_FILENAME,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_validation import (
    validate_search_evaluation_report,
)
from productiq.retrieval.evaluation.search_evaluation.statistical_schema import (
    SEARCH_STATISTICAL_ANALYSIS_FILENAME,
)


@dataclass(frozen=True)
class SearchEvaluationHardeningAuditResult:
    passed: bool
    checks_passed: tuple[str, ...]
    limitations: tuple[str, ...]
    determinism: DeterminismValidationResult | None = None


def _require_schema_version(payload: dict[str, object], expected: str, label: str) -> None:
    from productiq.exceptions.base import RetrievalError

    actual = payload.get("artifact_schema_version")
    if actual != expected:
        msg = f"{label} artifact_schema_version {actual!r} != expected {expected!r}"
        raise RetrievalError(msg)


def _validate_optional_checksum_artifact(path: Path, *, schema_version: str, label: str) -> None:
    if not path.is_file():
        return
    payload = load_json_object(path)
    _require_schema_version(payload, schema_version, label)
    verify_declared_checksum(payload, label=str(path.name))


def validate_persisted_artifact_integrity(repo_root: Path) -> None:
    root = Path(repo_root)
    eval_dir = root / "resources" / "evaluation"
    load_search_evaluation_benchmark(eval_dir / SEARCH_BENCHMARK_FILENAME)
    validate_baseline_artifact_file(eval_dir / SEARCH_BASELINE_BM25_RUN_FILENAME)
    validate_baseline_artifact_file(eval_dir / SEARCH_BASELINE_SEMANTIC_RUN_FILENAME)
    validate_baseline_artifact_file(eval_dir / SEARCH_BASELINE_RRF_RUN_FILENAME)

    experiment_path = eval_dir / SEARCH_BASELINE_COMPARISON_EXPERIMENT_FILENAME
    _validate_optional_checksum_artifact(
        experiment_path,
        schema_version=SEARCH_EXPERIMENT_ARTIFACT_SCHEMA_VERSION,
        label="12.6 experiment",
    )
    ranking_path = eval_dir / SEARCH_RANKING_EXPERIMENT_FILENAME
    if ranking_path.is_file():
        validate_ranking_experiment_artifact_file(ranking_path)
    failure_path = eval_dir / SEARCH_FAILURE_ANALYSIS_FILENAME
    if failure_path.is_file():
        validate_failure_analysis_artifact_file(failure_path)
    statistical_path = eval_dir / SEARCH_STATISTICAL_ANALYSIS_FILENAME
    if statistical_path.is_file():
        validate_statistical_analysis_artifact_file(statistical_path)
    report_path = eval_dir / SEARCH_EVALUATION_REPORT_FILENAME
    if report_path.is_file():
        validate_evaluation_report_artifact_file(report_path)


def validate_search_evaluation_hardening_sources(sources: SearchEvaluationReportSources) -> None:
    validate_cross_artifact_invariants(sources)
    validate_provenance_consistency(sources)
    validate_variant_identity_uniqueness(sources)


def run_search_evaluation_hardening_audit(
    repo_root: Path,
    *,
    include_determinism: bool = True,
    determinism_repetitions: int = 5,
) -> SearchEvaluationHardeningAuditResult:
    root = Path(repo_root)
    checks: list[str] = []
    validate_persisted_artifact_integrity(root)
    checks.append("persisted_artifact_integrity")
    sources = load_search_evaluation_report_sources(root)
    validate_search_evaluation_hardening_sources(sources)
    checks.append("cross_artifact_invariants")
    checks.append("provenance_consistency")
    from productiq.retrieval.evaluation.search_evaluation.reporting.report_builder import (
        build_search_evaluation_report,
    )

    report = build_search_evaluation_report(sources)
    validate_search_evaluation_report(report)
    checks.append("report_safety_contract")
    assert_no_hidden_ltr_fallback(root)
    checks.append("no_hidden_ltr_fallback")
    _present, ltr_note = ltr_artifact_status(root)
    limitations = [ltr_note]
    determinism_result: DeterminismValidationResult | None = None
    if include_determinism:
        determinism_result = validate_report_generation_determinism(
            root,
            repetitions=determinism_repetitions,
        )
        checks.append("determinism_regeneration")
        validate_persisted_report_markdown_matches_regeneration(root)
        checks.append("persisted_markdown_matches_regeneration")
    return SearchEvaluationHardeningAuditResult(
        passed=True,
        checks_passed=tuple(checks),
        limitations=tuple(limitations),
        determinism=determinism_result,
    )


__all__ = [
    "SearchEvaluationHardeningAuditResult",
    "run_search_evaluation_hardening_audit",
    "validate_persisted_artifact_integrity",
    "validate_search_evaluation_hardening_sources",
]
