# Phase 14A — Deployment configuration & environment contract

**Status:** Environment-driven deployment settings for local, production-like, and production targets.

## Configuration hierarchy

```text
Environment variables (+ optional .env, gitignored)
        ↓
Settings (APP_ENV, database, artifacts, CORS)
        +
ServingConfig (HTTP limits, resilience, service metadata)
        ↓
load_deployment_configuration()  →  create_app()
        ↓
FastAPI (middleware, routes, future containers/cloud)
```

Application code should use `get_settings()` and `ServingConfig` (via `app.state` or explicit injection). Do not introduce parallel `os.getenv` configuration.

## Environment model

| Value | Purpose |
|-------|---------|
| `development` | Local dev; safe defaults including optional local CORS for Next.js |
| `production-like` | Staging / prod-like local runs; no implicit CORS defaults |
| `production` | Deployed production; explicit secrets and origins required |
| `testing` | Pytest/CI only (not a deploy target) |

Set via `APP_ENV`. The same label is exposed on `ServingConfig.deployment_environment` (same variable).

Environment controls **configuration**, not branching business logic in domain pipelines.

## Service configuration (`ServingConfig`)

Existing Phase 13 fields unchanged in behavior: `PRODUCTIQ_SERVICE_NAME`, `PRODUCTIQ_API_VERSION`, top_k/query/body limits, rate limiting, concurrency, timeouts. See [production-serving-final.md](production-serving-final.md).

## Database configuration

Primary: `DATABASE_URL` (PostgreSQL DSN).

Optional component mode (`PRODUCTIQ_DATABASE_USE_COMPONENT_FIELDS=1`):

- `PRODUCTIQ_DATABASE_HOST`
- `PRODUCTIQ_DATABASE_PORT`
- `PRODUCTIQ_DATABASE_NAME`
- `PRODUCTIQ_DATABASE_USER`
- `DATABASE_PASSWORD` (secret)

When component mode is off and `DATABASE_URL` is unset, development uses a documented local default DSN (for backward compatibility). **Production and production-like deployments must set credentials via environment at runtime.**

Logs and public diagnostics use `redacted_database_url` / `settings_public_dict()` — never log raw `DATABASE_URL`.

## Artifact paths

Runtime-configurable, portable paths (no Windows drive letters):

| Variable | Default (relative) |
|----------|-------------------|
| `PRODUCTIQ_PROCESSED_CATALOG_PATH` | `resources/processed/product_catalog.parquet` |
| `PRODUCTIQ_BM25_ARTIFACT_PATH` | `resources/processed/bm25` |
| `PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH` | `resources/processed/product_embeddings.parquet` |
| `PRODUCTIQ_MODEL_ARTIFACTS_DIR` | `resources/models` |

Phase 14A defines the boundary only; retrieval/ranking code adoption is incremental. Do not hard-code `E:\`, `C:\`, or user home paths in application code.

## CORS

Variable: `PRODUCTIQ_CORS_ALLOWED_ORIGINS` (comma-separated list).

- **development:** if unset, defaults to `http://localhost:3000` and `http://127.0.0.1:3000`
- **production-like / production:** no default; set explicit frontend origins

`PRODUCTIQ_CORS_ALLOW_CREDENTIALS=1` requires explicit origins — wildcard `*` is rejected with credentials.

CORS is applied in `create_app()` when at least one origin is configured.

## Secrets

Treat as secrets (never in public dicts or committed files):

- `DATABASE_URL` (contains credentials)
- `DATABASE_PASSWORD`
- `PRODUCTIQ_RATE_LIMIT_DEPLOYMENT_KEY`
- Future external API keys

Use `.env.example` with placeholders only. Real secrets: `.env` / platform secret store (Phase 14B+).

## Forbidden hard-coded values

- Windows absolute paths in config
- Committed passwords or API keys
- Wildcard CORS with credentials
- Hard-coded cloud URLs (e.g. Vercel)

## Development defaults vs production requirements

| Concern | Development | Production |
|---------|-------------|------------|
| Database | Default local DSN if unset | `DATABASE_URL` or component fields + password |
| CORS | Local Next.js defaults if unset | Explicit `PRODUCTIQ_CORS_ALLOWED_ORIGINS` |
| Rate limits | Disabled by default (Phase 13) | Enable via env when needed |

## Related

- [production-serving-final.md](production-serving-final.md) — Phase 13 HTTP stack
- `.env.example` — variable template
- `productiq.config.deployment.load_deployment_configuration`

Regenerate nothing for 14A; run tests with `pytest tests/config`.

Phase 14B runtime contract: [deployment-runtime-contract.md](deployment-runtime-contract.md).
