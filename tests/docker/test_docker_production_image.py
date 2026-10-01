"""Docker production image contract tests (Phase 15A)."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def test_dockerfile_uses_python_313_slim() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.13" in content


def test_dockerfile_prefers_cpu_torch_before_project_install() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "download.pytorch.org/whl/cpu" in content


def test_dockerfile_installs_project_without_dev_extras() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "pip install --no-cache-dir ." in content
    assert "[dev]" not in content


def test_dockerfile_uvicorn_factory_entrypoint() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "productiq.api.app:create_app" in content
    assert "--factory" in content
    assert "0.0.0.0" in content
    assert "8000" in content


def test_dockerfile_healthcheck_uses_liveness_not_ready() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert "/api/v1/health" in content
    assert "/ready" not in content


def test_dockerfile_runs_as_non_root() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8")
    assert re.search(r"USER\s+productiq", content)


def test_dockerfile_has_no_secrets_or_windows_paths() -> None:
    content = (REPO_ROOT / "Dockerfile").read_text(encoding="utf-8").lower()
    assert "password=" not in content
    assert "api_key" not in content
    assert "e:\\" not in content
    assert "c:\\users" not in content


def test_dockerignore_excludes_large_artifacts_and_secrets() -> None:
    content = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "resources/processed" in content
    assert ".env" in content
    assert "tests" in content
    assert "notebooks" in content


def test_dockerignore_keeps_source_packaging_files() -> None:
    dockerignore = (REPO_ROOT / ".dockerignore").read_text(encoding="utf-8")
    assert "src" not in dockerignore.split()
    assert "pyproject.toml" not in dockerignore.split()
