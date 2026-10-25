# Phase 15B — Docker Compose PostgreSQL + pgvector

**Scope:** Database container environment and schema contract. Full stack artifact wiring and integration audit is **Phase 15C**.

## Why PostgreSQL + pgvector in Compose

Phase 14 defined the **database URL contract**, pgvector extension, `products.embedding vector(384)`, and HNSW cosine index semantics. Phase 15A containerized the **API only**. Phase 15B adds a **reproducible PostgreSQL + pgvector service** on the Compose network so the API can use hostname `postgres` without baking artifacts into the API image.

## Architecture

```text
Host :8000
    ↓
productiq-api (Phase 15A image)
    ↓  DATABASE_URL → postgres:5432
postgres (pgvector/pgvector:pg16)
    ↓
vector extension + products table + HNSW index
```

Large catalog/embeddings/BM25 files remain **host-mounted or operator-loaded** (Phase 14 artifact env vars). They are **not** copied into the API image (`.dockerignore` unchanged).

## Services

| Service | Role |
|---------|------|
| `postgres` | PostgreSQL 16 with pgvector; internal network only (no published `5432` by default) |
| `productiq-api` | Existing Dockerfile; Uvicorn factory; depends on `postgres` **healthy** |

## Network and `DATABASE_URL`

Inside Compose, the API must use the **service name** as host:

```text
postgresql+psycopg://<user>:<password>@postgres:5432/<database>
```

Do **not** use `localhost` or `127.0.0.1` in the Compose `DATABASE_URL` — that refers to the API container itself.

Local non-Compose development may still use `localhost` in `.env` (unchanged).

Copy `.env.example` → `.env` and set at least:

- `POSTGRES_PASSWORD`
- `DATABASE_URL` (Compose form with `@postgres:`)

## pgvector and schema contract

Bootstrap (explicit operator step):

```bash
docker compose up -d postgres
docker compose run --rm productiq-api python -m productiq.database.bootstrap_compose --load-demo-fixture
docker compose up -d productiq-api
```

Implementation reuses existing modules:

| Step | Module |
|------|--------|
| `CREATE EXTENSION vector` | `productiq.database.pgvector.ensure_pgvector_extension` |
| `products` table | `productiq.database.catalog_ddl.create_product_catalog_tables` |
| `embedding vector(384)` | `productiq.database.vector_catalog.ensure_product_vector_catalog_schema` |
| HNSW cosine index | `productiq.database.vector_catalog.create_product_embedding_hnsw_index` |

Contract constants (Phase 14 / 4.12):

- Extension: `vector`
- Column: `products.embedding vector(384)`
- Index: `ix_products_embedding_hnsw_cosine`
- Opclass: `vector_cosine_ops`

Verify only:

```bash
docker compose run --rm productiq-api python -m productiq.database.bootstrap_compose --verify-only --json
```

## Data loading strategy

| Layer | Responsibility |
|-------|----------------|
| **15B infrastructure** | Extension, table, embedding column, HNSW index (empty or demo rows) |
| **Full catalog** | Existing pipeline `load_processed_catalog` / Parquet loader (367k rows) — **manual** |
| **Full embeddings** | `scripts/run_vector_index_build.py` — **manual** |
| **Compose smoke demo** | `--load-demo-fixture` inserts **3** labeled `compose-demo-*` rows (not production data) |

## Healthchecks

- **Postgres:** `pg_isready -U … -d …` (Compose `healthcheck`)
- **API:** `/api/v1/health` (Dockerfile / Phase 13 liveness)

Readiness (`/api/v1/ready`) still reflects **configured serving dependencies**, not automatic full-stack DB/catalog loading.

## Security

- Passwords via `.env` only (gitignored); Compose uses `${POSTGRES_PASSWORD}` / `${DATABASE_URL}` substitution
- No credentials in `src/` or Dockerfile
- Postgres **not** published to host by default
- API runs as non-root `productiq` user (15A)

## Commands

```bash
docker compose config          # requires .env
docker compose up -d postgres
docker compose run --rm productiq-api python -m productiq.database.bootstrap_compose --load-demo-fixture
docker compose up -d
curl http://localhost:8000/api/v1/health
python scripts/run_phase_15b_database_audit.py
```

## Known limitations

- Full **367k** catalog + embedding load is out of band for default Compose startup
- Host tools need Postgres port mapping only if you add an optional `ports:` block (not default)
- Phase **15B audit** live Docker gates require a healthy Docker daemon and `.env`

## Phase 15C

Serving integration (real search / product / recommendations) is documented in [docker-serving-integration.md](docker-serving-integration.md). Schema bootstrap here remains the 15B contract; catalog load is an explicit 15C command.

## Deferred to later phases

- Next.js frontend
- Cloud deployment and CI/CD

## Related

- [docker-serving.md](docker-serving.md) (15A API container)
- [deployment-runtime-contract.md](deployment-runtime-contract.md)
- Audit: `resources/benchmark/phase_15b_database_audit.json`
