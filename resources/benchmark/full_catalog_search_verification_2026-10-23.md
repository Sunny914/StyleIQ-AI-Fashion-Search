# Full-catalog search verification — 2026-10-23

Recovery after `resources/benchmark/full_catalog_preflight_2026-10-22.md`. The catalog was not reloaded. No volume was deleted, no table was dropped or truncated, and the HNSW index was not rebuilt. Nothing was committed or pushed. The site is not publicly deployed. Frontend tests and the frontend build were not run.

## Git status — PASS

- Branch: `main`
- HEAD: `34dda60d9a049b60003d2c4f1f47c07dfe01e549`
- Uncommitted Phase 15B, 15C, and 16 files remain in the working tree.
- Scorer change kept: `src/productiq/retrieval/bm25.py` adds `_term_frequency_maps` on `BM25Scorer` and resolves term frequency from that map. IDF, length normalization, and the BM25 formula are unchanged. Each `score_bm25_lexical_query` call constructs a new scorer, so the map is per query.
- Targeted tests: `tests/retrieval/test_bm25.py` and `tests/retrieval/test_bm25_retriever.py` — **36 passed, 1 skipped** in 0.67s. The skip is the persisted-index smoke test.
- `ruff check` on `bm25.py`, `catalog_validation.py`, and `load_runtime_catalog.py` passed.

## Docker recovery — PASS

Docker Engine 29.8.1 answered. Containers before the API recreate:

- `productiq-postgres-1` — up 3 hours, healthy, image `pgvector/pgvector:pg16`
- `productiq-productiq-api-1` — stopped only for the image rebuild

Volume `productiq_productiq_pgdata` is mounted at `/var/lib/postgresql/data`. It was not removed. Postgres was not recreated.

Host memory at inspection: 15.79 GB total, about 1,096 MB available. Disk: C: 179.91 GB free, E: 349.05 GB free.

## Catalog counts — PASS

Queried before the API rebuild. Data was not reloaded.

- Products: 367,172
- Distinct product IDs: 367,172
- Embeddings: 367,172
- Null embeddings: 0
- Distinct embedding dimensions: 1
- Sample dimension: 384
- Database size: 1,375 MB

## API image rebuild — PASS

`docker compose build productiq-api` exited 0. Image: `productiq-api:local` (`sha256:002acea1121ac2a89847d118dd1ea418be3337882c0be2e4412bd011d236d698`).

A one-off container from that image imported `productiq.retrieval.bm25` and confirmed `_term_frequency_maps` is in `BM25Scorer`.

`docker compose up -d --no-deps --force-recreate productiq-api` recreated only the API container. Postgres stayed up. The running container uses the same image ID, and `docker exec` confirmed the running module also contains `_term_frequency_maps`.

Startup log:

`Production serving wired (catalog_mode=full, products=367172, embeddings=367172, bm25=persisted_artifact)`

## Health and readiness — PASS

- `GET /api/v1/health` — HTTP 200, `{"status":"ok","service":"productiq","api_version":"v1"}`
- `GET /api/v1/ready` — HTTP 200. `catalog_data` is `ready`: `full reference catalog loaded (367172 products, 367172 embeddings)`.

## Search — PASS

One request. Client timeout 120 seconds. No retry.

- HTTP 200
- Elapsed: **13.21 seconds**
- Query: `navy cotton shirt`
- `top_k`: 5
- `returned_count`: 5
- `request_id`: `e8d0cb0e-6d62-4c1b-93ca-1af6303fd707`

```json
{
  "query": "navy cotton shirt",
  "top_k": 5,
  "results": [
    {"product_id": "462494766003", "rank": 1},
    {"product_id": "441029880002", "rank": 2},
    {"product_id": "463356013005", "rank": 3},
    {"product_id": "460618402005", "rank": 4},
    {"product_id": "463920617004", "rank": 5}
  ],
  "request_id": "e8d0cb0e-6d62-4c1b-93ca-1af6303fd707",
  "returned_count": 5
}
```

PostgreSQL matches for those IDs, all with a 384-dimensional embedding:

| Rank | Product ID | Brand | Gender | Type | Description |
| --- | --- | --- | --- | --- | --- |
| 1 | 462494766003 | lindbergh | Men | shirt | Cotton Shirt with Curved Hem |
| 2 | 441029880002 | trends | Women | shirt | Cotton Shirt with Curved Hem |
| 3 | 463356013005 | max | Men | shirt | Floral Print Cotton Shirt |
| 4 | 460618402005 | celio | Men | shirt | Reversible Cotton Shirt |
| 5 | 463920617004 | code-by-lifestyle | Men | shirt | Checked Cotton Slim Fit Shirt |

The response is valid: five ranked IDs, every ID present in the loaded catalog. It is not empty and not malformed.

## Resource usage — PASS, with limited headroom

| Sample | Value |
| --- | --- |
| Host available memory before the search | 822 MB |
| Host available memory after the search | 806 MB |
| API memory after the search | 2.308 GiB, CPU 0.33% |
| Postgres memory after the search | 891.6 MiB, CPU 0.02% |
| Search elapsed time | 13.21 s |
| Timeout, OOM, restart, or database connection error | none observed |
| Access log | `POST /api/v1/search` HTTP 200 |

A mid-request CPU sample was not captured; the request finished before that sample ran. After the response, both containers were idle. No second search was sent.

The previous failure was BM25 scoring that scanned every posting for every candidate and did not reach PostgreSQL within five minutes. This request returned catalog products in 13.21 seconds, so that stall is gone. The 13.21 seconds still includes query embedding plus lexical and vector retrieval. There is no separate timer in the HTTP body, so this run does not assign the time to BM25 versus HNSW.

Host available memory stayed near 800 MB. That is enough for this one request and too little to treat the machine as a stable public host.

## Remaining blockers

- Public deployment was not attempted.
- Frontend verification was **NOT RUN**.
- Production still needs `NEXT_PUBLIC_PRODUCTIQ_API_URL` at frontend build time and `PRODUCTIQ_CORS_ALLOWED_ORIGINS` on the API.
- This desktop should not be the public API host while available memory stays near 800 MB.

No further scorer or index change is justified from this single 13-second response.

## Next step

Put the API and the existing Postgres volume on a host with at least 8 GB free for those two processes, then set the public API URL and CORS origin. Do not reload the catalog.
