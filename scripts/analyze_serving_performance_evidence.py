#!/usr/bin/env python3
"""Inventory serving benchmark evidence and emit bottleneck analysis (Phase 13.8.8)."""

from __future__ import annotations

import argparse
from pathlib import Path

from productiq.serving.performance.evidence_analysis import (
    build_serving_performance_evidence_report,
    render_evidence_report_markdown,
)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build evidence-based serving performance analysis (no fabricated metrics).",
    )
    parser.add_argument(
        "--benchmark-root",
        type=Path,
        default=None,
        help="Override resources/benchmark root (default: repository benchmark directory).",
    )
    parser.add_argument(
        "--json-out",
        type=Path,
        default=None,
        help="Optional path to write ServingPerformanceEvidenceReport JSON.",
    )
    parser.add_argument(
        "--markdown-out",
        type=Path,
        default=None,
        help="Optional path to write Markdown report.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    report = build_serving_performance_evidence_report(benchmark_root=args.benchmark_root)
    markdown = render_evidence_report_markdown(report)
    print(markdown)
    if args.json_out is not None:
        args.json_out.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    if args.markdown_out is not None:
        args.markdown_out.write_text(markdown, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
