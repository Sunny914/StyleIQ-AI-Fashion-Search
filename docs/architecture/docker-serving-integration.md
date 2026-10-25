# Phase 15C — Docker serving integration

**Scope:** Wire the Compose API to real search, product-detail, and recommendation services using PostgreSQL/pgvector plus mounted runtime artifacts. Next.js and cloud deploy remain later phases.

## Data flow

```text
Processed catalog parquet  --explicit load-->  products table
Embedding parquet          --explicit load-->  products.embedding vector(384) + HNSW
BM25 pickle (full)         --startup mount-->  BM25Retriever
  or fixture descriptions  --startup build-->  BM25Retriever (compose-demo-* only)

Query
  -> query representation
  -> BM25 + BGE/pgvector
  -> RRF hybrid
  -> PostgreSQL hard filters
  -> baseline ranking (LTR stays experimental / not the HTTP default)
  -> Search API response (product_id + rank only)
```

## Reused modules

| Concern | Module |
|---------|--------|
| Catalog upsert | `productiq.database.catalog_pipeline.load_processed_catalog` |
| Embedding load + HNSW | `productiq.retrieval.vector_index_builder.build_product_vector_index` |
| Schema bootstrap | `productiq.database.bootstrap_compose` |
| BM25 | `create_bm25_retriever_from_index_path` / in-memory fixture index |
| Semantic | `create_semantic_retriever_from_engine` |
| Hybrid | `create_rrf_hybrid_retriever` + `ProductionRetrievalPipeline` |
| Recommendations | `build_production_recommendation_pipeline` |
| Product read | `PostgresProductCatalogReadProvider` |

## Explicit load (never on ordinary API startup)

Fixture (3 labeled `compose-demo-*` rows, **not** the 367k catalog):

```bash
docker compose --profile load run --rm catalog-load
# or
docker compose run --rm productiq-api python -m productiq.database.load_runtime_catalog --mode fixture --json
```

Full reference catalog (operator-driven; long-running):

```bash
# PRODUCTIQ_CATALOG_LOAD_MODE=full
docker compose --profile load run --rm catalog-load \
  python -m productiq.database.load_runtime_catalog --mode full --enforce-official-checksums --json
```

Catalog upserts are restartable (`ON CONFLICT product_id`). Embeddings `UPDATE` by `product_id`.

## API serving flag

`PRODUCTIQ_ENABLE_PRODUCTION_SERVING=1` (Compose default for `productiq-api`).

First start downloads `BAAI/bge-small-en-v1.5` into `HF_HOME` (Compose default `/tmp/hf-cache`, writable by the non-root image user). A named cache volume is not used because Docker creates it as root.

Without the flag, `create_app()` stays the Phase 13/15A hollow shell (no DB, no BM25, no model load). Import time never opens PostgreSQL.

## Readiness

`/api/v1/ready` includes `catalog_data`:

| mode | meaning |
|------|---------|
| `fixture` | Labeled demo rows only |
| `full` | 367,172-row reference catalog |
| `partial` | Some other row count |
| `empty` / `not_checked` | Not loaded / not wired |

A database connection alone does not mark search ready; search/recommendation/product must be configured.

## Artifacts

Processed parquet, BM25 pickle, and embeddings stay **out of the API image**. Compose mounts `./resources/processed` read-only at `/artifacts/processed`. The small frozen embedding-model selection JSON is copied into the image (`resources/embedding/`) because query encoding must know the BGE contract; it is not the 730MB embedding parquet.

## Storefront

The Next.js app lives in `frontend/` and calls this API with `NEXT_PUBLIC_PRODUCTIQ_API_URL`. Search and recommendation responses stay ID-and-rank payloads; the storefront loads display fields from `GET /api/v1/products/{id}`. Browser calls need `APP_ENV=development` or an explicit `PRODUCTIQ_CORS_ALLOWED_ORIGINS` list. Credentials stay disabled.

## Known limits

- Full 367k load is supported by the loader but is not part of default `compose up`.
- Fixture embeddings are 384-d unit vectors; lexical search is the reliable fixture path unless a real encoder is used against BGE embeddings.
- Experimental LightGBM LTR is **not** the HTTP default (`retrieve_ranked` uses baseline ranking).
