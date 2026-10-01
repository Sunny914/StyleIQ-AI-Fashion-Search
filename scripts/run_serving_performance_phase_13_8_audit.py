#!/usr/bin/env python3
"""Write Phase 13.8 final audit artifacts (Phase 13.8.9)."""

from __future__ import annotations

import argparse
from pathlib import Path

from productiq.serving.performance.phase_13_8_audit import write_phase_13_8_final_audit_artifacts


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate Phase 13.8 final performance audit artifacts.")
    parser.add_argument("--benchmark-root", type=Path, default=None)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--markdown-out", type=Path, default=None)
    args = parser.parse_args(argv)
    write_phase_13_8_final_audit_artifacts(
        benchmark_root=args.benchmark_root,
        json_path=args.json_out,
        markdown_path=args.markdown_out,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
