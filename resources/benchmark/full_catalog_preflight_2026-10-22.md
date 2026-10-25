# Full-catalog preflight — 2026-10-22

Evidence from this run only. Historical Phase 15A/15B/15C audits were not modified. Nothing was committed or pushed. The site is not publicly deployed.

## 1. Working-tree safety — PASS

- Branch: `main`
- HEAD: `34dda60d9a049b60003d2c4f1f47c07dfe01e549` (`feat: added Fastapi backend production serving and deployment foundation`)
- Uncommitted Phase 15B, 15C, and 16 files were left in place.
- This preflight also changed `src/productiq/database/catalog_validation.py`, `src/productiq/database/load_runtime_catalog.py`, and `src/productiq/retrieval/bm25.py`.
- No commit, push, reset, stash, or discard.

## 2. Artifact validation — PASS

Read-only checks. Files were not rebuilt.

| Artifact | Bytes | SHA-256 | Rows | Notes |
| --- | ---: | --- | ---: | --- |
| `resources/raw/Ajio Fashion Clothing.csv` | 104,650,262 | `6f9e68f1658af812793a910dc2f2e59707aa8e266f125ce40b5aaf41440041d5` | 367,172 | Counted as cp1252. UTF-8 decode fails on byte `0xe9`. 9 header columns. |
| `resources/processed/product_catalog.parquet` | 37,299,740 | `ffd36e92793377b2b4eea467e8109ff1e202691624a7dc04abc7a0b2d1177645` | 367,172 | Matches manifest. 22 columns. 0 null IDs. 0 duplicate IDs. |
| `resources/processed/product_embeddings.parquet` | 768,086,259 | `d97a843f54ca2cc404bcce7955fb86edc066c9f504f66e82fc1d9d6a23316dc6` | 367,172 | Matches manifest. Model `BAAI/bge-small-en-v1.5`. 384 dimensions. 0 null embeddings. 0 bad dimensions. |
| `resources/processed/bm25_lexical_index.pkl` | 77,062,647 | `9d4c393c3535944cd7278165ffa3a9c5ddc9a08eef056f55c08b9012c627a855` | 367,172 | Matches manifest. 0 duplicate document IDs. |
| `resources/processed/product_representations.parquet` | 36,323,066 | `7fc2b6c08ef03233bdae1c845f4a087cd578fdb6d861b7d64ec72c71e92c3379` | 367,172 | Matches the representation checksum cited by the embedding and BM25 manifests. |

ID alignment: catalog, embeddings, representations, and BM25 are the same 367,172 IDs. No `compose-demo-*` IDs are in the Parquet catalog.

The historical `resources/processed/product_vector_index.manifest.json` was copied to `resources/benchmark/product_vector_index.manifest.preserved-2026-10-22.json` before loading. After the load, both files still share SHA-256 `84d98d6af07f74d06edbd966b453f21fad45754306ee330ded206e07177c3e80`. The new manifest is `resources/benchmark/product_vector_index.manifest.loaded-2026-10-22.json`.

## 3. Database status — PASS

Independent `psql` checks after the load:

- Products: **367,172**
- Distinct product IDs: **367,172**
- Embeddings: **367,172**
- Null embeddings: **0**
- Blank product IDs: **0**
- Embedding dimension: **384** on all 367,172 rows
- `source <> 'ajio'`: **0**
- Null `description`, `brand`, `image_url`, `product_url`, `category_gender`: **0**
- Null `product_type`: **66,466** (column is nullable)
- Genders: Women 211,534; Men 155,638
- Demo rows (`compose-demo-%`): **0**
- Database size: **1,375 MB** (1,441,299,479 bytes)
- HNSW index `ix_products_embedding_hnsw_cosine`: present, `vector_cosine_ops`, **623,067,136 bytes** (~594 MB)
- Column type: `vector(384)`

Before the load the database held only `compose-demo-001`, `compose-demo-002`, and `compose-demo-003` (7,871 kB).

## 4. Full-catalog loading — PASS, with two corrections

The existing Compose command was used:

`python -m productiq.database.load_runtime_catalog --mode full --enforce-official-checksums --json`

Corrections required before that command could finish:

1. The three demo rows were deleted first. The loader requires an exact row count of 367,172 and an exact embedding count of 367,172. Leaving the demo rows would fail validation. The delete was limited to those three IDs and only while the table contained exactly those three rows. No table was dropped or truncated.
2. Catalog validation rejected the table because `embedding` is not one of the 22 Parquet columns. The first run still committed all 367,172 catalog rows, then stopped with `CatalogValidationError` before any embedding update. Validation now allows that one extra column. The loader was given `--vector-manifest-dir` so the new manifest was written under `resources/benchmark/` instead of the read-only processed mount.

The successful run exited 0. Vector load took **1,306.5 seconds**. HNSW creation took **0.35 seconds** because the index already existed (`rebuild=False`) and grew with the updates. Its size is in the same range as the historical 625,590,272-byte index, so it was not rebuilt.

Catalog upsert is `ON CONFLICT (product_id) DO UPDATE`. It does not insert duplicate IDs. A later catalog-only rerun can set `embedding` back to null, because the Parquet rows omit that column and the update copies `EXCLUDED.embedding`. The embedding step in the same command restores it. Do not stop between those two steps.

Host disk before the load: C: 183.92 GB free; E: 349.05 GB free. Docker volume growth stayed inside that budget. Host RAM did not. The machine has 15.79 GB total, and available memory was about 1.7 GB before the load.

## 5. API verification — partial

The API container was restarted after the load. Startup log:

`Production serving wired (catalog_mode=full, products=367172, embeddings=367172, bm25=persisted_artifact)`

| Check | Result |
| --- | --- |
| `GET /api/v1/health` | **PASS.** HTTP 200, `{"status":"ok","service":"productiq","api_version":"v1"}`. |
| `GET /api/v1/ready` | **PASS.** HTTP 200. `catalog_data` status `ready`, message `full reference catalog loaded (367172 products, 367172 embeddings)`. |
| `POST /api/v1/search` | **FAIL for response bodies.** Before a scorer fix, one query used about 100% of one core for more than 5 minutes and never reached PostgreSQL. `BM25Scorer` was scanning each term's posting list once per candidate. The scorer now builds one posting map per term per query. Scores use the same frequencies. After that fix, uvicorn logged five `POST /api/v1/search` responses as HTTP 200 between 18:47:11Z and 18:47:27Z. This audit did not capture the response bodies, so product IDs, ranks, and catalog membership were **not** verified. |
| `GET /api/v1/products/{id}` | **NOT RUN** against the full catalog. |
| `POST /api/v1/recommendations` | **NOT RUN** against the full catalog. |
| Unknown product ID | **NOT RUN** against the full catalog. |

After those five access-log lines, `GET /api/v1/health` stopped answering. `docker restart` and `docker ps` then failed with Docker engine HTTP 500. Available memory had fallen to about 800 MB while the API process was near 2.45 GiB and Postgres near 1.57 GiB. Do not treat the five HTTP 200 lines as proof that search returned full-catalog products.

## 6. Frontend verification — inspection only

Frontend tests, typecheck, lint, and production build were **NOT RUN** in this preflight. They passed in the earlier storefront work and the frontend code was not changed here.

Configuration findings:

- **PASS:** the browser base URL comes from `NEXT_PUBLIC_PRODUCTIQ_API_URL`.
- **BLOCKED for public deploy:** if that variable is unset at build time, `frontend/lib/config.ts` falls back to `http://localhost:8000`.
- **PASS:** no credential or private env file is read by the frontend. `frontend/.env.local` is gitignored.
- **BLOCKED for public deploy:** Compose sets `APP_ENV` default `production`, and production CORS is empty unless `PRODUCTIQ_CORS_ALLOWED_ORIGINS` is set. Development defaults of localhost do not apply.
- Product cards use description, brand, and `image_url` from the API. The API does not provide a title or a live price. Empty or failed images already have a letter fallback in the existing card component. That fallback was not retested in the browser against full-catalog URLs.

## 7. Deployment readiness — BLOCKED

Do not deploy this tree yet.

Components that must be deployed together:

- Next.js frontend, built with the public API origin.
- FastAPI image `productiq-api:local`, rebuilt so it contains the validation and BM25 fixes. The running container only received `bm25.py` through `docker cp`. A new container from the current image will not have that fix.
- PostgreSQL 16 with pgvector, using the existing `productiq_pgdata` volume. Do not load the demo fixture over it.
- Processed artifacts mounted read-only: catalog Parquet, embeddings Parquet, BM25 pickle, and the embedding-selection file already copied into the image.
- BGE-small-en-v1.5 weights in `HF_HOME` on first startup, unless the cache is already present.

Storage, measured unless noted:

- Embeddings Parquet: 768 MB measured.
- BM25 pickle: 77 MB measured.
- Catalog Parquet: 37 MB measured.
- PostgreSQL database after load: 1,375 MB measured, including the 594 MB HNSW index.
- API process after model load: about 2.45 GiB measured.
- Postgres process after the vector load: about 1.57 GiB measured.
- Estimate: give the database host at least 8 GB RAM for API plus Postgres, and keep the Docker VM from competing with a full desktop session. This 16 GB machine was not enough once other processes were resident.

Environment variable names to set, values omitted:

- `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`
- `DATABASE_URL` (hostname `postgres` on the Compose network; port 5432 is not published)
- `APP_ENV`, `LOG_LEVEL`
- `PRODUCTIQ_ENABLE_PRODUCTION_SERVING`
- `PRODUCTIQ_PROCESSED_CATALOG_PATH`, `PRODUCTIQ_BM25_ARTIFACT_PATH`, `PRODUCTIQ_EMBEDDINGS_ARTIFACT_PATH`
- `PRODUCTIQ_CORS_ALLOWED_ORIGINS`, `PRODUCTIQ_CORS_ALLOW_CREDENTIALS`
- `HF_HOME`
- `PRODUCTIQ_API_PORT`
- `NEXT_PUBLIC_PRODUCTIQ_API_URL` at frontend build time

The API image is a CPU PyTorch image. Cold start includes unpickling the 77 MB BM25 index and loading BGE. The first full-catalog search before the scorer fix did not return within 5 minutes. Query latency after the fix was not measured from response bodies.

Frontend hosting can be a static/Next host. PostgreSQL, the API, and the artifact volume need a persistent container host. The AJIO files are a historical catalog. This preflight does not establish current stock or current prices.

## 8. Next actions

1. Restart Docker after freeing memory. Confirm `/api/v1/health` answers.
2. Rebuild `productiq-api:local` from the current source so the validation and BM25 fixes survive a new container.
3. Repeat the five searches plus one product, one recommendation, and one unknown ID. Record status, product IDs, and ranks, and confirm those IDs exist in `products`.
4. Only then set the public API URL and CORS origin and deploy. There is no public URL from this run.
