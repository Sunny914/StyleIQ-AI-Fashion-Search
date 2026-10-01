"""Run opt-in serving concurrency benchmark sweeps."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    env = os.environ.copy()
    env_name = "PRODUCTIQ_SERVING_CONCURRENCY_BENCHMARK"
    if env.get(env_name) != "1":
        print(f"Set {env_name}=1", file=sys.stderr)
        return 2
    catalog = root / "resources" / "processed" / "product_catalog.parquet"
    if not catalog.is_file():
        print(f"Missing catalog artifact: {catalog}", file=sys.stderr)
        return 3
    test_target = root / "tests" / "serving" / "test_serving_concurrency_benchmark_production.py"
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", str(test_target), "-q"],
        cwd=str(root),
        env=env,
        check=False,
    )
    return int(completed.returncode)


if __name__ == "__main__":
    raise SystemExit(main())
