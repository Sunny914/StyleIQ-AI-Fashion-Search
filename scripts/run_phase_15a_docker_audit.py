#!/usr/bin/env python3
"""Generate Phase 15A Docker audit artifacts (build/run optional)."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _run_pytest(repo: Path) -> tuple[int, int, int]:
    cmd = [sys.executable, "-m", "pytest", "-q", "--ignore=tests/retrieval/integration"]
    result = subprocess.run(cmd, cwd=repo, capture_output=True, text=True, check=False)
    combined = result.stdout + result.stderr
    passed = failed = skipped = 0
    match = re.search(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?", combined)
    if match:
        passed = int(match.group(1))
        if match.group(2):
            failed = int(match.group(2))
        if match.group(3):
            skipped = int(match.group(3))
    return passed, failed, skipped


def _run_ruff(repo: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _run_mypy(repo: Path) -> bool:
    result = subprocess.run(
        [sys.executable, "-m", "mypy", "src/productiq"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _try_docker_build(repo: Path) -> tuple[bool | None, str | None, str | None]:
    result = subprocess.run(
        ["docker", "build", "-t", "productiq-api:local", "."],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        err = (result.stderr or result.stdout)[-2000:]
        return False, err.strip(), None
    size_result = subprocess.run(
        ["docker", "images", "productiq-api:local", "--format", "{{.Size}}"],
        capture_output=True,
        text=True,
        check=False,
    )
    size = size_result.stdout.strip() or None
    return True, None, size


def _try_container_smoke(
    repo: Path,
) -> tuple[bool | None, bool | None, bool | None, bool | None]:
    """Run detached container and probe health, ready, and OpenAPI."""
    import time
    import urllib.error
    import urllib.request

    container_name = "productiq-15a-audit-smoke"
    subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)
    run_result = subprocess.run(
        [
            "docker",
            "run",
            "-d",
            "--name",
            container_name,
            "-p",
            "127.0.0.1:8000:8000",
            "-e",
            "APP_ENV=production",
            "productiq-api:local",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if run_result.returncode != 0:
        return False, None, None, None

    def _probe(url: str) -> bool:
        try:
            with urllib.request.urlopen(url, timeout=5) as response:
                return 200 <= response.status < 300
        except (urllib.error.URLError, TimeoutError):
            return False

    started = False
    health_ok: bool | None = None
    ready_ok: bool | None = None
    openapi_ok: bool | None = None
    try:
        deadline = time.time() + 90.0
        while time.time() < deadline:
            if _probe("http://127.0.0.1:8000/api/v1/health"):
                started = True
                break
            time.sleep(2.0)
        if started:
            health_ok = _probe("http://127.0.0.1:8000/api/v1/health")
            ready_ok = _probe("http://127.0.0.1:8000/api/v1/ready")
            openapi_ok = _probe("http://127.0.0.1:8000/api/v1/openapi.json")
        else:
            started = False
    finally:
        subprocess.run(["docker", "rm", "-f", container_name], capture_output=True, check=False)

    return started, health_ok, ready_ok, openapi_ok


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-docker", action="store_true")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]

    from productiq.config.phase_15a_docker_audit import (
        build_phase_15a_audit_document,
        write_phase_15a_audit_artifacts,
    )

    passed, failed, skipped = _run_pytest(repo)
    ruff_ok = _run_ruff(repo)
    mypy_ok = _run_mypy(repo)

    build_ok: bool | None = None
    build_err: str | None = None
    image_size: str | None = None
    start_ok: bool | None = None
    health_ok: bool | None = None
    ready_ok: bool | None = None
    openapi_ok: bool | None = None

    if not args.skip_docker:
        try:
            build_ok, build_err, image_size = _try_docker_build(repo)
        except FileNotFoundError:
            build_ok = None
            build_err = "docker CLI not found"
        if build_ok:
            start_ok, health_ok, ready_ok, openapi_ok = _try_container_smoke(repo)

    doc = build_phase_15a_audit_document(
        docker_build_ok=build_ok,
        docker_build_error=build_err,
        image_size=image_size,
        container_start_ok=start_ok,
        health_ok=health_ok,
        ready_ok=ready_ok,
        openapi_ok=openapi_ok,
        pytest_passed=passed,
        pytest_failed=failed,
        pytest_skipped=skipped,
        ruff_ok=ruff_ok,
        mypy_ok=mypy_ok,
    )
    json_path, md_path = write_phase_15a_audit_artifacts(doc)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status: {doc['phase_15a_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
