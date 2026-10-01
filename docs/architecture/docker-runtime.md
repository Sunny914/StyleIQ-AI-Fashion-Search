# Phase 15A — Docker runtime (FastAPI production container)

**Status:** Production-oriented API image; database and artifacts supplied at runtime (Phase 14).

## Purpose

Run the existing ProductIQ FastAPI application in Linux containers without a Windows/host Python environment. Configuration is **environment-driven** (Phase 14); PostgreSQL and large artifacts are **not** bundled by default.

## Base image

- `python:3.13-slim-bookworm`
- Matches `requires-python = ">=3.13,<3.14"` in `pyproject.toml`

## Build

```bash
docker build -t productiq-api:local .
```

Installs runtime dependencies via `pip install .` (no `[dev]` extras). **CPU-only PyTorch** is installed first to avoid pulling CUDA wheels during `sentence-transformers` resolution. Hugging Face **model weights are not downloaded** at build time; only Python packages are installed.

## Entrypoint

```bash
uvicorn productiq.api.app:create_app --factory --host 0.0.0.0 --port 8000
```

Uses the same `create_app()` factory as local development.

## Port

- Container listens on **8000** (`EXPOSE 8000`).
- Map host port as needed: `-p 8080:8000`.

## Environment variables

Set at `docker run` / orchestrator (see `.env.example` and [deployment-configuration.md](deployment-configuration.md)):

| Variable | Role |
|----------|------|
| `APP_ENV` | `production` recommended in container |
| `DATABASE_URL` | PostgreSQL when serving stack uses DB |
| `PRODUCTIQ_PROCESSED_CATALOG_PATH` | Mounted catalog parquet |
| `PRODUCTIQ_BM25_ARTIFACT_PATH` | Mounted BM25 artifact |
| `PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH` | Mounted embeddings (not in image) |
| `PRODUCTIQ_MODEL_ARTIFACTS_DIR` | Mounted model directory |
| `PRODUCTIQ_CORS_ALLOWED_ORIGINS` | Frontend origins |
| Phase 13 | `PRODUCTIQ_*` serving/resilience settings |

No production secrets are baked into the image.

## Artifact mounting

Large files under `resources/processed/` are **excluded** via `.dockerignore`. Mount volumes and point env vars at container paths, e.g.:

```bash
-v /data/productiq/catalog.parquet:/data/catalog.parquet:ro \
-e PRODUCTIQ_PROCESSED_CATALOG_PATH=/data/catalog.parquet
```

Embeddings (~768MB) and BM25 pickles are **not** copied into the image by default.

## Healthcheck

Docker `HEALTHCHECK` calls **`GET /api/v1/health`** (liveness only). Does not use `/ready` and does not require PostgreSQL or artifacts.

## Security

- Non-root user `productiq` (uid/gid 1000)
- No `ARG`/`ENV` credentials
- `.dockerignore` excludes `.env`, benchmarks, notebooks, tests

## Intentionally NOT in the image

- PostgreSQL / pgvector server
- docker-compose stack (Phase 15B+)
- Redis, Next.js, cloud tooling
- Full `resources/processed` tree
- Dev dependencies (pytest, ruff, mypy)
- CI/CD pipelines

## Minimal smoke run

```bash
docker run --rm -p 8000:8000 -e APP_ENV=production productiq-api:local
curl -s http://localhost:8000/api/v1/health
```

Liveness should succeed without PostgreSQL when no DB-dependent services are wired at startup.

## Related

- [docker-serving.md](docker-serving.md) — Phase 15A full guide
- `resources/deployment/productiq_deployment_manifest.json`
