"""Standalone import smoke tests (avoid pytest conftest bootstrap side effects)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def _run_clean_import_snippet(snippet: str) -> subprocess.CompletedProcess[str]:
    root = Path(__file__).resolve().parents[2]
    env = os.environ.copy()
    env["PYTHONPATH"] = str(root / "src")
    return subprocess.run(
        [sys.executable, "-c", snippet],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_embedding_encoder_imports_without_package_eager_init() -> None:
    result = _run_clean_import_snippet(
        "from productiq.retrieval.embedding_encoder import create_bge_small_en_v15_encoder; "
        "print('IMPORT_OK')"
    )
    assert result.returncode == 0, result.stderr
    assert "IMPORT_OK" in result.stdout


def test_retrieval_public_api_still_resolves_lazily() -> None:
    result = _run_clean_import_snippet(
        "from productiq.retrieval import SemanticVector, cosine_similarity; "
        "assert cosine_similarity("
        "SemanticVector(values=(1.0, 0.0)), SemanticVector(values=(1.0, 0.0))"
        ") == 1.0"
    )
    assert result.returncode == 0, result.stderr
