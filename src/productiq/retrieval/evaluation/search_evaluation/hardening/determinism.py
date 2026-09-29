"""Determinism validation for Phase 12 evaluation hardening (12.11)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.reporting.report_artifact import (
    build_search_evaluation_report_artifact_dict,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_builder import (
    build_search_evaluation_report_from_repo,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_renderer import (
    render_search_evaluation_report_markdown,
)
from productiq.retrieval.evaluation.search_evaluation.reporting.report_schema import (
    SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME,
)

_REPORT_MARKDOWN_DIR = "resources/evaluation/reports"


@dataclass(frozen=True)
class DeterminismValidationResult:
    repetitions: int
    checksum: str
    json_stable: bool
    markdown_stable: bool


def validate_report_generation_determinism(
    repo_root: Path,
    *,
    repetitions: int = 5,
) -> DeterminismValidationResult:
    if repetitions < 1:
        msg = "repetitions must be positive"
        raise RetrievalError(msg)
    checksums: list[str] = []
    json_bodies: list[str] = []
    markdown_bodies: list[str] = []
    for _ in range(repetitions):
        report = build_search_evaluation_report_from_repo(repo_root)
        payload = build_search_evaluation_report_artifact_dict(report)
        checksum = payload.get("deterministic_checksum_sha256")
        if not isinstance(checksum, str):
            msg = "report artifact missing deterministic checksum during determinism validation"
            raise RetrievalError(msg)
        checksums.append(checksum)
        body = {
            key: value for key, value in payload.items() if key != "deterministic_checksum_sha256"
        }
        json_bodies.append(json.dumps(body, sort_keys=True))
        markdown_bodies.append(render_search_evaluation_report_markdown(report))
    if len(set(checksums)) != 1:
        msg = "report checksum differed across deterministic regeneration repetitions"
        raise RetrievalError(msg)
    if len(set(json_bodies)) != 1:
        msg = "report JSON body differed across deterministic regeneration repetitions"
        raise RetrievalError(msg)
    if len(set(markdown_bodies)) != 1:
        msg = "report Markdown differed across deterministic regeneration repetitions"
        raise RetrievalError(msg)
    return DeterminismValidationResult(
        repetitions=repetitions,
        checksum=checksums[0],
        json_stable=True,
        markdown_stable=True,
    )


def validate_persisted_report_markdown_matches_regeneration(repo_root: Path) -> None:
    root = Path(repo_root)
    md_path = root / _REPORT_MARKDOWN_DIR / SEARCH_EVALUATION_REPORT_MARKDOWN_FILENAME
    if not md_path.is_file():
        return
    report = build_search_evaluation_report_from_repo(root)
    expected = render_search_evaluation_report_markdown(report)
    actual = md_path.read_text(encoding="utf-8")
    if actual != expected:
        msg = "persisted Markdown report does not match regenerated report from current artifacts"
        raise RetrievalError(msg)


__all__ = [
    "DeterminismValidationResult",
    "validate_persisted_report_markdown_matches_regeneration",
    "validate_report_generation_determinism",
]
