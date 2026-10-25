# Documentation consistency audit

This is an audit of the engineering notes. It does not rewrite them. No application file, test, configuration, diagram, database, or artifact was changed. No notebook, loader, or index build was run. No test suite was executed.

One check was a local compile of the catalog upsert statement. That compile does not open PostgreSQL and does not run the statement.

## 1. Documents reviewed

| Document | Role in the set |
| --- | --- |
| `docs/engineering/02-repository-and-code-map.md` | Implementation map. Written first |
| `docs/engineering/03-learning-assessment.md` | Study plan. Already flags one map error |
| `docs/engineering/04-http-routes-and-error-handling.md` | HTTP surface |
| `docs/engineering/05-data-contracts-and-dtos.md` | Models and mappers |
| `docs/engineering/06-database-operations-and-transactions.md` | Reads, upserts, embedding updates |
| `docs/engineering/07-application-startup-and-dependency-injection.md` | `create_app` and `app.state` |
| `docs/engineering/08-search-request-walkthrough.md` | One search, then product-card fetches |
| `docs/engineering/09-product-details-and-recommendations.md` | Detail `GET` and recommendation `POST` |
| `docs/engineering/10-offline-data-and-artifact-lifecycle.md` | Files, database load, startup, request |
| `docs/engineering/11-rebuilding-productiq-from-scratch.md` | Dependency order for a reconstruction |

Documents 04 through 11 agree with each other on the live paths. Document 02 agrees on those paths except for one sentence about learning-to-rank. Document 03 records that exception and does not repeat it as fact.

## 2. Source files inspected for verification

Checked against the notes during this audit:

- `src/productiq/api/app.py`, `routes/v1_router.py`, `routes/health.py`, `routes/search.py`, `routes/products.py`, `routes/recommendations.py`, `dependencies.py`
- `src/productiq/serving/versioning.py` (`SERVING_API_MAJOR_VERSION = "v1"`)
- `src/productiq/serving/config.py` (`DEFAULT_API_MAX_TOP_K = 100`, `DEFAULT_API_MAX_QUERY_LENGTH = 512`)
- `src/productiq/ranking/hardening/production_safety.py` (`assert_retrieve_ranked_uses_baseline_path`)
- `src/productiq/retrieval/production_pipeline.py` (`retrieve_ranked` calls `run_baseline_ranking_stage`)
- Call sites of `rank_candidates_with_ltr`: `ranking/ltr/inference.py`, `ranking/ltr/comparison/evaluator.py`, `retrieval/evaluation/search_evaluation/ranking_variant_executor.py`. None are `production_pipeline.py`
- `src/productiq/database/loaders/catalog_loader.py` (`_upsert_records`, `_dataframe_chunk_to_records`)
- `src/productiq/database/models/product.py` (`embedding` nullable, no server default)
- `src/productiq/retrieval/vector_index_loader.py` (alignment batches and `_UPDATE_EMBEDDING_SQL`)

The compile used the same insert and conflict `SET` as `_upsert_records`, rendered with the PostgreSQL dialect. It was not sent to a database.

Earlier notes already traced retrieval, recommendations, startup, and the manifests. This audit did not reopen every file they cite. Where a later note and the source agree, this report treats that agreement as the reference and calls out only the mismatches.

## 3. Findings by dimension

### 3.1 Endpoint and API consistency

The five routes are the same in every note that lists them, and they match the routers mounted at `SERVING_API_ROUTE_PREFIX` (`/api/v1`):

| Method and path | Handler | Public model |
| --- | --- | --- |
| `GET /api/v1/health` | `get_health` | `HealthResponse` |
| `GET /api/v1/ready` | `get_ready` | `ReadinessResponse` |
| `POST /api/v1/search` | `post_search` | `SearchApiRequest` → `SearchApiResponse` |
| `GET /api/v1/products/{product_id}` | `get_product` | `ProductApiResponse` |
| `POST /api/v1/recommendations` | `post_recommendations` | `RecommendationApiRequest` → `RecommendationApiResponse` |

Public fields agree across 04, 05, 08, 09, and 11.

- Search results are `product_id` and `rank`. The echoed `query` is normalized text. `top_k` is the caller's value.
- Product JSON is `product_id`, `brand`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`, and `request_id`. `brand_normalized` stops in the read model. `embedding` and prices stay on the row.
- Recommendation items are `product_id`, `rank`, and `recommendation_score`. The card does not render the score. 09 and 11 both say this.
- Caps: default `top_k` maximum `100`, query length `512`. 04, 05, and 08 state those numbers. 02 and 03 still say the defaults were not copied. That is a stale open item in the early notes, not a disagreement about the values. Source constants confirm 100 and 512.
- Missing product: `404`, message `Product not found.`
- Missing seed: `404`, message `Seed product not found`.
- `GET /api/v1/ready` has no custom status on the decorator, so a handler return is HTTP 200 even when the body status is `not_ready`. 04 is explicit that a test whose only assertion is that pair was not isolated. The status conclusion still follows from the decorator.

**Minor imprecision.** 04's route table names `ProductionRecommendationServingService.recommend` as the production path. The object stored on `app.state` is `_PerRequestRecommendationServingService`. Its `recommend` builds `ProductionRecommendationServingService` for that call. 07 and 09 describe the wrapper. The route itself only calls `service.recommend`.

### 3.2 Architecture and call-path consistency

These descriptions match across 02, 07, 08, 09, and 11, and they match the source that was re-read.

- `create_app` is a factory. Production wiring runs only when `PRODUCTIQ_ENABLE_PRODUCTION_SERVING` is on and services were not injected. Settings default the flag to false. Compose defaults it to `1`.
- Services are stored on `app.state`. Routes take them through `Depends` (`get_search_service`, `get_product_service`, `get_recommendation_service`).
- HTTP product detail uses `PostgresProductCatalogReadProvider.get_product`. It does not call `ProductRepository`. 02, 05, 06, and 09 agree. `ProductRepository` still exists for counts and other reads.
- Search is `ProductionSearchServingService.search` → `retrieve_ranked`.
- `rank_candidates_with_ltr` is not on that path.

**Critical contradiction.** Section 3 of `02-repository-and-code-map.md` says `assert_retrieve_ranked_uses_baseline_path` rejects an experimental LTR stage. The function body is `del stage` and a return. The same file's component table says LTR is not called by `retrieve_ranked`, which is the accurate half. 03, 08, and 11 correct the guard. A reader who stops at section 3 of the map will believe a safety check exists that the source does not implement.

Redis is absent from `create_app`. 02 and 11 say the frozen architecture diagram still draws it. No note tells a reader to implement Redis for the live path.

### 3.3 Search-flow consistency

08 is the detailed walkthrough. 05, 06, 07, and 11 use the same order. 02's search list matches until the LTR sentence.

| Step | Agreed description | Source check |
| --- | --- | --- |
| Storefront `top_k` | `SEARCH_TOP_K` is 12 | Used consistently in 05, 08, 11 |
| Pool | `candidate_pool_top_k` default 50, and a request `top_k` above the pool becomes `ValueError` then HTTP 400 | 08 and 11 |
| Retriever order | Lexical BM25, then semantic. Both run. An exception from either fails the request | 08 and 11 |
| Fusion | Reciprocal rank, `k` 60, then `product_id` ascending | 08 and 11 |
| Filter | After fusion, only when a constraint is active. Storefront Men/Women makes it active | 08 |
| Rank | `run_baseline_ranking_stage` because production sets `enabled=True`. Then cut back to the caller's `top_k` | `retrieve_ranked` → `_ranked_search_from_pool` |
| Response | `product_id` and `rank` only | Mappers, 05 and 08 |
| Card fetches | `loadProductCards` with `PRODUCT_LOOKUP_CONCURRENCY` of 4 | 05 and 08 |

No second document claims a different pool, a different fusion constant, or that search JSON includes `bm25_score`.

### 3.4 Database and transaction consistency

06, 10, and 11 agree, and the loader matches them.

- Catalog load: one session for the file, `autoflush=False`, `autocommit=False`, `expire_on_commit=False`.
- Parquet chunk default `10000`. `commit()` after each chunk. `rollback()` only in the exception handler, so earlier commits remain.
- Statement size: `65535 // 22` because the inserted dict has 22 processed columns.
- Embedding updates: `_UPDATE_EMBEDDING_SQL` inside `engine.begin()` per batch. Default batch `5000`. A `rowcount` of 0 raises inside that transaction.
- Alignment before updates: Parquet reads of `DEFAULT_EMBEDDING_READ_BATCH_SIZE` (10000) and existence checks of `_CATALOG_EXISTENCE_BATCH_SIZE` (10000). 06 states both. They are equal numbers and different constants.
- No application `DELETE` of `products` rows. 06 states this. Later notes do not invent one.
- `create_app` does not call `load_runtime_catalog`. 02, 03, 06, 07, 10, and 11 agree.

**Catalog upsert and existing embeddings.** This audit compiled the statement. The rendered SQL is:

- `INSERT INTO products` lists the 22 processed columns only. `embedding` is not in that list and is not a bound parameter.
- `ON CONFLICT (product_id) DO UPDATE SET` includes every other mapped column, ending in `embedding = excluded.embedding`.

`Product.embedding` is nullable and the model sets no server default. PostgreSQL fills a column omitted from `INSERT` with its default, which is null. `EXCLUDED` is that proposed row, so the conflict assignment writes null over an existing vector.

Conditions:

- The id already exists. A new id is inserted with a null embedding because the column is omitted. That is expected before the embedding `UPDATE`.
- `load_processed_catalog` performs the upsert and does not load vectors.
- `load_runtime_catalog` in `full` or `partial` mode calls `build_product_vector_index` only when an embeddings path is passed. The CLI passes that path for those modes, so a full CLI run is written to null the column and then `UPDATE` it again.
- A catalog-only rerun leaves the nulls until a later embedding load.

The statement was compiled, not executed. No live row was observed changing. The SQL text plus the column definition establish the outcome of the statement if it runs. 06, 10, and 11 already describe this. 02's CRUD table says the upsert updates every column except `product_id` and does not spell out the null embedding. That is a gap in the map, not a conflicting claim.

`SET hnsw.ef_search` on a pooled connection is still described in 06 as not fully verified for pool lifetime. This audit did not revisit that.

### 3.5 Offline and online lifecycle consistency

10 and 11, with 02's section 7, tell the same dependency story.

| Artifact | Produced from | Consumed by |
| --- | --- | --- |
| CSV | Vendor file, CP1252 | `AjioDataLoader` |
| `product_catalog.parquet` | Clean, normalize, dedupe, canonical, attributes, `ProcessedDatasetWriter` | Representation generator and `load_from_parquet` |
| `product_representations.parquet` | Processed catalog | Embedding generator and BM25 builder |
| `product_embeddings.parquet` | `semantic_text`, no query prefix | `load_product_embeddings_into_catalog` |
| `bm25_lexical_index.pkl` | `lexical_text` | Startup, except fixture mode |
| `products` rows | Catalog upsert | Filters, detail, recommendations, fixture BM25 |
| `products.embedding` and HNSW | Embedding `UPDATE`, then `create_product_embedding_hnsw_index` | `search_products_by_embedding` |
| Process memory | Unpickle plus `create_bge_small_en_v15_encoder` | Each search and recommendation request |

Embeddings and BM25 both read the representation file. Neither reads the other's output. The vector `UPDATE` requires catalog ids first. Startup does not rebuild those files.

Notebook order is marked inferred everywhere it appears. The notes that were specific (09, 19, 24, 29, 84) match the function inputs. 02 says notebooks were not read cell by cell. 10 and 11 name the notebooks that were searched. That is a scope difference, not a conflict.

Two on-disk vector manifests (2026-09-27 under `resources/processed/`, 2026-10-22 under `resources/benchmark/`) are reported as different files. No note claims they are the same index. Which one matches the live database is still open.

### 3.6 Error handling and operational behavior

04 is the detailed error note. 08, 09, and 11 repeat the same statuses. No note contradicts another on these cases.

| Case | Documented result | Status of the claim |
| --- | --- | --- |
| Invalid JSON, extra fields, `top_k` of 0 or above the cap | 400 `INVALID_REQUEST`, message `Request validation failed` | Consistent. Tests are cited and were not re-run |
| `top_k` 51–100 | Passes the API model, then `ValueError` from the pool check, still 400 | 08. Consistent with the pool default of 50 |
| Missing product | 404 `Product not found.` | Consistent |
| Missing seed | 404 `Seed product not found` | Consistent. Different message from a missing product |
| Empty recommendation candidates | 200 and an empty list | 09. The product page keeps the product |
| Generator exception with `continue_on_generator_failure=False` | `RecommendationError`, HTTP 500 | 09. Production rejects `True` |
| Unhandled exception | 500, message `An unexpected error occurred` | 04 |
| Empty catalog or missing BM25 file outside fixture mode | `ConfigurationError` before the app exists, mapped as 503 if it surfaces as a request error | 07 and 11 |
| Health | 200 from config, no catalog query | Consistent |
| Readiness counts | The startup snapshot on `ApplicationServices` | 06 and 07 |
| BM25 file replaced while the process runs | The in-memory index stays | 07, 08, 10, 11 |
| Unknown-path 404 and method 405 JSON bodies | Status codes are tested. 04 says the body was not asserted to be `ApiErrorEnvelope` | Still unresolved. Not contradicted |

### 3.7 Duplication and readability

The series repeats pool size, commit boundaries, the five routes, and the "startup does not load the catalog" rule. That repetition is useful if each note is read alone. It becomes a risk only where an early sentence was not updated, which is the LTR line in 02.

Terms that need one shared definition, because later notes redefine them:

- **Seed.** The recommendation product id. Not a search query.
- **Pool versus `top_k`.** Pool is 50 inside retrieval and recommendation generation. `top_k` is what the client asked for (12 for search, 8 for recommendations in the storefront).
- **Artifact versus column.** `product_embeddings.parquet` is the file. `products.embedding` is the column.
- **DTO.** The Pydantic object on the HTTP boundary. `Product` and `RetrievalCandidate` are not DTOs.
- **Baseline ranker.** Search uses `run_baseline_ranking_stage`. Recommendations use `rank_recommendations`. The names are close and 09 already separates them.

Missing cross-references:

- 02 section 3 should point at 03, 08, and this audit for the LTR correction.
- 02's upsert row should point at 06 and 10 for `embedding = excluded.embedding`.
- 04's recommendation row should point at 07 for `_PerRequestRecommendationServingService`.
- 02 and 03's "defaults not copied" lines should point at `DEFAULT_API_MAX_TOP_K` and `DEFAULT_API_MAX_QUERY_LENGTH`.

A diagram would help in 02, which has no picture of offline files versus startup versus a request. 07, 08, 10, and 11 already have Mermaid diagrams. Do not add another architecture diagram to `docs/architecture/`.

`SET hnsw.ef_search` and the exact baseline feature weights are explained more briefly than the call order. They do not block a correct reading of the request path.

## 4. Contradictions

| Severity | Where | What it says | What the other notes and the source say |
| --- | --- | --- | --- |
| Critical factual | `02-repository-and-code-map.md`, search step 8 | `assert_retrieve_ranked_uses_baseline_path` rejects an experimental LTR stage | The function only executes `del stage`. 03 states the correction. 08 and 11 repeat it. `retrieve_ranked` calls `run_baseline_ranking_stage` and does not call `rank_candidates_with_ltr` |
| Minor | `02-repository-and-code-map.md`, same file, component table versus step 8 | The table says LTR is not called by `retrieve_ranked` | That half matches the source. The two sentences inside 02 disagree with each other |
| Minor | `04-http-routes-and-error-handling.md`, recommendations row | Names `ProductionRecommendationServingService.recommend` as the production callee | 07 and 09: `app.state` holds `_PerRequestRecommendationServingService`, which constructs the production service per request |
| Stale open item, not a value conflict | `02` unresolved list and `03` section on defaults | Numeric `api_max_top_k` and `api_max_query_length` were not copied | 04, 05, and 08 copy 100 and 512. `src/productiq/serving/config.py` defines those defaults |

No contradiction was found on route paths, search response fields, fusion order, pool size, storefront `top_k`, card concurrency, catalog commit scope, embedding `UPDATE` batch size, the absence of product `DELETE`, or startup skipping `load_runtime_catalog`.

## 5. Unresolved-question register

| Question | Why it matters | Current evidence | What would resolve it | Risk | Blocks deployment |
| --- | --- | --- | --- | --- | --- |
| Does a catalog upsert clear existing embeddings? | A metadata reload can make semantic search skip every updated id | Compiled SQL omits `embedding` from `INSERT` and sets `embedding = excluded.embedding`. The column has no server default, so the proposed value is null. Not executed on a database | Run the statement against a disposable database with one row that already has a vector, then `SELECT embedding IS NULL`. Do not use the loaded catalog database | High operational | Blocks a catalog reload of the current database. It does not block serving the database as it is, if embeddings are already present |
| Which vector-index manifest matches the live HNSW index? | Two manifests disagree on timestamp and index size (2026-09-27 in `resources/processed/`, 2026-10-22 under `resources/benchmark/`) | File contents differ. This audit did not query `pg_indexes` or index size | Read index size and definition from the running database, read-only | Medium | Blocks a claim about which build is loaded. It does not by itself block search |
| Which BM25 path does startup open? | `resolve_bm25_index_path` can choose a nested pickle or the file beside the catalog | Resolver rules are in source. The pickle was not opened | Log or print the resolved path inside a disposable process, without regenerating the index | Medium | Blocks a rebuild that must copy "the" pickle. The running process already chose one path at last start |
| How many duplicate rows did the published catalog run remove? | Needed only to retell the cleaning story. The published manifest count is 367,172 | Cleaner never drops rows. Deduplicator can. CSV count in the preflight report matches 367,172 | Re-count only if you accept reading the CSV again. Do not rewrite the Parquet | Low | No |
| What is the cell-by-cell order of the unread notebooks? | A rebuild could miss an entry point | Notebooks 09, 19, 24, 29, and 84 were tied to functions. The others were not read cell by cell. No `src/` function chains the offline stages | Read the remaining notebooks. Do not run them | Low | No |
| Do unknown-path 404 and method 405 return `ApiErrorEnvelope`? | Clients that parse `error.code` need to know | Tests cited in 04 check status only | Read one test or one response body. No catalog access required | Low | No |
| Does `SET hnsw.ef_search` stick to a pooled connection? | It could change later searches on that connection | 06 saw the statement inside `engine.connect()` and did not prove pool lifetime | Read SQLAlchemy pool semantics or log `SHOW hnsw.ef_search` on a disposable connection | Low | No |
| What are the numeric baseline ranker weights? | Needed to reimplement the score, not to trace the call | 09 and 11 left `BaselineRecommendationRankerConfig` and the search baseline weights unread as numbers | Read those config classes. No execution | Low | No |
| Does anything outside `src/productiq/recommendation` read `enable_*_generator`? | The flags look like switches and are not consulted by the production tuple | 09 grepped the recommendation package and found only the field definitions | Grep the rest of `src/` | Low | No |
| Are stage timings visible to API clients? | Easy to promise latency breakdowns the JSON does not contain | Recommendation execution metadata is not copied by the HTTP mapper. Search JSON also has no stage timers in the verification report | Already strong for the public models. A mapper re-read would close it | Low | No |
| Is the current database's embedding count still equal to its row count? | The upsert risk is about a future reload. The live table was not counted in this audit | October verification reported embeddings present for returned ids. This audit did not query | Read-only `count_catalog_products` and `count_products_with_embeddings` | Medium | Blocks a freshness claim. It does not require a write |
| Can a later edit turn LTR on without the guard noticing? | The function name sounds like a rejection | Body is `del stage`. `retrieve_ranked` simply does not call LTR today | Code review of `production_pipeline.py` on each ranking change | Medium for future edits | No, for the current source |

Removed from the open list by this audit: "Does SQLAlchemy omit `embedding` or send it as an explicit null?" The compiled `INSERT` omits it. The conflict `SET` still names `excluded.embedding`.

## 6. Recommended minimal corrections

Do these only when you choose to edit the notes. This audit does not apply them.

1. In `02-repository-and-code-map.md` search step 8, replace the sentence that says `assert_retrieve_ranked_uses_baseline_path` rejects LTR. State that the function only executes `del stage`, and that `retrieve_ranked` calls `run_baseline_ranking_stage` and does not call `rank_candidates_with_ltr`. Point at `03` so the correction has a home.
2. In that same file's catalog upsert row, add that the compiled `INSERT` lists the 22 processed columns and the conflict `SET` includes `embedding = excluded.embedding`, which writes null when the column is omitted. Point at `06` and `10`.
3. In `04-http-routes-and-error-handling.md`, name `_PerRequestRecommendationServingService` as the object on `app.state`, and say it calls `ProductionRecommendationServingService` for the request.
4. In `02` and `03`, retire the line that says `api_max_top_k` and `api_max_query_length` were not copied, or point at `DEFAULT_API_MAX_TOP_K` (`100`) and `DEFAULT_API_MAX_QUERY_LENGTH` (`512`).
5. Add a short glossary to `03` or `11` for seed, pool, `top_k`, artifact, column, and the two baseline rankers. Link the other notes to it instead of pasting the search walkthrough again.

Do not regenerate embeddings, reload the catalog, or edit `docs/architecture/` as part of these corrections.

## 7. What is safe, and what still needs investigation

**Safe to use as the engineering reference.** Documents 04 through 11, read with 03's correction of the map, describe one system: five routes, search through BM25 then vectors then RRF then filter then baseline rank, product detail as one `SELECT`, recommendations as a separate pipeline with three generators, startup that loads BM25 and the encoder and does not load Parquet, and catalog writes that commit per batch.

**Safe to proceed with.** Reading, interview explanation, and a paper rebuild that follows `11`. Serving the database that is already loaded, without a catalog reload.

**Do not do on the current database until the disposable-database check in section 5 has passed.** Any `load_processed_catalog` or catalog upsert against ids that already have embeddings. The compiled statement assigns `excluded.embedding` from an insert that omits the column.

**Still investigate before you rely on them.** Which vector manifest matches the live index. Which BM25 path the process resolved. Whether the live embedding count still equals the row count. Those are read-only questions. They are not a reason to rewrite the notes or to reload data.

## Classification summary

| Class | Item |
| --- | --- |
| Critical factual contradiction | Map section 3 claims the LTR guard rejects an experimental stage |
| High-priority operational risk | Catalog conflict update can null `products.embedding`. Confirmed by compiled SQL, not by a live run |
| Documentation gap | Map upsert row omits that consequence. 04 omits the per-request recommendation wrapper. 02 and 03 still list API caps as uncopied |
| Minor inconsistency | The map's own component table already says LTR is not called, which disagrees with its step 8 |
| Optional improvement | Shared glossary, cross-links, less repeated search narrative |
