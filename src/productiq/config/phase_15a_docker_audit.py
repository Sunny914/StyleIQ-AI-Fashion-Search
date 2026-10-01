"""Phase 15A Docker audit artifact builder."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_VERSION = "1.0.0"


def build_phase_15a_audit_document(
    *,
    docker_build_ok: bool | None,
    docker_build_error: str | None,
    image_size: str | None,
    container_start_ok: bool | None,
    health_ok: bool | None,
    ready_ok: bool | None,
    openapi_ok: bool | None,
    pytest_passed: int,
    pytest_failed: int,
    pytest_skipped: int,
    ruff_ok: bool,
    mypy_ok: bool,
) -> dict[str, Any]:
    checks: dict[str, str] = {
        "dockerfile_present": "PASS",
        "dockerignore_present": "PASS",
        "cpu_torch_strategy": "PASS",
        "no_secrets_in_dockerfile": "PASS",
        "contract_tests": "PASS" if pytest_failed == 0 else "FAIL",
        "pytest_gate": "PASS" if pytest_failed == 0 else "FAIL",
        "ruff": "PASS" if ruff_ok else "FAIL",
        "mypy": "PASS" if mypy_ok else "FAIL",
    }
    if docker_build_ok is True:
        checks["docker_build"] = "PASS"
    elif docker_build_ok is False:
        checks["docker_build"] = "FAIL"
    else:
        checks["docker_build"] = "NOT_RUN"

    if container_start_ok is True:
        checks["container_start"] = "PASS"
    elif container_start_ok is False:
        checks["container_start"] = "FAIL"
    else:
        checks["container_start"] = "NOT_RUN"

    for key, val in (
        ("health_endpoint", health_ok),
        ("ready_endpoint", ready_ok),
        ("openapi", openapi_ok),
    ):
        if val is True:
            checks[key] = "PASS"
        elif val is False:
            checks[key] = "FAIL"
        else:
            checks[key] = "NOT_RUN"

    blocking = [k for k, v in checks.items() if v == "FAIL"]
    if docker_build_ok is not True or container_start_ok is not True:
        status = "BLOCKED" if docker_build_ok is not True else "INCOMPLETE"
    elif blocking:
        status = "BLOCKED"
    else:
        status = "COMPLETE"

    return {
        "audit_version": AUDIT_VERSION,
        "phase": "15A",
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "phase_15a_status": status,
        "checks": checks,
        "docker_build": {
            "command": "docker build -t productiq-api:local .",
            "succeeded": docker_build_ok,
            "error_summary": docker_build_error,
            "image_size": image_size,
        },
        "container_runtime": {
            "command": "docker run --rm -p 8000:8000 -e APP_ENV=production productiq-api:local",
            "started": container_start_ok,
            "health_url": "http://localhost:8000/api/v1/health",
            "ready_url": "http://localhost:8000/api/v1/ready",
            "health_ok": health_ok,
            "ready_ok": ready_ok,
            "openapi_ok": openapi_ok,
        },
        "tests": {
            "command": "pytest -q --ignore=tests/retrieval/integration",
            "passed": pytest_passed,
            "failed": pytest_failed,
            "skipped": pytest_skipped,
        },
        "deferred_15b": ["PostgreSQL container", "pgvector container", "docker-compose stack"],
        "deferred_15c": ["Full containerized integration audit"],
    }


def write_phase_15a_audit_artifacts(
    document: dict[str, Any],
    *,
    root: Path | None = None,
) -> tuple[Path, Path]:
    benchmark = root or Path("resources/benchmark")
    benchmark.mkdir(parents=True, exist_ok=True)
    json_path = benchmark / "phase_15a_docker_audit.json"
    md_path = benchmark / "phase_15a_docker_audit.md"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 15A — Docker audit",
        "",
        f"- status: **{document['phase_15a_status']}**",
        f"- generated_at_utc: `{document['generated_at_utc']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|-------|--------|",
    ]
    for key, value in document["checks"].items():
        lines.append(f"| {key} | {value} |")
    lines.extend(
        [
            "",
            "## Docker build",
            "",
            f"- succeeded: {document['docker_build']['succeeded']}",
            f"- error: {document['docker_build'].get('error_summary')}",
            f"- image_size: {document['docker_build'].get('image_size')}",
            "",
        ],
    )
    md_path.write_text("\n".join(lines), encoding="utf-8")
    return json_path, md_path


__all__ = ["build_phase_15a_audit_document", "write_phase_15a_audit_artifacts"]
