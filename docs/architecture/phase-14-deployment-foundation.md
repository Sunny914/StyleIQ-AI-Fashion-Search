# Phase 14 — Deployment foundation (final)

**Phase 14 status:** Complete after 14C audit (configuration + runtime contracts locally validated).

## Sub-phases

| Phase | Scope |
|-------|--------|
| **14A** | `Settings`, `ServingConfig`, `APP_ENV`, database/CORS/artifact env vars, secrets boundary |
| **14B** | `RuntimeArtifactPaths`, validation, database/pgvector contract, deployment manifest |
| **14C** | Evidence-first audit, Docker prerequisites, regression gate |

## Architecture

```text
Environment variables (+ optional .env)
        ↓
Settings + ServingConfig (single configuration system)
        ↓
load_deployment_configuration() / resolve_runtime_artifact_paths()
        ↓
create_app(app_settings=...)  →  FastAPI + Phase 13 middleware
        ↓
Optional serving services (injected pipelines / catalog providers)
        ↓
PostgreSQL + pgvector + artifacts (when production stack wired)
```

## Traces (14C verified)

- **APP_ENV** → `Settings.app_env` + `ServingConfig.deployment_environment` → `create_app`
- **DATABASE_URL** → `Settings.database_url` → `create_engine_from_settings()` on demand
- **PRODUCTIQ_PROCESSED_CATALOG_PATH** → `RuntimeArtifactPaths` → `product_wiring.resolved_processed_catalog_path()`
- **PRODUCTIQ_BM25_ARTIFACT_PATH** → `RuntimeArtifactPaths.bm25_index` → retrieval/benchmark consumers (HTTP search uses injected `Retriever`, not auto-loaded BM25)
- **CORS** → `Settings.cors_allowed_origins` → `CORSMiddleware` when non-empty

## Health

- `/health` — process liveness (Phase 13)
- `/ready` — configured workloads; external PostgreSQL/BM25/pgvector remain **not_checked** unless extended

## Audit artifacts

- `resources/benchmark/phase_14_deployment_foundation_audit.json`
- `resources/benchmark/phase_14_deployment_foundation_audit.md`

Regenerate: `python scripts/run_phase_14_deployment_foundation_audit.py`

## Related docs

- [deployment-configuration.md](deployment-configuration.md) — 14A
- [deployment-runtime-contract.md](deployment-runtime-contract.md) — 14B
- [production-serving-final.md](production-serving-final.md) — Phase 13

## Phase 15 (next)

Dockerfile / compose using documented entrypoint, env vars, artifact mounts, and health checks — see [docker-runtime.md](docker-runtime.md) (15A image).
