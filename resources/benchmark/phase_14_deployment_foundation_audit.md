# Phase 14 — Deployment foundation audit

- audit_version: `1.0.0`
- phase_14_status: **complete**
- generated_at_utc: `2026-09-30T18:39:16.203000Z`

## Closure

Phase 14 deployment foundation (configuration, runtime artifacts, database contract) is coherent and locally validated; live PostgreSQL/pgvector validation remains opt-in.

## Checks

| Check | Status |
|-------|--------|
| single configuration system | PASS |
| configuration contract | PASS |
| artifact resolution | PASS |
| artifact startup laziness | PASS |
| database pgvector contract | PASS |
| live postgresql pgvector | NOT_RUN |
| startup import safety | PASS |
| health readiness semantics | PASS |
| secret and path safety | PASS |
| deployment manifest consistency | PASS |
| api regression | PASS |
| configuration runtime traces | PASS |
| docker readiness | PASS |
| test suite | PASS |
| ruff | PASS |
| mypy | PASS |

## Tests

- passed: 1677
- failed: 0
- skipped: 45

- docker_readiness: **READY**

## Known limitations

- Default create_app does not auto-build production search/recommendation pipelines.
- BM25/embeddings paths resolved but not all offline benchmark modules use Settings yet.
- Committed manifest integrity checksums are point-in-time snapshots.
- Readiness does not probe PostgreSQL/BM25 unless explicitly extended.
- Bare pytest -q fails collection on tests/retrieval/integration conftest (pre-existing).

## Deferred

- Wire all benchmark/evaluation hard-coded artifact paths to Settings.
- Automatic manifest regeneration in CI.
- Runtime checksum verification against artifact bytes.
- Redis/distributed rate limiting (Phase 13 deferred).
- Dockerfile and compose (Phase 15).
