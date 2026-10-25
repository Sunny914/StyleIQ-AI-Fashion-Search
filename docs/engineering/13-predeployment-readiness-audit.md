# Pre-deployment readiness audit

Read-only pass on 25 October 2026. No loader, notebook, test suite, migration, or index build was run. No application code or configuration was changed. The only edits are the learning-to-rank sentence in the implementation map and this report.

Nothing here is a blanket "ready to deploy" result.

## 1. Executive summary

The running Compose database holds 367,172 `products` rows, 367,172 non-null embeddings, and zero null embeddings. The column type is `vector` with typmod `384`. The live HNSW index matches the 22 October 2026 manifest on name, operator class, `m`, `ef_construction`, and size in bytes. It does not match the 27 September manifest's recorded size.

The BM25 pickle the process resolves is on disk and was not opened. Local settings and the running container point at the same file through different path strings.

A catalog upsert can still overwrite a stored embedding with null. That conclusion is from the compiled statement, not from running the loader. Do not reload the catalog onto this database.

A public browser deployment is not configured. The running API is `APP_ENV=development` with the development CORS defaults. Production leaves CORS empty unless `PRODUCTIQ_CORS_ALLOWED_ORIGINS` is set. The storefront file points at `http://localhost:8010`, which is the port the current container publishes.

## 2. Correction made to the implementation map

**File:** `docs/engineering/02-repository-and-code-map.md`, search step 8.

**Removed claim:** `assert_retrieve_ranked_uses_baseline_path` rejects an experimental learning-to-rank stage.

**Replacement, matched to source:**

- `retrieve_ranked` calls `run_baseline_ranking_stage` when `ProductionRankingStageConfig(enabled=True)`. That stage calls `extract_features_for_request`, `normalize_features_for_query`, and `rank_candidates`.
- The call sits in `_ranked_search_from_pool` (`src/productiq/retrieval/production_pipeline.py`). That helper also calls `assert_retrieve_ranked_uses_baseline_path`.
- The assertion function in `src/productiq/ranking/hardening/production_safety.py` is `del stage`. It does not read `experimental_ltr` and does not reject learning-to-rank.
- `retrieve_ranked` does not call `rank_candidates_with_ltr`.
- Outside `inference.py`, the call sites are `src/productiq/ranking/ltr/comparison/evaluator.py` and `src/productiq/retrieval/evaluation/search_evaluation/ranking_variant_executor.py`. `rank_candidates_with_ltr_feature_rows` in the same inference module delegates to `rank_candidates_with_ltr`.

Classification: **Confirmed.** No other document was edited.

## 3. BM25 path

| Item | Result | Class |
| --- | --- | --- |
| Setting | `Settings.bm25_artifact_path`, alias `PRODUCTIQ_BM25_ARTIFACT_PATH`. Default `resources/processed/bm25` in `src/productiq/config/artifacts.py` | Confirmed |
| Resolver | `resolve_bm25_index_path`. A `.pkl` path is used as given. Otherwise it looks for `bm25_lexical_index.pkl` inside the configured directory, then beside the processed catalog | Confirmed |
| This checkout, no path override | Configured value `resources/processed/bm25`. That directory is absent. The sibling file exists, so the resolver returns `resources/processed/bm25_lexical_index.pkl` | Confirmed |
| File | Present. 77,062,647 bytes. Not opened | Confirmed |
| Running container | `PRODUCTIQ_BM25_ARTIFACT_PATH=/artifacts/processed/bm25_lexical_index.pkl`. Compose default in `docker-compose.yml`. The file is on the read-only mount and has the same byte size | Confirmed |
| Local versus container | Different strings. Same pickle: host `resources/processed/bm25_lexical_index.pkl`, container `/artifacts/processed/bm25_lexical_index.pkl`, mount `${PRODUCTIQ_ARTIFACTS_HOST:-./resources/processed}` | Confirmed |
| Overrides | Process environment and root `.env` do not set `PRODUCTIQ_BM25_ARTIFACT_PATH`. Container value is the Compose default. No unknown override was found for this variable | Confirmed |

Startup load remains `create_bm25_retriever_from_index_path` in `_resolve_lexical_retriever`, except fixture mode. This database is not fixture mode (zero `compose-demo-` ids).

## 4. HNSW index and manifests

Source definition: `create_product_embedding_hnsw_index` in `src/productiq/database/vector_catalog.py`. Name `ix_products_embedding_hnsw_cosine`. Column `products.embedding`. Operator class `vector_cosine_ops`. Parameters `m` 16 and `ef_construction` 64. `rebuild=False` returns when the index already exists.

Read-only queries against the already running `postgres` service (`psql` inside the container, no session settings changed):

```sql
SELECT indexname, indexdef
FROM pg_indexes
WHERE schemaname = 'public' AND tablename = 'products';

SELECT pg_relation_size('public.ix_products_embedding_hnsw_cosine');

SELECT atttypid::regtype, atttypmod
FROM pg_attribute
WHERE attrelid = 'public.products'::regclass AND attname = 'embedding';
```

Live index definition:

`CREATE INDEX ix_products_embedding_hnsw_cosine ON public.products USING hnsw (embedding vector_cosine_ops) WITH (m='16', ef_construction='64')`

`pg_relation_size` returned `623067136` bytes.

| Field | Live index | `resources/processed/product_vector_index.manifest.json` (2026-09-27) | `resources/benchmark/product_vector_index.manifest.loaded-2026-10-22.json` |
| --- | --- | --- | --- |
| Index name | `ix_products_embedding_hnsw_cosine` | same | same |
| Type / opclass | `hnsw` / `vector_cosine_ops` | same | same |
| `m` / `ef_construction` | 16 / 64 | 16 / 64 | 16 / 64 |
| Dimension | column typmod 384 | `vector_dimension` 384 | `vector_dimension` 384 |
| Size in bytes | 623,067,136 | 625,590,272 | 623,067,136 |
| Vectors recorded | 367,172 non-null rows | `product_count` 367,172 | `vectors_loaded` 367,172 |

Classification: **Confirmed** that the live index matches the 22 October manifest on every comparable field above, including size. The September manifest records a different size and a long index-build duration (`426` seconds versus `0.35` seconds in the October file). Those durations are manifest text, not something this pass timed.

Missing for a stronger identity: the manifests have no PostgreSQL index OID or checksum of the index pages. Size plus definition is the comparison this pass can make. It is enough to reject the September file as the description of the current index bytes.

## 5. Product and embedding consistency

Same read-only session. Query:

```sql
SELECT COUNT(*) AS product_rows,
       COUNT(*) FILTER (WHERE embedding IS NOT NULL) AS embeddings_non_null,
       COUNT(*) FILTER (WHERE embedding IS NULL) AS embeddings_null,
       COUNT(DISTINCT product_id) AS distinct_product_ids,
       COUNT(*) FILTER (WHERE product_id LIKE 'compose-demo-%') AS fixture_ids
FROM products;

SELECT vector_dims(embedding) FROM products WHERE embedding IS NOT NULL LIMIT 5;
```

Constraints: `products_pkey` is `PRIMARY KEY (product_id)`. `ck_products_source_ajio` requires `source = 'ajio'`.

| Check | Result | Class |
| --- | --- | --- |
| Product rows | 367,172 | Confirmed |
| Non-null embeddings | 367,172 | Confirmed |
| Null embeddings | 0 | Confirmed |
| Distinct `product_id` | 367,172, and the primary key forbids duplicates | Confirmed |
| Fixture ids | 0 | Confirmed |
| Column type | `vector`, typmod 384 | Confirmed |
| Sample of five `vector_dims` | 384, 384, 384, 384, 384 | Confirmed for those five rows |

A matching count does not prove every vector is finite, L2-normalized, or from the recorded BGE revision. This pass did not scan all 367,172 vectors and did not run a similarity search. Classification of full-vector validity: **Requires runtime verification** beyond the type, the counts, and the five-row sample.

## 6. Catalog reload safety

Static reading of `ProductCatalogLoader._upsert_records` and `_dataframe_chunk_to_records` in `src/productiq/database/loaders/catalog_loader.py`. The statement was compiled with the PostgreSQL dialect in an earlier inspection and was not executed.

1. The insert column list is the 22 names in `PROCESSED_COLUMN_ORDER`.
2. `embedding` is omitted from that insert. It is not a bound parameter.
3. The conflict `SET` includes `embedding = excluded.embedding` together with every other column except `product_id`.
4. `Product.embedding` is nullable and has no server default. PostgreSQL fills an omitted insert column with null.
5. On `product_id` conflict, the assignment writes that null over an existing vector.
6. The loader does not exclude `embedding` from `update_columns`. `load_processed_catalog` does not follow the upsert with the embedding `UPDATE`. `load_runtime_catalog` does call `build_product_vector_index` when an embeddings path is passed. The CLI passes that path for `full` and `partial`. A catalog-only call has no such protection.

Classification: **Confirmed risk** as static analysis. Not a runtime observation on this database. The live table currently has zero null embeddings, which only describes the present rows.

Smallest safe remediation, not implemented: stop assigning `embedding` in the conflict `SET`, so a metadata upsert leaves the vector column untouched. Until that change exists, do not run `load_processed_catalog` or a catalog-only `load_runtime_catalog` against this volume. A full CLI load that continues into `build_product_vector_index` is still a rewrite of every vector and was not authorized here.

## 7. Deployment-critical configuration

Values below are non-secret. `DATABASE_URL` and `POSTGRES_PASSWORD` are set in the process environment. Their contents were not printed. Root `.env` contains `DATABASE_URL` and was not quoted.

| Mechanism | Where | What was verified | Implication | Class |
| --- | --- | --- | --- | --- |
| Production serving | `Settings.enable_production_serving`, default `False`. Compose default `1`. This process and the running container are `1` | The API container is on the production wiring path | Ready for this local Compose process. A clean shell without the variable stays on the hollow app | Confirmed |
| Database | `DATABASE_URL` required by Compose. Image `pgvector/pgvector:pg16`. Volume `productiq_pgdata`. Port 5432 is not published | The healthy `postgres` service answered the queries above. Data survives container restart because of the named volume | Ready for this machine. Do not point a load at this volume | Confirmed |
| BM25 path | Section 3 | Pickle present on the mount | Ready for this container | Confirmed |
| BGE load | `create_bge_small_en_v15_encoder` loads `BAAI/bge-small-en-v1.5` from the Hugging Face cache. Compose sets `HF_HOME=/tmp/hf-cache` and does not mount it | A new container can miss the cache and download on startup. The Dockerfile does not fetch weights at build time | Requires the cache or a download on first boot. Not verified that `/tmp/hf-cache` currently holds the revision | Requires runtime verification |
| CORS | `default_cors_origins_for_environment`. Development: `http://localhost:3000` and `http://127.0.0.1:3000`. Any other `APP_ENV`: empty unless `PRODUCTIQ_CORS_ALLOWED_ORIGINS` is set | Running container `APP_ENV=development`. The variable is unset. Root `.env` sets `APP_ENV=development` | Local Next.js on port 3000 can call the API. `APP_ENV=production` with this `.env` would send no CORS origins | Requires configuration before a public origin |
| Frontend API URL | `frontend/lib/config.ts` defaults to `http://localhost:8000` when `NEXT_PUBLIC_PRODUCTIQ_API_URL` is empty. `frontend/.env.local` sets `http://localhost:8010` | `docker compose port` shows `0.0.0.0:8010`. Root `.env` does not set `PRODUCTIQ_API_PORT`. Compose's file default is `8000` | The current container matches `.env.local`. A new Compose up without the port variable would publish 8000 and the storefront would still call 8010. Next inlines `NEXT_PUBLIC_*` at build time | Requires configuration. The port override that produced 8010 is not in the current `.env` |
| Compose health | Postgres: `pg_isready`. API image: HTTP GET `/api/v1/health` in the Dockerfile. Compose `productiq-api` has `depends_on` postgres healthy and no Compose healthcheck of its own | Both services reported healthy | Local stack is up. Health does not prove search or embeddings | Confirmed for liveness only |
| Persistence | Named volume `productiq_pgdata`. Artifact mount is read-only | Rows and the pickle survived this inspection | Do not remove the volume. Do not treat `/tmp/hf-cache` as durable | Confirmed |
| Written instructions | `docs/architecture/deployment-configuration.md` and `docs/architecture/deployment-runtime-contract.md` exist | They describe env contracts. They do not name a public host, and this pass did not treat them as a deploy procedure | A public runbook is still a configuration task, not an unwritten blank | Requires configuration |

No cloud size or free-tier capacity was assumed. This pass did not choose a host.

## 8. Tests inspected but not run

These files were read for what they assert. None were executed. Existence is not a pass.

| File | What the source of the test asserts | What it does not assert |
| --- | --- | --- |
| `tests/ranking/test_ltr_inference_and_comparison.py` `test_retrieve_ranked_still_not_ltr` | The text of `retrieve_ranked` does not contain `rank_candidates_with_ltr` | It does not inspect `_ranked_search_from_pool` or the body of the guard |
| `tests/ranking/test_ranking_hardening.py` `test_production_retrieve_ranked_no_ltr` | Same text check | Same gap |
| `tests/ranking/test_ltr_training.py` `test_production_baseline_not_integrated_in_retrieve_ranked` | `retrieve_ranked` source has no `ltr` substring and no `train_ltr_model` | The guard call lives in the helper, so this test can pass while the guard remains a no-op |
| `tests/ranking/test_ranking_hardening.py` `test_production_default_baseline_mode` | Default experimental LTR flag is false. `resolve_production_ranking_mode` returns the baseline version when the stage is enabled | It does not call `retrieve_ranked` |
| `tests/database/test_catalog_loader.py` | Chunk size, nullable attribute conversion, Parquet validation | No assertion about `embedding` on conflict. `tests/database/test_catalog_integration.py` also has no `embedding` assertion |
| `tests/retrieval/test_vector_index_loader.py` | Official artifact validation and a missing-file rejection | Not a live 367,172-row load |
| `tests/config/test_runtime_deployment_contract.py` | BM25 legacy path beside the catalog, import of `create_app` without a Postgres connection | Uses temp files, not this pickle |
| `tests/api/test_production_stack_contract.py` | Default `create_app` does not enable production serving. Catalog mode labels. The loader is a separate entry | Not a test of this container |
| `tests/api/test_readiness.py`, `tests/api/test_production_safety.py` | Unconfigured services are not ready. Health is liveness. Ready responses omit secrets | They do not re-count this database |

## 9. Open questions

| Question | Class |
| --- | --- |
| Are all 367,172 embeddings finite and unit-norm, or only well-typed? | Requires runtime verification. A full scan was not run |
| Does `/tmp/hf-cache` in the running container already contain `BAAI/bge-small-en-v1.5` revision `5c38ec7c405ec4b44b94cc5a9bb96e735b38267a`? | Requires runtime verification. The cache directory was not listed |
| Why is the running API published on 8010 when the current `.env` has no `PRODUCTIQ_API_PORT`? | Blocked by missing information. The mapping is a fact. The variable that created it is not in the current env file |
| How many CSV duplicates the original catalog build removed | Still open. Not needed to serve the loaded table |
| Notebooks not read cell by cell | Still open. Not a deploy blocker |
| Whether `SET hnsw.ef_search` survives on a pooled connection | Still open. This pass did not set the parameter |
| Numeric baseline ranker weights | Still open. Not required to keep the current process serving |
| Whether `enable_*_generator` is read outside `src/productiq/recommendation` | Still open. Production passes the three generators directly |

## 10. Recommended next actions

1. Do not run a catalog upsert against `productiq_pgdata`. The conflict update can null `embedding`. The smallest code change, when you authorize one, is to omit `embedding` from that `SET`.
2. Before a public site, set `PRODUCTIQ_CORS_ALLOWED_ORIGINS` to the real origin and set `NEXT_PUBLIC_PRODUCTIQ_API_URL` to the public API origin at frontend build time. Keep `APP_ENV=production` from inheriting an empty CORS list.
3. Record `PRODUCTIQ_API_PORT` in the env file if 8010 must survive a new `docker compose up`. The running map is 8010. The file default is 8000. The storefront file calls 8010.
4. Confirm the BGE files under the container `HF_HOME`, or accept a download on the next container start. Do not bake a plan that assumes `/tmp/hf-cache` survives.
5. Leave the HNSW index as it is. `rebuild=True` would drop `ix_products_embedding_hnsw_cosine`. The live definition already matches the October manifest.
6. If you need stronger embedding proof later, sample `vector_dims` more widely or check norms in a read-only query. Do not start with a catalog-wide nearest-neighbor search.
