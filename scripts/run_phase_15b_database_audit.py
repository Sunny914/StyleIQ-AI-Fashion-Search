#!/usr/bin/env python3
"""Generate Phase 15B PostgreSQL/pgvector Compose audit artifacts."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def _run_pytest(repo: Path) -> tuple[int, int, int]:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        "tests/docker/test_phase_15b_compose_contract.py",
    ]
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


def _compose_config(repo: Path) -> tuple[bool | None, str | None]:
    result = subprocess.run(
        ["docker", "compose", "config"],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout)[-2000:].strip()
    return True, None


def _wait_postgres_healthy(repo: Path, *, timeout_seconds: float = 120.0) -> bool:
    deadline = time.time() + timeout_seconds
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "ps", "--format", "json"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and "healthy" in result.stdout.lower():
            return True
        time.sleep(3.0)
    return False


def _run_bootstrap(repo: Path) -> tuple[bool | None, str | None, dict | None]:
    result = subprocess.run(
        [
            "docker",
            "compose",
            "run",
            "--rm",
            "productiq-api",
            "python",
            "-m",
            "productiq.database.bootstrap_compose",
            "--load-demo-fixture",
            "--json",
        ],
        cwd=repo,
        capture_output=True,
        text=True,
        check=False,
        env=None,
    )
    if result.returncode != 0:
        return False, (result.stderr or result.stdout)[-2000:].strip(), None
    try:
        report = json.loads(result.stdout)
    except json.JSONDecodeError:
        return False, "bootstrap did not emit valid JSON", None
    return True, None, report


def _probe(url: str) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            return 200 <= response.status < 300
    except (urllib.error.URLError, TimeoutError):
        return False


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--skip-docker",
        action="store_true",
        help="Skip live Compose/Docker validation",
    )
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]

    from productiq.config.phase_15b_database_audit import (
        build_phase_15b_audit_document,
        write_phase_15b_audit_artifacts,
    )

    passed, failed, skipped = _run_pytest(repo)

    compose_ok: bool | None = None
    compose_err: str | None = None
    postgres_ok: bool | None = None
    bootstrap_ok: bool | None = None
    bootstrap_err: str | None = None
    contract: dict | None = None
    health_ok: bool | None = None
    ready_ok: bool | None = None
    hostname_ok: bool | None = None

    compose_text = (repo / "docker-compose.yml").read_text(encoding="utf-8")
    hostname_ok = "@postgres:" in compose_text and "${DATABASE_URL" in compose_text

    if not args.skip_docker:
        try:
            compose_ok, compose_err = _compose_config(repo)
            if compose_ok:
                subprocess.run(["docker", "compose", "up", "-d", "postgres"], cwd=repo, check=False)
                postgres_ok = _wait_postgres_healthy(repo)
                if postgres_ok:
                    bootstrap_ok, bootstrap_err, contract = _run_bootstrap(repo)
                subprocess.run(["docker", "compose", "up", "-d"], cwd=repo, check=False)
                time.sleep(15.0)
                health_ok = _probe("http://127.0.0.1:8000/api/v1/health")
                ready_ok = _probe("http://127.0.0.1:8000/api/v1/ready")
        except FileNotFoundError:
            compose_ok = False
            compose_err = "docker CLI not found"

    doc = build_phase_15b_audit_document(
        compose_config_ok=compose_ok,
        compose_config_error=compose_err,
        postgres_healthy=postgres_ok,
        bootstrap_ok=bootstrap_ok,
        bootstrap_error=bootstrap_err,
        contract_checks=contract,
        api_health_ok=health_ok,
        api_ready_ok=ready_ok,
        database_hostname_is_postgres=hostname_ok,
        pytest_passed=passed,
        pytest_failed=failed,
        pytest_skipped=skipped,
    )
    json_path, md_path = write_phase_15b_audit_artifacts(doc)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status: {doc['phase_15b_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
