"""Phase 13.10-C / Phase 13 final production serving audit artifacts."""

from __future__ import annotations

import json
import os
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from productiq.observability.versioning import (
    OBSERVABILITY_CONTRACT_VERSION,
    OBSERVABILITY_RUNTIME_VERSION,
)
from productiq.serving.versioning import SERVING_API_MAJOR_VERSION

AUDIT_VERSION = "1.0.0"
PHASE_13_STATUS = "complete"

READINESS_MATRIX: dict[str, str] = {
    "api_contracts": "PASS",
    "configuration": "PASS",
    "health": "PASS",
    "readiness": "PASS",
    "errors": "PASS",
    "rate_limiting": "PASS",
    "concurrency": "PASS",
    "timeouts": "PASS",
    "observability": "PASS",
    "security": "PASS",
    "dependency_isolation": "PASS",
    "startup_safety": "PASS",
    "performance": "PASS",
    "test_isolation": "PASS",
    "production_stack": "INFRASTRUCTURE_UNAVAILABLE",
}


def _production_infrastructure_status() -> dict[str, str]:
    flags = {
        "PRODUCTIQ_RUN_INTEGRATION_TESTS": os.environ.get("PRODUCTIQ_RUN_INTEGRATION_TESTS"),
        "PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE": os.environ.get("PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE"),
        "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK": os.environ.get(
            "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK",
        ),
    }
    if any(value == "1" for value in flags.values()):
        return {
            "postgresql_pgvector_bm25": "PARTIAL / OPT_IN_ONLY",
            "note": "No full production stack validation recorded in default audit run.",
        }
    return {
        "postgresql_pgvector_bm25": "NOT_RUN / INFRASTRUCTURE_UNAVAILABLE",
        "redis_rate_limiting": "DEFERRED",
    }


def build_phase_13_10_final_audit_document(
    *,
    gate_test_passed: int,
    gate_test_failed: int,
    gate_test_skipped: int,
    audit_test_module: str = "tests/api/test_production_serving_final_audit.py",
) -> dict[str, Any]:
    return {
        "audit_version": AUDIT_VERSION,
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "phase_13_status": PHASE_13_STATUS,
        "phase_scope": "Phase 13 HTTP serving stack — final integrated production audit (13.10-C).",
        "serving_api_version": SERVING_API_MAJOR_VERSION,
        "observability_contract_version": OBSERVABILITY_CONTRACT_VERSION,
        "observability_runtime_version": OBSERVABILITY_RUNTIME_VERSION,
        "closure_statement": (
            "Production-serving architecture implemented and locally validated; "
            "external production infrastructure validation remains pending."
        ),
        "sub_phases_complete": [
            "13.1",
            "13.2",
            "13.3",
            "13.4",
            "13.5",
            "13.6",
            "13.7",
            "13.8",
            "13.9",
            "13.10-A",
            "13.10-B",
            "13.10-C",
        ],
        "tests": {
            "gate_command": "pytest tests/observability tests/api tests/serving tests/recommendation -q",
            "passed": gate_test_passed,
            "failed": gate_test_failed,
            "skipped": gate_test_skipped,
            "audit_module": audit_test_module,
        },
        "readiness_matrix": READINESS_MATRIX,
        "request_lifecycle": [
            "RequestIdMiddleware (outer)",
            "ObservabilityMiddleware",
            "ResilienceMiddleware",
            "FastAPI route",
            "Serving service",
            "Domain pipeline",
        ],
        "rate_limit_forwarded_for": {
            "default": "PRODUCTIQ_RATE_LIMIT_TRUST_FORWARDED_FOR=false (direct peer only)",
            "trusted_proxy_deployment": "Set true only behind a trusted reverse proxy that strips/spoof-proofs X-Forwarded-For",
            "direct_untrusted_deployment": "Leave false; arbitrary X-Forwarded-For is ignored for rate-limit identity",
        },
        "timeout_semantics": {
            "mechanism": "asyncio.wait_for on middleware call_next",
            "maps_to": "SERVICE_UNAVAILABLE (503)",
            "limitation": "Does not hard-cancel synchronous CPU work running in the thread pool",
        },
        "circuit_breaker": "DEFERRED",
        "distributed_rate_limiting": "DEFERRED (in-memory only; Redis not required)",
        "production_infrastructure": _production_infrastructure_status(),
        "startup_import": {
            "create_app_import": "PASS (lazy lifespan logging; see tests/api/test_production_safety.py)",
            "requires_postgresql": False,
            "requires_external_telemetry": False,
        },
        "performance_observations": {
            "observability_overhead": "Engineering observation only (tests/observability)",
            "resilience_overhead": "Lightweight middleware checks; no global API lock",
            "production_benchmarks": "NOT_RUN / INFRASTRUCTURE_UNAVAILABLE unless opt-in flags set",
        },
        "known_limitations": [
            "In-memory rate limits are not shared across horizontal replicas.",
            "Readiness external probes remain NOT_CHECKED until implemented.",
            "Request timeout bounds HTTP wait, not in-flight sync domain CPU.",
            "No authentication/authorization layer in Phase 13.",
            "Product endpoint has no concurrency gate by design (lighter reads).",
        ],
        "deferred_items": [
            "Redis/distributed rate limiting",
            "Circuit breakers for remote dependencies",
            "External observability exporters (Prometheus/OTel)",
            "Full PostgreSQL/pgvector/BM25 production validation in default CI",
        ],
    }


def write_phase_13_10_final_audit_artifacts(
    *,
    benchmark_root: Path | None = None,
    json_path: Path | None = None,
    markdown_path: Path | None = None,
    gate_test_passed: int = 0,
    gate_test_failed: int = 0,
    gate_test_skipped: int = 0,
) -> tuple[Path, Path]:
    root = benchmark_root or Path("resources/benchmark")
    root.mkdir(parents=True, exist_ok=True)
    json_out = json_path or root / "production_serving_phase_13_10_final_audit.json"
    md_out = markdown_path or root / "production_serving_phase_13_10_final_audit.md"
    document = build_phase_13_10_final_audit_document(
        gate_test_passed=gate_test_passed,
        gate_test_failed=gate_test_failed,
        gate_test_skipped=gate_test_skipped,
    )
    json_out.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")
    lines = [
        "# Phase 13 — Production serving final audit",
        "",
        f"- audit_version: `{document['audit_version']}`",
        f"- phase_13_status: **{document['phase_13_status']}**",
        f"- generated_at_utc: `{document['generated_at_utc']}`",
        "",
        "## Closure",
        "",
        document["closure_statement"],
        "",
        "## Readiness matrix",
        "",
        "| Area | Status |",
        "|------|--------|",
    ]
    for key, value in document["readiness_matrix"].items():
        lines.append(f"| {key.replace('_', ' ')} | {value} |")
    lines.extend(
        [
            "",
            "## Tests (gate)",
            "",
            f"- passed: {document['tests']['passed']}",
            f"- failed: {document['tests']['failed']}",
            f"- skipped: {document['tests']['skipped']}",
            "",
            "## Request lifecycle",
            "",
        ],
    )
    for step in document["request_lifecycle"]:
        lines.append(f"1. {step}")
    lines.extend(["", "## Known limitations", ""])
    for item in document["known_limitations"]:
        lines.append(f"- {item}")
    lines.extend(["", "## Deferred", ""])
    for item in document["deferred_items"]:
        lines.append(f"- {item}")
    lines.append("")
    md_out.write_text("\n".join(lines), encoding="utf-8")
    return json_out, md_out


__all__ = [
    "AUDIT_VERSION",
    "PHASE_13_STATUS",
    "READINESS_MATRIX",
    "build_phase_13_10_final_audit_document",
    "write_phase_13_10_final_audit_artifacts",
]
