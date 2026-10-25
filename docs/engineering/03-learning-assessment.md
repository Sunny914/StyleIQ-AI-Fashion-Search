# ProductIQ learning assessment

Verified against the source on 2026-10-25, using `docs/engineering/02-repository-and-code-map.md` as the starting map. This file does not change application code or architecture diagrams.

One map claim is narrower than the source. Section 3 of the map says `assert_retrieve_ranked_uses_baseline_path` rejects an experimental learning-to-rank stage. The function in `src/productiq/ranking/hardening/production_safety.py` only executes `del stage` and returns. The live search path still ranks with `run_baseline_ranking_stage` because `ProductionRetrievalPipeline._ranked_search_from_pool` calls that function when `stage.enabled` is true. `rank_candidates_with_ltr` is not called from `retrieve_ranked`.

## 1. Confirmed architecture and design patterns

These are patterns visible in the call structure. They are not a separate framework ProductIQ imported.

| Pattern | Status | Where it shows up |
| --- | --- | --- |
| Layered flow | Confirmed | HTTP route → serving service → retrieval or recommendation pipeline → database provider or SQL. Example: `post_search` → `ProductionSearchServingService.search` → `ProductionRetrievalPipeline.retrieve_ranked`. |
| Route and handler separation | Confirmed | `src/productiq/api/routes/search.py` `post_search` does not contain retrieval code. It validates a body and calls the injected service. The same shape is in `products.py`, `recommendations.py`, and `health.py`. `v1_router` only includes those routers. |
| Service layer | Confirmed | `ProductionSearchServingService`, `ProductionProductServingService`, `ProductionRecommendationServingService`. Protocols for those roles are in `src/productiq/serving/protocols.py`. |
| Repository | Confirmed, limited | `ProductRepository` in `src/productiq/database/repository.py` is a read API: `get_by_id`, `find_by_brand`, `find_by_category`, `find_by_color`, `find_filtered`, `count`. The HTTP product route does not use it. |
| Provider | Confirmed | `PostgresProductCatalogReadProvider.get_product` is the product HTTP read. Recommendation code uses `PostgresRecommendationCatalog`, `PostgresSeedProductResolver`, `PostgresProductEmbeddingProvider`, and `PostgresRecommendationProductContextProvider`. |
| Dependency injection | Confirmed, manual | `create_app` builds services and stores them on `app.state`. Route functions receive them through FastAPI `Depends` in `src/productiq/api/dependencies.py` (`get_search_service`, `get_product_service`, `get_recommendation_service`, `get_health_service`). Constructors also receive pipelines, engines, and encoders. This is not a third-party DI container. |
| Pipeline | Confirmed | Search: `ProductionRetrievalPipeline.retrieve_ranked`. Recommendations: `RecommendationPipeline.recommend_with_metadata`. Offline stages are separate functions, not one pipeline object. |
| Offline preparation versus online serving | Confirmed | `src/data/` plus `generate_representation_dataset`, `generate_product_embeddings_from_representation_dataset`, and `build_bm25_lexical_index_from_representation_dataset` prepare files. `load_runtime_catalog` writes PostgreSQL only when an operator runs it. `create_app` does not call that loader. |

Interpretation, not a named pattern in the code: the serving services are an application boundary that translates public models (`SearchApiRequest`) into internal models (`RetrievalRequest`, `RecommendationRequest`) and back. That is the usual meaning of an application service. The code does not label itself with that term.

Not present on the production path: a Redis cache, a generic CRUD controller, or an ORM unit-of-work exposed to routes.

## 2. Endpoints and request flow

Prefix: `SERVING_API_ROUTE_PREFIX` is `/api/v1` (`src/productiq/serving/versioning.py`).

| Method and path | Handler | Request model | Response model | Service | Database |
| --- | --- | --- | --- | --- | --- |
| `GET /api/v1/health` | `get_health` | None | `HealthResponse` | `ComposedHealthServingService.health` | None |
| `GET /api/v1/ready` | `get_ready` | None | `ReadinessResponse` | `ComposedHealthServingService.ready` → `build_readiness_response` | None. Catalog counts were captured at startup. |
| `POST /api/v1/search` | `post_search` | `SearchApiRequest` | `SearchApiResponse` | `ProductionSearchServingService.search` | Read: pgvector search, candidate filter `SELECT`, ranking context `SELECT` |
| `GET /api/v1/products/{product_id}` | `get_product` | Path `product_id: str` | `ProductApiResponse` | `ProductionProductServingService.get_product` | One `SELECT` by `product_id` |
| `POST /api/v1/recommendations` | `post_recommendations` | `RecommendationApiRequest` | `RecommendationApiResponse` | `_PerRequestRecommendationServingService.recommend` | Seed `SELECT`, generator reads, embedding reads |

Validation:

- FastAPI parses JSON into the Pydantic model before the handler body runs.
- `SearchApiRequest.validate_top_k_limit` checks `top_k` and query length.
- `RecommendationApiRequest.validate_production_scope` allows only `RecommendationType.SIMILAR`.
- `QueryFilterConstraints` validators run when `filters` is present.
- Invalid JSON or fields become `RequestValidationError`, handled by `request_validation_handler` as `ApiErrorCode.INVALID_REQUEST` and the message `Request validation failed`.

Serialization:

- Handlers declare `response_model=...`, so FastAPI serializes the returned Pydantic object.
- `ranked_search_to_api_response`, `product_read_model_to_api`, and `recommendation_response_to_api` choose which fields leave the process. Search drops scores. Product detail drops `brand_normalized`.

Errors:

- `ProductNotFoundError` and a missing-seed `CatalogValidationError` map to not-found bodies in `map_http_exception_to_api_error`.
- Other `ProductIQError` values go through `productiq_error_handler`.
- Any other exception becomes `ApiErrorCode.INTERNAL_ERROR` with `An unexpected error occurred`. The handler does not put the exception text in the response.
- `ResilienceMiddleware` can reject a request before the route using the in-memory `FixedWindowRateLimiter` and `ConcurrencyGate`.

Frontend callers in `frontend/lib/api.ts`: `getHealth`, `getReady`, `searchProducts`, `getProduct`, `getRecommendations`. `SearchExperience` calls search, then `loadProductCards`. `ProductDetailView` calls `getProduct`, then `getRecommendations`. `StatusIndicator` uses health and ready through `frontend/lib/catalog-status.ts`.

Search flow, short form:

`SearchPage` → `SearchExperience` → `searchProducts` → `post_search` → `build_query_representation` → `retrieve_ranked` → `RRFHybridRetriever.retrieve` (`BM25Retriever.retrieve` and `SemanticRetriever.retrieve`) → `PostgresCatalogCandidateFilter.filter_candidate_ids` → `run_baseline_ranking_stage` → `ranked_search_to_api_response` → `loadProductCards` → `get_product`.

Product flow:

`ProductPage` → `ProductDetailView` → `getProduct` → `get_product` → `PostgresProductCatalogReadProvider.get_product` → `product_read_model_to_api`.

Recommendation flow:

`getRecommendations` → `post_recommendations` → new SQLAlchemy session → `build_production_recommendation_pipeline` → `RecommendationPipeline.recommend_with_metadata` → `PostgresSeedProductResolver.resolve_seed_product` → generators → `exclude_seed_product` → `BaselineRecommendationRanker.rank` → `recommendation_response_to_api`.

## 3. Data-model inventory

Not every Pydantic model is a public DTO. Not every internal object is a database row.

### Public HTTP models

| Model | File | Fields that matter | Consumed by |
| --- | --- | --- | --- |
| `SearchApiRequest` | `serving/search_schema.py` | `query`, `top_k`, optional `filters` | `post_search`, `ProductionSearchServingService.search` |
| `SearchResultItem`, `SearchApiResponse` | same | `product_id`, `rank`; envelope adds `query`, `top_k`, `request_id`, `returned_count` | `ranked_search_to_api_response`, `frontend/lib/types.ts` `SearchResponse` |
| `ProductApiResponse` | `serving/product_schema.py` | `product_id`, `brand`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`, `request_id` | `product_read_model_to_api`, `ProductResponse` |
| `ProductCatalogReadModel` | same | Product fields plus `brand_normalized`. Not returned by HTTP as itself. | `PostgresProductCatalogReadProvider` |
| `RecommendationApiRequest` | `serving/recommendation_schema.py` | `seed_product_id`, `recommendation_type`, `top_k`, optional `filters` | `post_recommendations` |
| `RecommendationResultItem`, `RecommendationApiResponse` | same | `product_id`, `rank`, `recommendation_score` | `recommendation_response_to_api`, `RecommendationResponse` |
| `HealthResponse` | `serving/health.py` | `status`, `service`, `api_version` | `ComposedHealthServingService.health` |
| `ReadinessCheck`, `ReadinessResponse` | same | `name`, `status`, `message` | `build_readiness_response` |
| `ApiErrorBody`, `ApiErrorEnvelope` | `serving/errors.py` | `code`, `message`, `request_id` inside `error` | Exception handlers |

### Internal request and candidate models

| Model | File | Purpose |
| --- | --- | --- |
| `QueryFilterConstraints`, `QueryRepresentation` | `representation/query_contract.py` | Normalized query text plus hard filters. Built by `build_query_representation`. |
| `RetrievalRequest`, `RetrievalCandidate`, `RetrievalResponse` | `retrieval/contracts.py` | What BM25, semantic search, and RRF exchange. A candidate has `product_id`, `score`, and `method`. |
| `RankedSearchResponse` | `retrieval/ranked_search.py` | Output of `retrieve_ranked` before the API mapper. |
| `RankingRequest`, `RankingCandidate`, `RankedCandidate` | `ranking/contracts.py` | Baseline search ranker input and output. |
| `RecommendationRequest`, `RecommendationCandidate`, `RankedRecommendation`, `RecommendationResponse` | `recommendation/contracts.py` | Recommendation pipeline, including `recommendation_score`. |
| `RecommendationFeatures` | `recommendation/feature_schema.py` | Feature record scored by `compute_baseline_recommendation_score`. |
| `ProductRepresentation` | `representation/schema.py` | In-memory product used for text, filters, and the recommendation seed. |
| `FilteringRepresentation` | `representation/filtering.py` | Fields compared with query constraints. |

### ORM entity

`Product` in `src/productiq/database/models/product.py` is the only catalog entity on this path. Table `products`. Primary key `product_id`. Nullable `embedding` is `vector(384)`. Price columns exist on the row. They are not fields on `ProductApiResponse`.

### Frontend types

`frontend/lib/types.ts` mirrors the JSON the API returns. `ProductCardModel` in the same file is a UI shape built by `productToCard`. It is not sent to the server.

## 4. CRUD support matrix

| Action | Status | Evidence |
| --- | --- | --- |
| Create catalog rows | Implemented, as upsert | `ProductCatalogLoader.load_from_parquet` → `_upsert_records`: `INSERT ... ON CONFLICT (product_id) DO UPDATE`. New ids insert. Existing ids update. Commits once per Parquet batch. On exception, `session.rollback()`. |
| Create demo rows | Implemented | `load_compose_integration_demo_catalog` uses `session.merge` for `compose-demo-*` rows. |
| Update embeddings | Implemented | `load_product_embeddings_into_catalog` runs `UPDATE products SET embedding = CAST(:embedding AS vector) WHERE product_id = :product_id` inside `engine.begin()` per batch. |
| Read one product | Implemented | `PostgresProductCatalogReadProvider.get_product` and `ProductRepository.get_by_id`. |
| Read by brand, category, or color | Implemented on the repository | `find_by_brand`, `find_by_category`, `find_by_color`, `find_filtered`. Not used by `post_search`. |
| Read vectors for search | Implemented | `PgVectorProductVectorIndex.search` → `search_products_by_embedding`. |
| Count rows | Implemented | `ProductRepository.count`, `count_catalog_products`, `count_products_with_embeddings`. |
| Schema create | Implemented | `bootstrap_productiq_database`, `create_product_catalog_tables`, `ensure_pgvector_extension`, `ensure_product_embedding_column`. |
| HNSW create | Implemented | `create_product_embedding_hnsw_index`. If the index exists and `rebuild` is false, the function returns without rebuilding. |
| Delete product rows | Not implemented | No repository or route method deletes `products` rows. |
| Delete HNSW index | Partially implemented | `drop_product_embedding_hnsw_index` runs only when `create_product_embedding_hnsw_index(rebuild=True)`. The production wiring passes `rebuild=False` through `build_product_vector_index` unless a caller sets `rebuild_hnsw`. |
| Update a product from the API | Not implemented | Search, product, and recommendation handlers do not commit catalog writes. |
| User accounts, carts, orders | Not implemented | No such models or routes were found on the v1 router. |

Catalog load was not executed for this assessment.

Transaction notes that are established:

- Catalog upsert uses one session, `autocommit=False`, and `session.commit()` after each Parquet chunk. A failure rolls that session back. Chunks already committed stay written.
- Embedding updates use `engine.begin()` around each parquet batch, so each batch is its own transaction.
- Request sessions in `create_session_factory` also set `autocommit=False`. The read paths inspected (`get_product`, filter, recommendation request) open a session and `close()` it. They do not call `commit()`.

## 5. Startup and lifecycle

1. Uvicorn loads `create_app` as a factory (`Dockerfile` command).
2. `get_settings()` reads environment variables and an optional `.env`.
3. `settings.enable_production_serving` comes from `PRODUCTIQ_ENABLE_PRODUCTION_SERVING`. When it is false, and no services are injected, `build_application_services` builds a hollow app. Import still does not open PostgreSQL.
4. When the flag is true, `build_production_application_services` runs inside `create_app`, before requests are served:
   - `create_engine_from_settings`
   - `inspect_catalog_runtime_status` (counts only)
   - empty catalog raises `ConfigurationError`
   - BM25: fixture mode builds an index from database text; any other mode calls `create_bm25_retriever_from_index_path`
   - `create_bge_small_en_v15_encoder` unless tests inject an encoder
   - semantic retriever, RRF retriever, and `create_production_retrieval_pipeline(..., ranking_stage=ProductionRankingStageConfig(enabled=True))`
5. `build_lifespan` marks `app.state.is_running` and, on shutdown, calls `runtime.engine.dispose()`.
6. `load_runtime_catalog` is a separate CLI (`python -m productiq.database.load_runtime_catalog`). Compose runs it only as the `catalog-load` profile. Default Compose mode is fixture unless `PRODUCTIQ_CATALOG_LOAD_MODE` is changed.
7. The storefront base URL is `NEXT_PUBLIC_PRODUCTIQ_API_URL` in `frontend/lib/config.ts`, with a fallback of `http://localhost:8000`.

Cache and refresh, only what the code shows:

- `get_settings` is decorated with `lru_cache` in `src/productiq/config/settings.py`. That caches the settings object for the process.
- The BM25 `InvertedLexicalIndex` is held on `BM25Retriever` created at startup. A new pickle on disk is not reread until a new process calls `create_bm25_retriever_from_index_path` again.
- `BM25Scorer._term_frequency_maps` is a dict on the scorer instance. `BM25Retriever` builds one scorer in `__init__`, so that map lives for the process and fills as terms are seen. It is not a catalog cache.
- Readiness catalog counts are the values stored on `ApplicationServices` at startup. `build_readiness_response` does not query PostgreSQL again. Its own docstring says it aggregates readiness without expensive dependency I/O. Several checks are explicitly `not_checked` (`search_vector_index`, `search_bm25_index`, `product_catalog`).
- Rate limiting state is the in-memory `FixedWindowRateLimiter`. It is not shared across processes.
- No code path was found that refreshes the HNSW index or the BM25 artifact when a request arrives.

Unresolved: whether SQLAlchemy's connection pool reuses connections across requests is the library default for `create_engine`. This assessment did not read the engine constructor arguments beyond `create_engine_from_settings`.

## 6. Unresolved questions

- Notebooks call cleaning, representation, embeddings, and BM25 separately. No single `src/` function orders those steps. The offline sequence in the implementation map is still an inference from inputs and outputs.
- `assert_retrieve_ranked_uses_baseline_path` does not inspect `stage.experimental_ltr`. Safety today is "this function is not called," not "this guard rejects LTR."
- `ProductRepository.find_filtered` has no caller on the HTTP search path. Other callers outside tests were not fully enumerated.
- The SQL string inside `search_products_by_embedding` was not copied here.
- Numeric defaults for `ServingConfig.api_max_top_k` and `api_max_query_length` were not copied here.
- `docs/architecture/system.md` includes Redis. Production serving does not import Redis. Distributed rate limiting is described as deferred in `src/productiq/serving/phase_13_10_final_audit.py`.

## 7. Learning sequence

Study in this order. Later topics assume the earlier ones.

1. **HTTP.** A request has a method, a path, headers, and a body. A response has a status and a body. ProductIQ's five routes are the whole public surface. Read `src/productiq/api/routes/v1_router.py` and `frontend/lib/api.ts`. You should be able to say which function runs for each URL.

2. **FastAPI routes.** A handler is a function decorated with `@router.get` or `@router.post`. FastAPI turns the JSON body into a parameter. Read `post_search`, `get_product`, `post_recommendations`, `get_health`, `get_ready`. You should be able to point at the line that calls the service.

3. **Pydantic validation.** Models declare fields and constraints. Invalid input never enters `search()`. Read `SearchApiRequest` and `RecommendationApiRequest`, then `request_validation_handler`. You should be able to explain why an empty query or a non-SIMILAR recommendation type fails before retrieval.

4. **DTOs and serialization.** A DTO is the object you allow across a boundary. `SearchApiResponse` is a DTO. `RetrievalCandidate` is not. `Product` is a database row. Read `serving/mappers.py` next to the schema files. You should be able to explain why the browser never sees a BM25 score.

5. **Layers and services.** The route stays thin. The service owns the use case. The pipeline owns the steps. Read `ProductionSearchServingService.search` and `retrieve_ranked`. You should be able to walk one search without opening the frontend.

6. **Dependency injection.** `create_app` chooses the objects. `Depends` hands them to the route. Read `create_app`, `build_production_application_services`, and `dependencies.py`. You should be able to explain how tests can pass a fake service and how production passes the real pipeline.

7. **SQLAlchemy and PostgreSQL.** `Product` describes the table. A session is the short-lived handle for queries. `select(Product).where(...)` is a read. Read `database/models/product.py`, `postgres_catalog_provider.py`, and `database/session.py`. You should be able to say what one product-detail request does in the database.

8. **CRUD and transactions.** Create and update of catalog rows happen in the loader, not in the API. `commit` makes a batch durable. `rollback` undoes the open transaction. Read `catalog_loader.py` from `load_from_parquet` through the `except` block, and the `UPDATE` in `vector_index_loader.py`. You should be able to say what is persisted if batch 30 fails.

9. **Offline preparation.** Files are built before the server starts: Parquet, embeddings, BM25 pickle. Read the function names in section 7 of the implementation map, then one notebook only after the function is clear. You should be able to separate "build an artifact" from "answer a query."

10. **BM25 and vector retrieval.** BM25 scores lexical overlap using `BM25Scorer`. Semantic search encodes the query with `SentenceTransformerBGEEncoder.encode_query` and calls `PgVectorProductVectorIndex.search`. Read `bm25_retriever.py` and `semantic_retriever.py`. You should be able to say what each retriever returns: a `RetrievalResponse` of candidates.

11. **RRF and ranking.** `RRFHybridRetriever.retrieve` calls both retrievers and `build_rrf_fused_retrieval_response`. Filters run after fusion. `run_baseline_ranking_stage` orders that pool. Read `rrf_hybrid_retriever.py` and `ranking_integration.py`. You should be able to explain why rank 1 is not "the BM25 winner" by itself.

12. **Recommendations.** Same layering, different pipeline. Seed lookup, three generators, seed exclusion, weighted features. Read `recommendation_pipeline.py` `recommend_with_metadata` and `candidate_generation.py` `exclude_seed_product`. You should be able to say where the seed is removed.

13. **Lifecycle.** What is loaded once per process versus once per request. Read section 5 above, then `lifespan.py`. You should be able to explain why changing the pickle does nothing until the process starts again.

14. **Errors and tests.** Not-found versus validation versus unexpected errors. Read `exception_handlers.py` and one test file per route (`tests/api/test_search_integration.py`, `tests/serving/test_product_service.py`, `tests/api/test_recommendation_route.py`). You should be able to name the status behavior for a missing product without running the server.

## 8. Time to understand each area

These are study hours for a beginner who can already read Python, not calendar deadlines. They assume you trace the files, do not rewrite them.

| Area | Hours | Done when |
| --- | --- | --- |
| HTTP and the five routes | 6–8 | You can list method, path, handler, and caller from memory |
| Pydantic and error bodies | 4–6 | You can predict the failure for a bad `top_k` and a missing product |
| Layers, services, and `Depends` | 8–10 | You can draw search from `post_search` to `retrieve_ranked` |
| SQLAlchemy reads and the `Product` row | 8–12 | You can explain product detail SQL and which columns the API hides |
| Loader transactions and embedding updates | 6–8 | You can explain upsert, batch `commit`, and `rollback` |
| Offline artifacts | 8–12 | You can name the file each stage writes |
| BM25, pgvector, RRF, baseline rank | 12–16 | You can explain one query's candidate lists and the final rank |
| Recommendations | 8–10 | You can explain seed resolution and seed exclusion |
| Startup, readiness, and tests | 6–8 | You can explain the production flag, engine dispose, and one test per route |

About 70–90 focused hours covers a rebuild-level explanation of this backend. The offline notebooks are the part most likely to take longer, because they are not one function.

## 9. Documentation sequence

Write these only after the matching study block. Do not replace `02-repository-and-code-map.md`.

1. `04-http-and-errors.md` — five routes, status codes, validation, frontend callers.
2. `05-data-contracts.md` — which model crosses which boundary, with fields.
3. `06-database-and-transactions.md` — `Product`, reads, upsert, embedding `UPDATE`, what is not implemented.
4. `07-startup-and-process-lifetime.md` — `create_app`, flag, BM25, encoder, engine dispose, what is not refreshed.
5. `08-search-walkthrough.md` — one query, function by function, ending at `SearchApiResponse`.
6. `09-product-and-recommendations.md` — detail read, then the recommendation pipeline.
7. `10-offline-artifacts.md` — stage functions and the files they write, after a notebook is actually read.
8. `11-rebuild-checklist.md` — the smallest order in which you would reimplement the pieces.

Correct the learning-to-rank sentence in `02-repository-and-code-map.md` only when you next edit that map: the guard function does not reject LTR; `retrieve_ranked` simply calls `run_baseline_ranking_stage`.
