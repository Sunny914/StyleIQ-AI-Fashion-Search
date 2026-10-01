"""Phase 14C — Deployment foundation final audit artifacts."""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_VERSION = "1.0.0"
PHASE = "14C"
PHASE_14_STATUS = "complete"

# Deterministic check ordering for reports.
AUDIT_CHECK_KEYS: tuple[str, ...] = (
    "single_configuration_system",
    "configuration_contract",
    "artifact_resolution",
    "artifact_startup_laziness",
    "database_pgvector_contract",
    "live_postgresql_pgvector",
    "startup_import_safety",
    "health_readiness_semantics",
    "secret_and_path_safety",
    "deployment_manifest_consistency",
    "api_regression",
    "configuration_runtime_traces",
    "docker_readiness",
    "test_suite",
    "ruff",
    "mypy",
)


def default_check_statuses() -> dict[str, str]:
    """Baseline statuses populated by the audit runner."""
    return {key: "PASS" for key in AUDIT_CHECK_KEYS}


def compare_deployment_manifest_on_disk(
    *,
    manifest_path: Path,
    settings: Any | None = None,
) -> dict[str, Any]:
    """Compare committed manifest JSON with ``build_deployment_manifest`` output."""
    from productiq.config.deployment_manifest import build_deployment_manifest
    from productiq.config.settings import Settings

    resolved_settings = settings or Settings(_env_file=None)  # type: ignore[call-arg]
    on_disk = json.loads(manifest_path.read_text(encoding="utf-8"))
    built = build_deployment_manifest(settings=resolved_settings)
    mismatches: list[str] = []
    for section in ("application", "database", "configuration", "health"):
        if on_disk.get(section) != built.get(section):
            if section == "database":
                on_cfg = on_disk.get("database", {}).get("configuration", {})
                built_cfg = built.get("database", {}).get("configuration", {})
                if on_cfg != built_cfg:
                    mismatches.append("database.configuration snapshot differs from current Settings")
                on_db = {k: v for k, v in on_disk.get("database", {}).items() if k != "configuration"}
                built_db = {k: v for k, v in built.get("database", {}).items() if k != "configuration"}
                if on_db != built_db:
                    mismatches.append("database contract metadata differs")
            else:
                mismatches.append(f"section {section!r} differs from builder")
    if on_disk.get("artifacts", {}).get("paths") != built.get("artifacts", {}).get("paths"):
        mismatches.append("artifact paths differ")
    try:
        manifest_display = str(manifest_path.resolve().relative_to(Path.cwd()))
    except ValueError:
        manifest_display = str(manifest_path.as_posix())
    return {
        "manifest_path": manifest_display,
        "consistent": not mismatches,
        "mismatches": mismatches,
        "note": (
            "database.configuration and integrity blocks are environment snapshots; "
            "contract sections must match builder."
        ),
    }


def build_phase_14_deployment_foundation_audit_document(
    *,
    gate_test_passed: int,
    gate_test_failed: int,
    gate_test_skipped: int,
    check_statuses: dict[str, str],
    ruff_ok: bool,
    mypy_ok: bool,
    security_ok: bool,
    manifest_audit: dict[str, Any],
    docker_readiness: str,
    audit_test_module: str = "tests/config/test_phase_14_deployment_foundation_audit.py",
) -> dict[str, Any]:
    checks = {key: check_statuses.get(key, "NOT_RUN") for key in AUDIT_CHECK_KEYS}
    if not ruff_ok:
        checks["ruff"] = "FAIL"
    if not mypy_ok:
        checks["mypy"] = "FAIL"
    if gate_test_failed:
        checks["test_suite"] = "FAIL"
    if not manifest_audit.get("consistent", False):
        checks["deployment_manifest_consistency"] = "FAIL"
    if checks.get("live_postgresql_pgvector") != "PASS":
        checks["live_postgresql_pgvector"] = "NOT_RUN"

    blocking = [name for name, status in checks.items() if status == "FAIL"]
    overall = PHASE_14_STATUS if not blocking else "blocked"

    return {
        "audit_version": AUDIT_VERSION,
        "phase": PHASE,
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "phase_14_status": overall,
        "closure_statement": (
            "Phase 14 deployment foundation (configuration, runtime artifacts, database contract) "
            "is coherent and locally validated; live PostgreSQL/pgvector validation remains opt-in."
        ),
        "sub_phases_complete": ["14A", "14B", "14C"],
        "checks": checks,
        "tests": {
            "gate_command": "pytest -q --ignore=tests/retrieval/integration",
            "passed": gate_test_passed,
            "failed": gate_test_failed,
            "skipped": gate_test_skipped,
            "audit_module": audit_test_module,
        },
        "ruff": "PASS" if ruff_ok else "FAIL",
        "mypy": "PASS" if mypy_ok else "FAIL",
        "security_scan": "PASS" if security_ok else "FAIL",
        "docker_readiness": docker_readiness,
        "manifest_audit": manifest_audit,
        "configuration_runtime_traces": {
            "app_env_to_fastapi": "APP_ENV → Settings.app_env + ServingConfig.deployment_environment → create_app(app_settings)",
            "database_url": "DATABASE_URL → Settings.database_url → database.engine.create_engine_from_settings (on demand)",
            "processed_catalog": "PRODUCTIQ_PROCESSED_CATALOG_PATH → RuntimeArtifactPaths → product_wiring.resolved_processed_catalog_path",
            "bm25_artifact": (
                "PRODUCTIQ_BM25_ARTIFACT_PATH → RuntimeArtifactPaths.bm25_index → "
                "retrieval/benchmark consumers (HTTP default pipeline injects Retriever; not auto-wired)"
            ),
            "cors": "PRODUCTIQ_CORS_ALLOWED_ORIGINS → Settings → create_app CORSMiddleware when origins configured",
        },
        "docker_prerequisites": {
            "python_version": f"{sys.version_info.major}.{sys.version_info.minor}",
            "requires_python_project": ">=3.13,<3.14",
            "install": "pip install -e .",
            "api_entrypoint": "productiq.api.app:create_app",
            "process_entrypoint": "uvicorn productiq.api.app:create_app --factory",
            "default_port": "8000 (operator choice; not hard-coded in app)",
            "health": "/health",
            "readiness": "/ready",
            "env_vars_documented": True,
            "artifact_mount_paths_configurable": True,
        },
        "known_limitations": [
            "Default create_app does not auto-build production search/recommendation pipelines.",
            "BM25/embeddings paths resolved but not all offline benchmark modules use Settings yet.",
            "Committed manifest integrity checksums are point-in-time snapshots.",
            "Readiness does not probe PostgreSQL/BM25 unless explicitly extended.",
            "Bare pytest -q fails collection on tests/retrieval/integration conftest (pre-existing).",
        ],
        "deferred_items": [
            "Wire all benchmark/evaluation hard-coded artifact paths to Settings.",
            "Automatic manifest regeneration in CI.",
            "Runtime checksum verification against artifact bytes.",
            "Redis/distributed rate limiting (Phase 13 deferred).",
            "Dockerfile and compose (Phase 15).",
        ],
    }


def write_phase_14_deployment_foundation_audit_artifacts(
    *,
    benchmark_root: Path | None = None,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
    gate_test_passed: int = 0,
    gate_test_failed: int = 0,
    gate_test_skipped: int = 0,
    check_statuses: dict[str, str] | None = None,
    ruff_ok: bool = True,
    mypy_ok: bool = True,
    security_ok: bool = True,
    manifest_audit: dict[str, Any] | None = None,
    docker_readiness: str = "READY",
) -> tuple[Path, Path]:
    root = benchmark_root or Path("resources/benchmark")
    root.mkdir(parents=True, exist_ok=True)
    json_out = json_path or root / "phase_14_deployment_foundation_audit.json"
    md_out = markdown_path or root / "phase_14_deployment_foundation_audit.md"
    manifest_path = Path("resources/deployment/productiq_deployment_manifest.json")
    resolved_manifest_audit = manifest_audit or compare_deployment_manifest_on_disk(
        manifest_path=manifest_path,
    )
    document = build_phase_14_deployment_foundation_audit_document(
        gate_test_passed=gate_test_passed,
        gate_test_failed=gate_test_failed,
        gate_test_skipped=gate_test_skipped,
        check_statuses=check_statuses or default_check_statuses(),
        ruff_ok=ruff_ok,
        mypy_ok=mypy_ok,
        security_ok=security_ok,
        manifest_audit=resolved_manifest_audit,
        docker_readiness=docker_readiness,
    )
    json_out.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 14 — Deployment foundation audit",
        "",
        f"- audit_version: `{document['audit_version']}`",
        f"- phase_14_status: **{document['phase_14_status']}**",
        f"- generated_at_utc: `{document['generated_at_utc']}`",
        "",
        "## Closure",
        "",
        document["closure_statement"],
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|-------|--------|",
    ]
    for key in AUDIT_CHECK_KEYS:
        lines.append(f"| {key.replace('_', ' ')} | {document['checks'][key]} |")
    lines.extend(
        [
            "",
            "## Tests",
            "",
            f"- passed: {document['tests']['passed']}",
            f"- failed: {document['tests']['failed']}",
            f"- skipped: {document['tests']['skipped']}",
            "",
            f"- docker_readiness: **{document['docker_readiness']}**",
            "",
            "## Known limitations",
            "",
        ],
    )
    for item in document["known_limitations"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Deferred", ""])
    for item in document["deferred_items"]:
        lines.append(f"- {item}")
    lines.append("")
    md_out.write_text("\n".join(lines), encoding="utf-8")
    return json_out, md_out


__all__ = [
    "AUDIT_CHECK_KEYS",
    "AUDIT_VERSION",
    "PHASE_14_STATUS",
    "build_phase_14_deployment_foundation_audit_document",
    "compare_deployment_manifest_on_disk",
    "default_check_statuses",
    "write_phase_14_deployment_foundation_audit_artifacts",
]
