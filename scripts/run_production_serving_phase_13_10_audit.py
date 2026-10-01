#!/usr/bin/env python3
"""Write Phase 13.10-C / Phase 13 final production serving audit artifacts."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _run_gate() -> tuple[int, int, int]:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/observability",
        "tests/api",
        "tests/serving",
        "tests/recommendation",
        "-q",
    ]
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 13 final production serving audit.")
    parser.add_argument("--benchmark-root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args(argv)

    from productiq.serving.phase_13_10_final_audit import (
        write_phase_13_10_final_audit_artifacts,
    )

    passed, failed, skipped = _run_gate()
    json_path, md_path = write_phase_13_10_final_audit_artifacts(
        benchmark_root=args.benchmark_root,
        json_path=args.json_out,
        markdown_path=args.markdown_out,
        gate_test_passed=passed,
        gate_test_failed=failed,
        gate_test_skipped=skipped,
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    print(f"Gate: {passed} passed, {failed} failed, {skipped} skipped")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
