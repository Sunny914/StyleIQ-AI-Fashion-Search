"""Explicit failure-mode helpers for Phase 12 evaluation hardening (12.11)."""

from __future__ import annotations

from pathlib import Path

from productiq.exceptions.base import RetrievalError
from productiq.retrieval.evaluation.search_evaluation.reporting.reproducibility import (
    LTR_REFERENCE_ARTIFACT_PATH,
)

FORBIDDEN_EVALUATIVE_FIELD_NAMES: frozenset[str] = frozenset(
    {
        "winner",
        "best",
        "recommended",
        "preferred",
        "promote",
        "promotion",
    }
)


def ltr_artifact_status(repo_root: Path) -> tuple[bool, str]:
    path = Path(repo_root) / LTR_REFERENCE_ARTIFACT_PATH
    if path.is_dir():
        return True, f"LTR artifact present at {LTR_REFERENCE_ARTIFACT_PATH}"
    return False, (
        f"LTR artifact absent at {LTR_REFERENCE_ARTIFACT_PATH}; "
        "ranking LTR reproducibility requires retraining or explicit artifact supply"
    )


def assert_no_hidden_ltr_fallback(repo_root: Path) -> None:
    reference = Path(repo_root) / LTR_REFERENCE_ARTIFACT_PATH
    experimental = Path(repo_root) / "resources" / "processed" / "experimental_ltr_ranker"
    if experimental.is_dir() and not reference.is_dir():
        msg = (
            "experimental_ltr_ranker exists but canonical reference LTR path is absent; "
            "hardening does not silently substitute fallback models"
        )
        raise RetrievalError(msg)


__all__ = [
    "FORBIDDEN_EVALUATIVE_FIELD_NAMES",
    "assert_no_hidden_ltr_fallback",
    "ltr_artifact_status",
]
