"""Search evaluation reporting and reproducibility (Phase 12.10)."""

from __future__ import annotations

from pathlib import Path

from productiq.retrieval.evaluation.search_evaluation.reporting.report_artifact import (
    build_search_evaluation_report_artifact_dict,
    validate_search_evaluation_report_artifact,
    write_search_evaluation_report_artifact,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_builder import (
    build_search_evaluation_report_from_repo,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_renderer import (
    render_search_evaluation_report_markdown,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_FILENAME,
    SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME,
    SearchEvaluationReport,
)

REPORT_MARKDOWN_DIR = "resources/evaluation/reports"


def run_search_evaluation_report(repo_root: Path) -> SearchEvaluationReport:
    return build_search_evaluation_report_from_repo(repo_root)


def run_default_search_evaluation_report(repo_root: Path) -> SearchEvaluationReport:
    root = Path(repo_root)
    report = run_search_evaluation_report(root)
    eval_dir = root / "resources" / "evaluation"
    json_path = eval_dir / SEARCH_EVALUATION_REPORT_FILENAME
    write_search_evaluation_report_artifact(
        json_path,
        build_search_evaluation_report_artifact_dict(report),
    )
    md_dir = root / REPORT_MARKDOWN_DIR
    md_dir.mkdir(parents=True, exist_ok=True)
    md_path = md_dir / SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME
    md_path.write_text(render_search_evaluation_report_markdown(report), encoding="utf-8")
    return report


__all__ = [
    "REPORT_MARKDOWN_DIR",
    "render_search_evaluation_report_markdown",
    "run_default_search_evaluation_report",
    "run_search_evaluation_report",
    "validate_search_evaluation_report_artifact",
]
