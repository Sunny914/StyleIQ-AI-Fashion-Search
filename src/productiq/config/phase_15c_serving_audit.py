"""Phase 15C serving-integration audit artifact builder."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

AUDIT_VERSION = "1.0.0"
FULL_CATALOG_EXPECTED = 367_172


def _status(value: bool | None) -> str:
    if value is True:
        return "PASS"
    if value is False:
        return "FAIL"
    return "NOT_RUN"


def build_phase_15c_audit_document(
    *,
    compose_config_ok: bool | None,
    image_build_ok: bool | None,
    fixture_load_ok: bool | None,
    schema_ok: bool | None,
    search_http_ok: bool | None,
    product_http_ok: bool | None,
    recommendation_http_ok: bool | None,
    ready_ok: bool | None,
    full_catalog_loaded: bool | None,
    full_catalog_row_count: int | None,
    pytest_passed: int,
    pytest_failed: int,
    pytest_skipped: int,
    pytest_ok: bool | None,
    ruff_ok: bool | None,
    mypy_ok: bool | None,
    catalog_mode: str | None,
    notes: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    checks = {
        "compose_config": _status(compose_config_ok),
        "api_image_build": _status(image_build_ok),
        "fixture_load": _status(fixture_load_ok),
        "pgvector_schema": _status(schema_ok),
        "http_search": _status(search_http_ok),
        "http_product": _status(product_http_ok),
        "http_recommendation": _status(recommendation_http_ok),
        "readiness": _status(ready_ok),
        "full_catalog_load": _status(full_catalog_loaded),
        "pytest_gate": _status(pytest_ok),
        "ruff": _status(ruff_ok),
        "mypy": _status(mypy_ok),
    }
    blocking = [name for name, status in checks.items() if status == "FAIL"]
    live = [checks[key] for key in ("http_search", "http_product", "http_recommendation")]
    if blocking:
        status = "BLOCKED"
    elif any(value == "NOT_RUN" for value in live):
        status = "INCOMPLETE"
    else:
        status = "COMPLETE"
    return {
        "audit_version": AUDIT_VERSION,
        "phase": "15C",
        "generated_at_utc": datetime.now(tz=UTC).isoformat().replace("+00:00", "Z"),
        "phase_15c_status": status,
        "checks": checks,
        "catalog": {
            "mode": catalog_mode,
            "full_catalog_row_count": full_catalog_row_count,
            "full_catalog_expected": FULL_CATALOG_EXPECTED,
            "full_catalog_verified": full_catalog_loaded is True,
        },
        "tests": {
            "command": "pytest -q --ignore=tests/retrieval/integration",
            "passed": pytest_passed,
            "failed": pytest_failed,
            "skipped": pytest_skipped,
        },
        "evidence": evidence or {},
        "notes": notes or [],
        "deferred": ["Next.js frontend", "cloud deployment", "CI/CD"],
    }


def write_phase_15c_audit_artifacts(
    document: dict[str, Any],
    *,
    root: Path | None = None,
) -> tuple[Path, Path]:
    benchmark = root or Path("resources/benchmark")
    benchmark.mkdir(parents=True, exist_ok=True)
    json_path = benchmark / "phase_15c_serving_audit.json"
    md_path = benchmark / "phase_15c_serving_audit.md"
    json_path.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# Phase 15C — Serving integration audit",
        "",
        f"- status: **{document['phase_15c_status']}**",
        f"- generated_at_utc: `{document['generated_at_utc']}`",
        f"- catalog_mode: `{document['catalog'].get('mode')}`",
        "",
        "## Checks",
        "",
        "| Check | Status |",
        "|-------|--------|",
    ]
    for key, value in document["checks"].items():
        lines.append(f"| {key} | {value} |")
    notes = document.get("notes") or []
    if notes:
        lines.extend(["", "## Notes", ""])
        lines.extend(f"- {note}" for note in notes)
    lines.extend(
        [
            "",
            "## Catalog",
            "",
            f"- expected full count: `{document['catalog']['full_catalog_expected']}`",
            f"- observed full count: `{document['catalog']['full_catalog_row_count']}`",
            f"- full catalog verified: `{document['catalog']['full_catalog_verified']}`",
        ]
    )
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return json_path, md_path


__all__ = ["build_phase_15c_audit_document", "write_phase_15c_audit_artifacts"]
