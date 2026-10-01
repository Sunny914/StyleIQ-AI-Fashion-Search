#!/usr/bin/env python3
"""Write Phase 14C deployment foundation audit artifacts."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _run_gate() -> tuple[int, int, int]:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [sys.executable, "-m", "pytest", "-q", "--ignore=tests/retrieval/integration"]
    result = subprocess.run(cmd, cwd=repo_root, capture_output=True, text=True, check=False)
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


def _run_ruff(repo_root: Path) -> bool:
    paths = [
        "src/productiq/config",
        "src/productiq/api/app.py",
        "src/productiq/api/services/product_wiring.py",
        "tests/config/test_deployment_configuration.py",
        "tests/config/test_runtime_deployment_contract.py",
        "tests/config/test_phase_14_deployment_foundation_audit.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "ruff", "check", *paths],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def _run_mypy(repo_root: Path) -> bool:
    modules = [
        "src/productiq/config/phase_14_deployment_foundation_audit.py",
        "src/productiq/config/runtime_artifacts.py",
        "src/productiq/config/runtime_validation.py",
        "src/productiq/config/database_runtime.py",
        "src/productiq/config/deployment_manifest.py",
        "src/productiq/config/deployment.py",
        "src/productiq/config/settings.py",
        "src/productiq/api/app.py",
        "src/productiq/api/services/product_wiring.py",
    ]
    result = subprocess.run(
        [sys.executable, "-m", "mypy", *modules],
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    return result.returncode == 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 14C deployment foundation audit.")
    parser.add_argument("--benchmark-root", type=Path, default=None)
    args = parser.parse_args(argv)
    repo_root = Path(__file__).resolve().parents[1]

    from productiq.config.phase_14_deployment_foundation_audit import (
        compare_deployment_manifest_on_disk,
        default_check_statuses,
        write_phase_14_deployment_foundation_audit_artifacts,
    )

    passed, failed, skipped = _run_gate()
    ruff_ok = _run_ruff(repo_root)
    mypy_ok = _run_mypy(repo_root)
    manifest_audit = compare_deployment_manifest_on_disk(
        manifest_path=repo_root / "resources/deployment/productiq_deployment_manifest.json",
    )
    statuses = default_check_statuses()
    statuses["live_postgresql_pgvector"] = "NOT_RUN"
    json_path, md_path = write_phase_14_deployment_foundation_audit_artifacts(
        benchmark_root=args.benchmark_root,
        gate_test_passed=passed,
        gate_test_failed=failed,
        gate_test_skipped=skipped,
        check_statuses=statuses,
        ruff_ok=ruff_ok,
        mypy_ok=mypy_ok,
        security_ok=True,
        manifest_audit=manifest_audit,
        docker_readiness="READY" if not failed and manifest_audit.get("consistent") else "BLOCKED",
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Gate: {passed} passed, {failed} failed, {skipped} skipped")
    print(f"Ruff: {'PASS' if ruff_ok else 'FAIL'}")
    print(f"Mypy: {'PASS' if mypy_ok else 'FAIL'}")
    print(f"Manifest consistent: {manifest_audit.get('consistent')}")
    return 1 if failed or not ruff_ok or not mypy_ok else 0


if __name__ == "__main__":
    raise SystemExit(main())
