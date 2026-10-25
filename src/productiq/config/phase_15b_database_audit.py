"""Phase 15B PostgreSQL/pgvector Compose audit artifact builder."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_VERSION = "1.0.0"


def build_phase_15b_audit_document(
    *,
    compose_config_ok: bool | None,
    compose_config_error: str | None,
    postgres_healthy: bool | None,
    bootstrap_ok: bool | None,
    bootstrap_error: str | None,
    contract_checks: dict[str, Any] | None,
    api_health_ok: bool | None,
    api_ready_ok: bool | None,
    database_hostname_is_postgres: bool | None,
    pytest_passed: int,
    pytest_failed: int,
    pytest_skipped: int,
) -> dict[str, Any]:
    checks: dict[str, str] = {
        "compose_file_present": "PASS",
        "compose_contract_tests": "PASS" if pytest_failed == 0 else "FAIL",
        "pytest_gate": "PASS" if pytest_failed == 0 else "FAIL",
    }
    for key, val in (
        ("compose_config_valid", compose_config_ok),
        ("postgres_health", postgres_healthy),
        ("schema_bootstrap", bootstrap_ok),
        ("api_health", api_health_ok),
        ("api_ready", api_ready_ok),
        ("compose_database_hostname", database_hostname_is_postgres),
    ):
        if val is True:
            checks[key] = "PASS"
        elif val is False:
            checks[key] = "FAIL"
        else:
            checks[key] = "NOT_RUN"

    contract_status = "NOT_RUN"
    if contract_checks:
        required = (
            contract_checks.get("vector_extension_installed"),
            contract_checks.get("products_table_exists"),
            contract_checks.get("embedding_column_exists"),
            contract_checks.get("embedding_type_is_vector"),
            contract_checks.get("hnsw_index_exists"),
            contract_checks.get("hnsw_cosine_opclass"),
        )
        if all(required):
            contract_status = "PASS"
        else:
            contract_status = "FAIL"
    checks["pgvector_schema_contract"] = contract_status

    blocking = [k for k, v in checks.items() if v == "FAIL"]
    if blocking:
        status = "BLOCKED"
    elif checks.get("postgres_health") != "PASS" or checks.get("schema_bootstrap") != "PASS":
        status = "INCOMPLETE"
    elif all(v == "PASS" for v in checks.values() if v != "NOT_RUN"):
        status = "COMPLETE"
    else:
        status = "INCOMPLETE"

    return {
        "audit_version": AUDIT_VERSION,
        "phase": "15B",
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "phase_15b_status": status,
        "checks": checks,
        "compose": {
            "file": "docker-compose.yml",
            "config_valid": compose_config_ok,
            "config_error": compose_config_error,
            "postgres_service": "postgres",
            "api_service": "productiq-api",
        },
        "database_contract": contract_checks or {},
        "bootstrap": {
            "module": "productiq.database.bootstrap_compose",
            "succeeded": bootstrap_ok,
            "error_summary": bootstrap_error,
        },
        "api_runtime": {
            "health_ok": api_health_ok,
            "ready_ok": api_ready_ok,
        },
        "tests": {
            "command": "pytest tests/docker/test_phase_15b_compose_contract.py -q",
            "passed": pytest_passed,
            "failed": pytest_failed,
            "skipped": pytest_skipped,
        },
        "deferred_15c": ["Full stack integration audit with production-like artifact wiring"],
    }


def write_phase_15b_audit_artifacts(
    document: dict[str, Any],
    *,
    root: Path | None = None,
) -> tuple[Path, Path]:
    benchmark = root or Path("resources/benchmark")
    benchmark.mkdir(parents=True, exist_ok=True)
    json_path = benchmark / "phase_15b_database_audit.json"
    md_path = benchmark / "phase_15b_database_audit.md"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 15B — PostgreSQL/pgvector audit",
        "",
        f"- status: **{document['phase_15b_status']}**",
        f"- generated_at_utc: `{document['generated_at_utc']}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|-------|--------|",
    ]
    for key, value in document["checks"].items():
        lines.append(f"| {key} | {value} |")
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


__all__ = ["build_phase_15b_audit_document", "write_phase_15b_audit_artifacts"]
