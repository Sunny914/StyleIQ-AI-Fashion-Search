#!/usr/bin/env python3
"""Write Phase 13.9-C observability final audit artifacts."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path


def _count_observability_tests() -> int:
    repo_root = Path(__file__).resolve().parents[1]
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/observability",
        "--collect-only",
        "-q",
    ]
    result = subprocess.run(
        cmd,
        cwd=repo_root,
        capture_output=True,
        text=True,
        check=False,
    )
    combined = result.stdout + result.stderr
    match = re.search(r"(\d+)\s+tests?\s+collected", combined)
    if match:
        return int(match.group(1))
    for line in reversed(result.stdout.splitlines()):
        stripped = line.strip()
        if stripped.isdigit():
            return int(stripped)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 13.9 observability final audit artifacts.")
    parser.add_argument("--benchmark-root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args(argv)

    from productiq.observability.phase_13_9_audit import write_phase_13_9_final_audit_artifacts

    count = _count_observability_tests()
    json_path, md_path = write_phase_13_9_final_audit_artifacts(
        benchmark_root=args.benchmark_root,
        json_path=args.json_out,
        markdown_path=args.markdown_out,
        observability_test_count=count,
    )
    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
