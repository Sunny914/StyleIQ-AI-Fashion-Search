# Phase 15A — Docker serving (FastAPI production container)

**Scope:** API container only. PostgreSQL/pgvector compose is **Phase 15B**; full stack audit is **Phase 15C**.

## Why containerize the API

Phase 14 defined environment-driven configuration and runtime artifact boundaries. Phase 15A packages the **existing** FastAPI stack (`create_app`, Phase 13 middleware, Phase 14 settings) so it runs on Linux without a Windows host Python tree or local PostgreSQL.

## Container architecture

```text
Host :8000
    ↓
Uvicorn (--factory)
    ↓
productiq.api.app:create_app
    ↓
Settings (env) + ServingConfig + optional injected services
    ↓
/api/v1/* routes
```

Large artifacts and PostgreSQL are **outside** the image (mounts + env vars).

## Base runtime

| Item | Value |
|------|--------|
| Base image | `python:3.13-slim-bookworm` |
| Python | 3.13 (matches `pyproject.toml`) |
| Workdir | `/app` |
| User | `productiq` (uid/gid 1000, non-root) |
| Port | **8000** |

## Dependency installation

1. `COPY pyproject.toml README.md` + `COPY src`
2. `pip install --index-url https://download.pytorch.org/whl/cpu torch` (**CPU-only**)
3. `pip install .` (runtime deps, no `[dev]`)

**CPU-only PyTorch:** Prevents `sentence-transformers` from resolving CUDA wheels during build. GPU deployment is out of scope for 15A.

**Not removed:** PyTorch, Transformers, sentence-transformers, LightGBM, FastAPI, Uvicorn, psycopg/pgvector clients, pandas/pyarrow, etc.

**Not done at build:** Hugging Face model weight downloads, PostgreSQL connections, BM25 index build, catalog/embeddings copy.

## Runtime artifact strategy

`.dockerignore` excludes `resources/processed`, `*.parquet`, `*.pkl`, benchmarks, notebooks, tests.

Configure at run time (Phase 14):

- `PRODUCTIQ_PROCESSED_CATALOG_PATH`
- `PRODUCTIQ_BM25_ARTIFACT_PATH`
- `PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH`
- `PRODUCTIQ_MODEL_ARTIFACTS_DIR`

No fake sample artifacts in the image.

## Build

```bash
docker build -t productiq-api:local .
```

Record image size after success:

```bash
docker images productiq-api:local
docker history productiq-api:local --no-trunc | head
```

## Run

```bash
docker run --rm -p 8000:8000 -e APP_ENV=production productiq-api:local
```

`APP_ENV=production` avoids implicit development CORS defaults.

## Health and readiness (existing contract)

Routes are under **`/api/v1`** (not root `/health`):

| Endpoint | Purpose |
|----------|---------|
| `GET /api/v1/health` | Liveness (Phase 13) |
| `GET /api/v1/ready` | Readiness (Phase 13/14; external deps often `not_checked`) |

Examples (PowerShell):

```powershell
Invoke-WebRequest -Uri http://localhost:8000/api/v1/health -UseBasicParsing
Invoke-WebRequest -Uri http://localhost:8000/api/v1/ready -UseBasicParsing
```

Docker `HEALTHCHECK` in the Dockerfile uses **`/api/v1/health`**.

Startup does **not** require PostgreSQL, BM25, embeddings, or model downloads for the process to listen on 8000 when services are not wired.

## OpenAPI smoke (15A)

```bash
curl -s http://localhost:8000/api/v1/openapi.json
```

Expect paths such as `/api/v1/search`, `/api/v1/recommendations`, `/api/v1/products/{product_id}`.

Search/recommendation **business** calls may return configuration errors without 15B/artifacts — acceptable for 15A.

## Security

- No secrets in Dockerfile `ENV`/`ARG`
- `.dockerignore` excludes `.env`, `.env.*`
- Non-root runtime user
- No Windows paths in image definition

## Deferred

| Phase | Work |
|-------|------|
| **15B** | PostgreSQL + pgvector container environment |
| **15C** | Full containerized integration + audit |

## Related

- [docker-runtime.md](docker-runtime.md) (short reference)
- [deployment-configuration.md](deployment-configuration.md)
- [phase-14-deployment-foundation.md](phase-14-deployment-foundation.md)
- Audit: `resources/benchmark/phase_15a_docker_audit.json`
