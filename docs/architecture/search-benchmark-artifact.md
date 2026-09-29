# Phase 12.2 — Search Benchmark Artifact

**Status:** Benchmark dataset and loading (Phase 12.3+ implements evaluation runners)  
**Contracts:** Phase 12.1 `SearchEvaluationBenchmark` and related types

## Why first-class benchmark artifacts

Search experimentation needs a **versioned, offline source of truth** for queries and graded judgments. Runners (Phase 12.3+) consume the same artifact regardless of retrieval implementation (BM25, semantic, RRF, LTR). Structural validation is separate from live catalog checks so benchmarks remain reproducible without a database at load time.

## Canonical artifact

| Field | Value |
|-------|--------|
| Path | `resources/evaluation/productiq_search_benchmark_v1.json` |
| `artifact_schema_version` | `12.2.0` |
| `benchmark_name` | `productiq_search_benchmark_v1` |
| `benchmark_version` | `1.0.0` |
| Queries | 10 (same review set as lexical v1) |
| Judgments | 44 graded pairs (grade **2** for each legacy binary relevant ID) |

Envelope shape:

```text
artifact_schema_version
metadata  → SearchEvaluationBenchmarkMetadata
queries   → SearchEvaluationQuery[]
```

On disk, `metadata` and `queries` match the Phase 12.1 benchmark body; the file adds `artifact_schema_version` for loader compatibility checks.

## Query representation

Each **`SearchEvaluationQuery`** includes:

- `query_id` — unique within the benchmark
- `query_text` — non-empty search string
- `query_category` — review batch label (e.g. `brand_activity`)
- `relevance_judgments` — one or more graded product labels

## Graded relevance

**`SearchRelevanceJudgment`**: `product_id`, `grade` in **0–3** (Phase 12.1). Canonical v1 uses grade **2** only, aligned with legacy binary relevance and `SearchMetricConfiguration.min_relevant_grade` default **2**.

Rules enforced at validation:

- Non-empty `product_id`
- Valid grade range
- No duplicate `product_id` within a query
- Unique `query_id` across the benchmark
- Non-empty benchmark

## Validation layers

1. **Pydantic** — frozen models, `extra="forbid"`, field validators on 12.1 types.
2. **Artifact loader** — JSON parse, `artifact_schema_version` match, `SearchBenchmarkArtifactFile` validation.
3. **Integrity** — `validate_search_benchmark_integrity()` (non-empty queries/judgments, metadata identity).

**Not** part of structural load: catalog membership checks (see `semantic_catalog_validation` pattern for legacy retrieval). Use `catalog_provenance_from_benchmark()` to read `catalog_artifact` and `source_representation_checksum` without DB I/O.

## Versioning and provenance

- **Artifact schema** (`12.2.0`) — file envelope and loader behavior.
- **Benchmark identity** (`benchmark_name` / `benchmark_version`) — semantic dataset version for lineage in `SearchEvaluationLineage`.
- **Catalog provenance** — optional paths and representation checksums document which catalog snapshot judgments were reviewed against; compatibility with the current catalog is a separate concern.

## Legacy lexical conversion

Phase 4.8 **`lexical_retrieval_benchmark_v1.json`** (`productiq_lexical_retrieval_v1`, v1.0.0) remains unchanged.

Explicit adapters in `legacy_benchmark_adapter.py`:

| Function | Behavior |
|----------|----------|
| `convert_lexical_retrieval_benchmark_to_search` | Input: loaded `LexicalRetrievalBenchmark` (IDs **deduped** by Phase 4.8 loader) |
| `convert_lexical_benchmark_payload_to_search` | Input: raw JSON (**file order**, duplicates fail graded query validation) |
| `convert_lexical_benchmark_path_to_search` | `use_lexical_loader=True` (default) or raw payload path |

Binary `relevant_product_ids` map to grade **2** via `lexical_query_to_search_evaluation_query`. The canonical search benchmark is a **derived** artifact with new identity `productiq_search_benchmark_v1`; adapter output retains lexical **name/version** when converting from legacy for traceability.

## Future runners (Phase 12.3+)

```text
load_search_evaluation_benchmark(path)
        ↓
SearchEvaluationBenchmark
        ↓
build_search_evaluation_request(benchmark, variant, metric_configuration)
        ↓
SearchEvaluationRequest
        ↓
(runner executes search → ranked IDs → metrics)
```

Phase 12.2 does not execute search or compute metrics.

## Related docs

- `docs/architecture/search-evaluation-contract.md` — Phase 12.1 contracts
- `resources/evaluation/README.md` — evaluation artifact index
