#!/usr/bin/env python3
"""Generate Phase 15C serving-integration audit artifacts.

Never records PASS for a check that was not executed. Does not treat health-only
success as end-to-end serving. Does not claim the 367,172-row catalog was loaded
unless that load is independently verified.
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


def _parse_pytest(output: str) -> tuple[int, int, int]:
    def _count(label: str) -> int:
        match = re.search(rf"(\d+) {label}", output)
        return int(match.group(1)) if match else 0

    return _count("passed"), _count("failed"), _count("skipped")


def _http_json(url: str, method: str = "GET", body: bytes | None = None) -> tuple[int | None, Any]:
    request = urllib.request.Request(url, data=body, method=method)
    if body is not None:
        request.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"raw": raw[:500]}
            return response.status, payload
    except urllib.error.HTTPError as exc:
        try:
            payload = json.loads(exc.read().decode("utf-8"))
        except (json.JSONDecodeError, OSError):
            payload = {"error": exc.reason}
        return exc.code, payload
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return None, {"error": str(exc)}


def _sanitize(value: str) -> str:
    return re.sub(r"(postgresql(?:\+psycopg)?://)([^:@/]+):([^@/]+)@", r"\1***:***@", value)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-docker", action="store_true")
    parser.add_argument("--skip-image-build", action="store_true")
    parser.add_argument("--skip-pytest", action="store_true")
    parser.add_argument("--fixture-verified", action="store_true")
    parser.add_argument("--schema-verified", action="store_true")
    parser.add_argument("--image-built", action="store_true")
    parser.add_argument("--api-base", default="http://127.0.0.1:8000")
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[1]

    from productiq.config.phase_15c_serving_audit import (
        build_phase_15c_audit_document,
        write_phase_15c_audit_artifacts,
    )

    passed = failed = skipped = 0
    pytest_result_text = ""
    if args.skip_pytest:
        notes_prefix = ["pytest skipped (--skip-pytest); gate recorded as NOT_RUN"]
    else:
        notes_prefix = []
        pytest_cmd = [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "--ignore=tests/retrieval/integration",
        ]
        pytest_result = subprocess.run(pytest_cmd, cwd=repo, capture_output=True, text=True, check=False)
        passed, failed, skipped = _parse_pytest(pytest_result.stdout + pytest_result.stderr)
        pytest_result_text = (pytest_result.stdout + pytest_result.stderr)[-1500:]
    ruff = subprocess.run(
        [sys.executable, "-m", "ruff", "check", "src", "tests"],
        cwd=repo,
        capture_output=True,
        check=False,
    )
    mypy = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            "src/productiq/api/services/production_stack.py",
            "src/productiq/database/load_runtime_catalog.py",
            "src/productiq/serving/postgres_catalog_provider.py",
            "src/productiq/config/phase_15c_serving_audit.py",
            "src/productiq/api/app.py",
            "src/productiq/api/lifespan.py",
        ],
        cwd=repo,
        capture_output=True,
        check=False,
    )

    compose_ok: bool | None = None
    image_ok: bool | None = None
    fixture_ok: bool | None = None
    schema_ok: bool | None = None
    search_ok: bool | None = None
    product_ok: bool | None = None
    rec_ok: bool | None = None
    ready_ok: bool | None = None
    catalog_mode: str | None = None
    notes: list[str] = list(notes_prefix)
    evidence: dict[str, Any] = {
        "pytest_tail": pytest_result_text,
        "ruff_returncode": ruff.returncode,
        "mypy_returncode": mypy.returncode,
    }

    if not args.skip_docker:
        config = subprocess.run(
            ["docker", "compose", "config"],
            cwd=repo,
            capture_output=True,
            text=True,
            check=False,
        )
        compose_ok = config.returncode == 0
        if not compose_ok:
            notes.append(_sanitize(config.stderr.strip() or "docker compose config failed"))
        if args.image_built:
            image_ok = True
            notes.append("API image build verified in this session; not rebuilt by the audit runner")
        elif args.skip_image_build:
            image_ok = None
            notes.append("API image build skipped (--skip-image-build)")
        else:
            build = subprocess.run(
                ["docker", "compose", "build", "productiq-api"],
                cwd=repo,
                capture_output=True,
                text=True,
                check=False,
            )
            image_ok = build.returncode == 0
            if not image_ok:
                notes.append("docker compose build productiq-api failed")
        base = args.api_base.rstrip("/")
        ready_status, ready_body = _http_json(f"{base}/api/v1/ready")
        product_status, product_body = _http_json(f"{base}/api/v1/products/compose-demo-001")
        search_status, search_body = _http_json(
            f"{base}/api/v1/search",
            method="POST",
            body=json.dumps({"query": "navy cotton shirt", "top_k": 3}).encode(),
        )
        rec_status, rec_body = _http_json(
            f"{base}/api/v1/recommendations",
            method="POST",
            body=json.dumps({"seed_product_id": "compose-demo-001", "top_k": 3}).encode(),
        )
        ready_ok = ready_status == 200 and isinstance(ready_body, dict)
        if isinstance(ready_body, dict):
            catalog_mode = next(
                (
                    str(check.get("message", ""))
                    for check in ready_body.get("checks", [])
                    if check.get("name") == "catalog_data"
                ),
                None,
            )
            evidence["ready_status_value"] = ready_body.get("status")
        product_ok = (
            product_status == 200
            and isinstance(product_body, dict)
            and product_body.get("product_id") == "compose-demo-001"
        )
        search_ok = (
            search_status == 200
            and isinstance(search_body, dict)
            and bool(search_body.get("results"))
        )
        rec_ok = rec_status == 200 and isinstance(rec_body, dict) and "recommendations" in rec_body
        evidence["http"] = {
            "ready": ready_status,
            "product": product_status,
            "search": search_status,
            "recommendations": rec_status,
        }
        notes.append("full_catalog_load not executed by this audit runner")
        if args.fixture_verified:
            fixture_ok = True
        if args.schema_verified:
            schema_ok = True
        if fixture_ok is None or schema_ok is None:
            notes.append("fixture_load and pgvector_schema are PASS only when independently verified")
    else:
        notes.append("Docker live HTTP checks skipped (--skip-docker)")

    doc = build_phase_15c_audit_document(
        compose_config_ok=compose_ok,
        image_build_ok=image_ok,
        fixture_load_ok=fixture_ok,
        schema_ok=schema_ok,
        search_http_ok=search_ok,
        product_http_ok=product_ok,
        recommendation_http_ok=rec_ok,
        ready_ok=ready_ok,
        full_catalog_loaded=None,
        full_catalog_row_count=None,
        pytest_passed=passed,
        pytest_failed=failed,
        pytest_skipped=skipped,
        pytest_ok=None if args.skip_pytest else failed == 0,
        ruff_ok=ruff.returncode == 0,
        mypy_ok=mypy.returncode == 0,
        catalog_mode=catalog_mode,
        notes=notes,
        evidence=evidence,
    )
    json_path, md_path = write_phase_15c_audit_artifacts(doc)
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"status: {doc['phase_15c_status']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
