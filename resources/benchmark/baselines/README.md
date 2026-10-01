# Performance baselines (Phase 13.8.7)

Pinned baseline records live here, separate from raw benchmark run artifacts under
`sibling directories` (`search_serving/`, `product_serving/`, etc.).

## Layout

```text
resources/benchmark/baselines/
  search/
  recommendation/
  product/
  concurrency/
```

Each baseline file is a JSON `ServingPerformanceBaselineRecord` keyed by deterministic
`baseline_id` (defaults to `BenchmarkRunIdentity.storage_key()`).

## Pinning

Use `pin_run_result_as_baseline()` from `productiq.serving.performance.baseline_storage`.
Baselines are **not** overwritten unless `overwrite=True`.

## Comparison

Use `scripts/compare_serving_performance.py` with `--baseline` and `--current`, or
`compare_to_stored_baseline()` for lookup by identity under a category directory.

Do not fabricate baseline numbers; pin from an explicit benchmark run artifact.
