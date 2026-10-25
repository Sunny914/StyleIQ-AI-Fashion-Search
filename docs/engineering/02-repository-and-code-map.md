# ProductIQ repository and code map

Verified from the source tree on 2026-10-25. This document records the implementation that is in the repository. It does not change architecture diagrams under `docs/architecture/`.

If a relationship is not established by a function call in source, it is listed under [Unresolved questions](#12-unresolved-questions).

## 1. Repository map

```text
ProductIQ/
  src/productiq/          Python package: API, retrieval, ranking, recommendations, serving, database
  src/data/               Offline catalog ingestion, cleaning, normalization, deduplication, export
  frontend/               Next.js App Router storefront
  tests/                  Pytest suites aligned with the packages above
  frontend/tests/         Vitest tests for the storefront
  docs/architecture/      Existing design notes (unchanged by this map)
  docs/engineering/       Engineering notes, including this file
  notebooks/data_engineering/   Notebooks that call offline stage functions
  resources/raw/          Source AJIO CSV
  resources/processed/    Processed Parquet, embeddings, BM25 pickle, manifests
  docker-compose.yml      Postgres, API, and the explicit catalog-load service
  Dockerfile              API image; command is uvicorn --factory productiq.api.app:create_app
```

Top-level Python packages under `src/productiq/`:

| Directory | Role in the running system |
| --- | --- |
| `api/` | FastAPI factory, routes, middleware, production wiring |
| `serving/` | HTTP-facing services, schemas, mappers, health, in-process resilience |
| `retrieval/` | BM25, semantic search, RRF, vector index, production search pipeline |
| `ranking/` | Baseline search ranker and experimental LightGBM learning-to-rank |
| `recommendation/` | Similar-product pipeline, generators, baseline recommendation ranker |
| `database/` | Engine, sessions, `Product` ORM, catalog load, pgvector schema helpers |
| `representation/` | Product and query text contracts used by retrieval and recommendations |
| `config/` | `Settings` and artifact path resolution |
| `observability/` | Request and stage tracing around serving calls |

`src/data/` is offline only. The HTTP application does not import it on the search, product, or recommendation request path.

## 2. Component responsibility table

| Concern | File | Types and functions | Reads / writes | Tests |
| --- | --- | --- | --- | --- |
| Process entry | `Dockerfile` | `uvicorn productiq.api.app:create_app --factory` | None | `tests/docker/test_docker_production_image.py` |
| App factory | `src/productiq/api/app.py` | `create_app`, `_apply_application_services`, `_configure_cors` | Reads settings. Attaches services to `app.state` | `tests/api/test_fastapi_app.py` |
| Settings | `src/productiq/config/settings.py` | `Settings`, `get_settings` | Reads environment and optional `.env`. No catalog writes | `tests/config/test_settings.py` |
| Lifespan | `src/productiq/api/lifespan.py` | `build_lifespan` | On shutdown, `ProductionServingRuntime.engine.dispose()` | `tests/api/test_fastapi_app.py` |
| Production wiring | `src/productiq/api/services/production_stack.py` | `build_production_application_services` | Reads catalog counts and BM25 artifact. Opens a SQLAlchemy engine. Does not load Parquet | `tests/api/test_production_stack_contract.py` |
| Routes | `src/productiq/api/routes/v1_router.py` | `v1_router` includes health, search, recommendations, products | None | `tests/api/test_api_http_boundary.py` |
| Search HTTP | `src/productiq/api/routes/search.py` | `post_search` | Delegates to the search service | `tests/api/test_search_integration.py`, `tests/api/test_api_search_coverage.py` |
| Product HTTP | `src/productiq/api/routes/products.py` | `get_product` | Delegates to the product service | `tests/serving/test_product_service.py` |
| Recommendation HTTP | `src/productiq/api/routes/recommendations.py` | `post_recommendations` | Delegates to the recommendation service | `tests/api/test_recommendation_route.py` |
| Dependencies | `src/productiq/api/dependencies.py` | `get_search_service`, `get_product_service`, `get_recommendation_service`, `get_request_id` | Reads `app.state` | `tests/api/test_application_integration.py` |
| Search service | `src/productiq/serving/search_service.py` | `ProductionSearchServingService.search` | No direct SQL | `tests/serving/test_search_service.py` |
| Product service | `src/productiq/serving/product_service.py` | `ProductionProductServingService.get_product` | Read through the catalog provider | `tests/serving/test_product_service.py` |
| Recommendation service | `src/productiq/serving/recommendation_service.py` | `ProductionRecommendationServingService.recommend` | No direct SQL | `tests/serving/test_recommendation_service.py` |
| API mapping | `src/productiq/serving/mappers.py` | `ranked_search_to_api_response`, `product_read_model_to_api`, `recommendation_response_to_api` | None | `tests/serving/test_serving_mappers.py` |
| Product SQL read | `src/productiq/serving/postgres_catalog_provider.py` | `PostgresProductCatalogReadProvider.get_product` | `SELECT` one `products` row | `tests/api/test_production_stack_contract.py` |
| Repository reads | `src/productiq/database/repository.py` | `ProductRepository` | Read only: `get_by_id`, `find_by_*`, `find_filtered`, `count` | `tests/database/test_product_repository.py` |
| BM25 load and retrieve | `src/productiq/retrieval/bm25_retriever.py` | `create_bm25_retriever_from_index_path`, `BM25Retriever.retrieve` | Reads the pickle at startup. Query time is in memory | `tests/retrieval/test_bm25.py`, `tests/retrieval/test_bm25_retriever.py` |
| BM25 scoring | `src/productiq/retrieval/bm25.py` | `BM25Scorer.score_lexical_query`, `BM25Scorer._term_frequency` | In memory | `tests/retrieval/test_bm25.py` |
| Query embedding | `src/productiq/retrieval/embedding_encoder.py` | `SentenceTransformerBGEEncoder.encode_query`, `create_bge_small_en_v15_encoder` | Loads model weights. Does not write embeddings | `tests/retrieval/test_embedding_generation.py` |
| Semantic retrieve | `src/productiq/retrieval/semantic_retriever.py` | `SemanticRetriever.retrieve` | Calls the vector index | `tests/retrieval/test_semantic_retriever.py` |
| pgvector search | `src/productiq/retrieval/pgvector_vector_index.py`, `pgvector_search.py` | `PgVectorProductVectorIndex.search`, `search_products_by_embedding` | Read of `products.embedding` | `tests/retrieval/test_pgvector_vector_index.py` |
| RRF | `src/productiq/retrieval/rrf_hybrid_retriever.py`, `rrf_fusion.py` | `RRFHybridRetriever.retrieve`, `build_rrf_fused_retrieval_response` | None | `tests/retrieval/test_rrf_fusion.py`, `tests/retrieval/test_hybrid_retriever.py` |
| Search pipeline | `src/productiq/retrieval/production_pipeline.py` | `ProductionRetrievalPipeline.retrieve_ranked` | Filter and ranking open short SQL sessions | `tests/retrieval/integration/` |
| Hard filters | `src/productiq/retrieval/catalog_candidate_filter.py` | `PostgresCatalogCandidateFilter.filter_candidate_ids` | `SELECT` candidate rows | `tests/retrieval/test_retrieval_failure_analysis.py` |
| Baseline search rank | `src/productiq/retrieval/ranking_integration.py` | `run_baseline_ranking_stage` | Reads ranking context rows | `tests/ranking/test_ranking_contract.py` |
| Experimental LTR | `src/productiq/ranking/ltr/inference.py`, `ranking/ltr/training.py` | `rank_candidates_with_ltr`, `train_ltr_model` | Artifact load for experiments. Not called by `retrieve_ranked` | `tests/ranking/test_ltr_inference_and_comparison.py` |
| Recommendations | `src/productiq/recommendation/recommendation_pipeline.py` | `RecommendationPipeline.recommend_with_metadata` | Seed and candidate reads | `tests/recommendation/test_recommendation_pipeline.py` |
| Recommendation wiring | `src/productiq/serving/performance/recommendation_production_wiring.py` | `build_production_recommendation_pipeline` | Uses the request session and engine | `tests/serving/test_recommendation_service.py` |
| Catalog upsert | `src/productiq/database/loaders/catalog_loader.py` | `ProductCatalogLoader.load_from_parquet`, `_upsert_records` | Insert or update `products` | `tests/database/test_catalog_integration.py` |
| Runtime load CLI | `src/productiq/database/load_runtime_catalog.py` | `load_runtime_catalog`, `main` | Writes catalog and embeddings when an operator runs it | `tests/docker/test_phase_15c_compose_contract.py` |
| Schema and HNSW | `src/productiq/database/vector_catalog.py`, `bootstrap_compose.py` | `create_product_embedding_hnsw_index`, `bootstrap_productiq_database` | DDL. Index drop only when `rebuild=True` | `tests/database/test_pgvector.py`, `tests/retrieval/test_vector_index_contract.py` |
| Storefront | `frontend/lib/api.ts`, `frontend/components/SearchExperience.tsx`, `frontend/components/ProductDetailView.tsx` | `searchProducts`, `getProduct`, `getRecommendations` | HTTP only | `frontend/tests/` |

## 3. Search call chain

Browser route: `frontend/app/search/page.tsx` `SearchPage` reads `q` and `gender`, then renders `SearchExperience`.

1. `SearchExperience` (`frontend/components/SearchExperience.tsx`) calls `searchProducts` with `topK` from `SEARCH_TOP_K` and an optional `filters.category_gender`.
2. `searchProducts` (`frontend/lib/api.ts`) `POST`s `{ query, top_k, filters? }` to `/api/v1/search` through `requestJson`.
3. `v1_router` mounts `search_router` under `SERVING_API_ROUTE_PREFIX` (`/api/v1`, `src/productiq/serving/versioning.py`).
4. `post_search` (`src/productiq/api/routes/search.py`) validates the body as `SearchApiRequest` and calls `service.search(body, request_id=request_id)`.
5. `get_search_service` returns `app.state.search_service`.
6. `ProductionSearchServingService.search` calls `build_query_representation`, then `ProductionRetrievalPipeline.retrieve_ranked`, then `ranked_search_to_api_response`.
7. `retrieve_ranked` calls `_retrieve_filtered_pool`:
   - `RRFHybridRetriever.retrieve`
   - `BM25Retriever.retrieve` and `SemanticRetriever.retrieve` with the same `RetrievalRequest`
   - `build_rrf_fused_retrieval_response`
   - `_SessionFactoryCatalogFilter.filter_candidate_ids` → `PostgresCatalogCandidateFilter.filter_candidate_ids`
8. When `ProductionRankingStageConfig(enabled=True)`, `retrieve_ranked` calls `run_baseline_ranking_stage`. That function calls `extract_features_for_request`, `normalize_features_for_query`, and `rank_candidates`. `retrieve_ranked` reaches that ranker through `_ranked_search_from_pool`, which calls `assert_retrieve_ranked_uses_baseline_path`. That function's body is `del stage`. `assert_retrieve_ranked_uses_baseline_path` does not inspect or reject learning-to-rank. `retrieve_ranked` does not call `rank_candidates_with_ltr`. Outside that module, the call sites are evaluation code: `src/productiq/ranking/ltr/comparison/evaluator.py` and `src/productiq/retrieval/evaluation/search_evaluation/ranking_variant_executor.py`. `rank_candidates_with_ltr_feature_rows` in `inference.py` delegates to the same function.
9. `ranked_search_to_api_response` copies `product_id` and `rank` into `SearchResultItem` values. Scores are not copied.
10. `SearchExperience` calls `loadProductCards` (`frontend/lib/catalog.ts`), which calls `getProduct` for each id with concurrency `PRODUCT_LOOKUP_CONCURRENCY`. `productToCard` builds the card. `ProductCard` renders it.

`SearchApiRequest` (`src/productiq/serving/search_schema.py`) fields: `query` (non-empty), `top_k` (positive, capped by `ServingConfig.api_max_top_k`), optional `filters` of type `QueryFilterConstraints`. Extra fields are forbidden.

`SearchApiResponse` fields: `query`, `top_k`, `results`, `request_id`, `returned_count`.

## 4. Product-detail call chain

1. `frontend/app/products/[id]/page.tsx` `ProductPage` decodes the route id and renders `ProductDetailView`.
2. `ProductDetailView` calls `getProduct(productId)`.
3. `getProduct` (`frontend/lib/api.ts`) sends `GET /api/v1/products/{id}`.
4. `get_product` (`src/productiq/api/routes/products.py`) calls `ProductionProductServingService.get_product`.
5. The service strips `product_id`, calls `PostgresProductCatalogReadProvider.get_product`, and maps the row with `product_read_model_to_api`.
6. The provider opens a session, runs `select(Product).where(Product.product_id == product_id)`, and returns `ProductCatalogReadModel` or `None`.
7. A missing row raises `ProductNotFoundError("Product not found.")`.
8. The view then calls `getRecommendations` for similar products. That second call is the recommendation chain below. `withoutSeed` drops the seed id on the client as well.

`ProductApiResponse` fields: `product_id`, `brand`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`, `request_id`. `brand_normalized` is on `ProductCatalogReadModel` and is not copied to the HTTP response.

The HTTP product path does not call `ProductRepository`.

## 5. Recommendation call chain

1. `ProductDetailView` calls `getRecommendations(seedProductId, RECOMMENDATION_TOP_K)`.
2. `getRecommendations` `POST`s `{ seed_product_id, top_k }` to `/api/v1/recommendations`.
3. `post_recommendations` validates `RecommendationApiRequest` and calls `service.recommend`.
4. In production, that service is `_PerRequestRecommendationServingService.recommend` (`production_stack.py`). It opens one session and calls `build_production_recommendation_pipeline`.
5. `build_production_recommendation_pipeline` constructs:
   - `PostgresRecommendationCatalog`
   - `VectorRecommendationCandidateGenerator`
   - `AttributeRecommendationCandidateGenerator`
   - `BM25RecommendationCandidateGenerator`
   - `ContentSimilarityEngine` with `PostgresProductEmbeddingProvider`
   - `PostgresRecommendationProductContextProvider`
   - `BaselineRecommendationRanker`
   - `_LazyPostgresFilteringMap`
6. `create_recommendation_serving_service_from_pipeline` wraps that pipeline in `ProductionRecommendationServingService`.
7. `recommend` builds a `RecommendationRequest` and calls `RecommendationPipeline.recommend_with_metadata`.
8. `recommend_with_metadata` calls `catalog.resolve_seed_product`. `PostgresRecommendationCatalog.resolve_seed_product` loads the ORM row and `build_product_representation`. A missing seed raises `CatalogValidationError`.
9. `generate_recommendation_candidates` runs each generator, merges with `merge_recommendation_candidates`, calls `exclude_seed_product`, filters with `filter_recommendation_candidates`, excludes the seed again, and sorts by `product_id`.
10. Later stages call `extract_features_for_candidates`, `BaselineRecommendationRanker.rank` → `rank_recommendations`, and `select_recommendations_for_request`. `rank_recommendations` also calls `_exclude_seed_features` and `validate_seed_product_excluded`.
11. `recommendation_response_to_api` copies `product_id`, `rank`, and `recommendation_score`.

`RecommendationApiRequest` requires `recommendation_type` to be `RecommendationType.SIMILAR`. The default is `SIMILAR`.

## 6. Startup and shutdown

`create_app` (`src/productiq/api/app.py`):

1. Loads `Settings` through `get_settings()` unless a settings object is passed in.
2. If `application_services` is passed, those services are used.
3. Else if `settings.enable_production_serving` is true and no search, recommendation, or product service was injected, it calls `build_production_application_services`.
4. Otherwise it calls `build_application_services`, which can leave services unset. That is the hollow app.
5. Stores services, `ServingConfig`, `ComposedHealthServingService`, artifact paths, and `ProductionServingRuntime` on `app.state`.
6. Adds CORS when `settings.cors_allowed_origins` is non-empty. Methods are `GET`, `POST`, and `OPTIONS`.
7. Adds `ResilienceMiddleware`, `ObservabilityMiddleware`, and `RequestIdMiddleware`.
8. Registers exception handlers and includes `v1_router` at `/api/v1`.

`build_production_application_services` runs during `create_app`, before the lifespan yield:

1. `create_engine_from_settings`
2. `resolve_runtime_artifact_paths`
3. `inspect_catalog_runtime_status`
4. Raises `ConfigurationError` when `catalog_status.mode == "empty"`
5. `create_session_factory`
6. `_resolve_lexical_retriever`
   - mode `fixture`: `_bm25_from_postgres_descriptions` reads `Product` rows and builds an in-memory index
   - otherwise: `create_bm25_retriever_from_index_path` when the BM25 file exists
7. `create_bge_small_en_v15_encoder(device="cpu", allow_cpu_fallback=True)` unless an encoder is injected
8. `create_semantic_retriever_from_engine`
9. `create_rrf_hybrid_retriever` with `RRFConfig(rank_constant=60)`
10. `create_production_retrieval_pipeline` with `ProductionRankingStageConfig(enabled=True)`
11. Search, product, and recommendation services are stored on `ApplicationServices`

`build_lifespan` sets `app.state.is_running = True`, logs configured service names, yields, then sets `is_running = False` and calls `runtime.engine.dispose()` when a production runtime exists. The lifespan docstring says it does not itself load retrieval or model resources. Those loads happen in `create_app` when production serving is enabled.

Importing `create_app` does not open PostgreSQL. `tests/conftest.py` forces production serving off for the default suite.

Compose sets `PRODUCTIQ_ENABLE_PRODUCTION_SERVING` for `productiq-api` and mounts `resources/processed` read-only at `/artifacts/processed`. The catalog-load service is a separate profile. Its command is `python -m productiq.database.load_runtime_catalog`. The default mode in Compose is `fixture` unless `PRODUCTIQ_CATALOG_LOAD_MODE` is set.

## 7. Offline catalog preparation and loading

There is no single Python function that runs the CSV through embeddings and database load. Each stage is a separate class or function. Notebooks under `notebooks/data_engineering/` call those stages. The order below is the dependency order of their inputs and outputs, not one traced `main`.

| Stage | Implementation | Persistent output |
| --- | --- | --- |
| CSV ingest | `AjioDataLoader.load` in `src/data/ingestion/ajio.py` | DataFrame in memory |
| Cleaning | `AjioDataCleaner.clean` in `src/data/preprocessing/cleaning.py` | DataFrame |
| Normalization | `AjioDataNormalizer` in `src/data/preprocessing/normalization.py` | DataFrame |
| Deduplication | `AjioDataDeduplicator` in `src/data/deduplication/deduplicator.py` | DataFrame |
| Canonical rows | `AjioCanonicalProductBuilder` in `src/data/catalog/canonical.py` | Canonical records |
| Attributes | `ProductAttributeExtractor` in `src/data/attributes/extractor.py` | Attribute columns |
| Processed Parquet | `ProcessedDatasetWriter` in `src/data/export/processed.py` | `product_catalog.parquet` and its manifest |
| Representation | `generate_representation_dataset` in `src/productiq/representation/dataset.py` | Representation Parquet |
| Embeddings | `generate_product_embeddings_from_representation_dataset` in `src/productiq/retrieval/embedding_builder.py` | `product_embeddings.parquet` |
| BM25 artifact | `build_bm25_lexical_index_from_representation_dataset` in `src/productiq/retrieval/index_builder.py` | `bm25_lexical_index.pkl` and manifest |
| Database catalog | `load_runtime_catalog` → `load_processed_catalog` → `ProductCatalogLoader.load_from_parquet` | Upsert into `products` |
| Database vectors | `build_product_vector_index` → `load_product_embeddings_into_catalog` | `UPDATE` of `products.embedding`, then HNSW ensure |
| Validation | `validate_product_catalog`, `validate_product_vector_index_state` | Read-only checks |

`load_runtime_catalog` (`src/productiq/database/load_runtime_catalog.py`):

- `mode="fixture"` calls `bootstrap_productiq_database` and `load_compose_integration_demo_catalog`. The demo loader uses `session.merge` for three `compose-demo-*` rows with unit embeddings.
- `mode="full"` or `"partial"` calls `load_processed_catalog` and, when an embeddings path is present, `build_product_vector_index`.
- `classify_catalog_mode` returns `full` only when the product count equals `AJIO_PROCESSED_ROW_COUNT`.

`ProductCatalogLoader.load_from_parquet` validates the Parquet, reads it in chunks (`DEFAULT_CATALOG_LOAD_CHUNK_SIZE` is 10_000), and calls `_upsert_records`. The upsert is `INSERT ... ON CONFLICT (product_id) DO UPDATE` for every ORM column except `product_id`.

`build_product_vector_index` validates the embedding artifact, updates vectors, calls `create_product_embedding_hnsw_index(rebuild=False)` unless the caller sets `rebuild_hnsw`, validates counts, and publishes a vector-index manifest. `load_runtime_catalog` can pass `vector_manifest_dir` as `output_dir`.

Online startup does not call this loader.

## 8. Data contracts

### HTTP

| Model | File | Role |
| --- | --- | --- |
| `SearchApiRequest`, `SearchResultItem`, `SearchApiResponse` | `src/productiq/serving/search_schema.py` | Search body and response |
| `ProductCatalogReadModel`, `ProductApiResponse` | `src/productiq/serving/product_schema.py` | Catalog read boundary and product response |
| `RecommendationApiRequest`, `RecommendationResultItem`, `RecommendationApiResponse` | `src/productiq/serving/recommendation_schema.py` | Recommendation body and response |
| `HealthResponse`, `ReadinessResponse`, `ReadinessCheck` | `src/productiq/serving/health.py` | Health and readiness |
| `ApiErrorBody` | `src/productiq/serving/errors.py` | Error envelope |

### Query and retrieval

| Model | File |
| --- | --- |
| `QueryFilterConstraints`, `QueryRepresentation` | `src/productiq/representation/query_contract.py` |
| `RetrievalRequest`, `RetrievalCandidate`, `RetrievalResponse` | `src/productiq/retrieval/contracts.py` |
| `RankedSearchResponse` | `src/productiq/retrieval/ranked_search.py` |
| `RankingRequest`, `RankingCandidate`, `RankedCandidate`, `RankingResponse` | `src/productiq/ranking/contracts.py` |
| `RankingProductContext` | `src/productiq/ranking/product_context.py` |

`QueryFilterConstraints` includes `category_gender`, brand, product type, color, pattern, material, fit, sleeve, neckline, product features, style attributes, and discount-price bounds. The storefront sends only `category_gender`.

### Recommendations

| Model | File |
| --- | --- |
| `RecommendationType`, `RecommendationRequest`, `RecommendationCandidate`, `RankedRecommendation`, `RecommendationResponse` | `src/productiq/recommendation/contracts.py` |
| `RecommendationFeatures` | `src/productiq/recommendation/feature_schema.py` |
| `ProductRepresentation` | `src/productiq/representation/schema.py` |

### Database

`Product` in `src/productiq/database/models/product.py` maps table `products`.

Required text columns: `product_id` (primary key), `product_url`, `brand`, `brand_normalized`, `description`, `image_url`, `category_gender`, `color_raw`, `color_normalized`, `source`.

Other required columns: `color_is_coded`, `discount_price_inr`, `original_price_inr`, `price_anomaly`.

Nullable attribute columns: `product_type`, `fit`, `pattern`, `sleeve`, `neckline`, `material`, `product_features`, `style_attributes`.

`embedding` is nullable `Vector(384)`.

Check constraint `ck_products_source_ajio`. B-tree indexes: `ix_products_brand_normalized`, `ix_products_category_gender`, `ix_products_color_normalized`, `ix_products_source`. The HNSW index `ix_products_embedding_hnsw_cosine` is created by `create_product_embedding_hnsw_index`, not by `Product.__table_args__`.

### Frontend

`frontend/lib/types.ts` defines `SearchResponse`, `ProductResponse`, `RecommendationResponse`, `HealthResponse`, and `ReadinessResponse`. `ProductCardModel` is the display shape built by `productToCard`. It is not an API model.

## 9. CRUD and database access

| Operation | Implemented where | Not implemented where |
| --- | --- | --- |
| Create / update catalog rows | `ProductCatalogLoader._upsert_records` (`ON CONFLICT DO UPDATE`). Fixture rows: `load_compose_integration_demo_catalog` uses `session.merge`. | `ProductRepository` has no insert or update method. HTTP routes do not write products. |
| Create / update embeddings | `load_product_embeddings_into_catalog` updates `products.embedding` by `product_id`. | Search and product routes do not write embeddings. |
| Read one product | `PostgresProductCatalogReadProvider.get_product`. Also `ProductRepository.get_by_id` and `PostgresRecommendationCatalog.resolve_seed_product`. | |
| Read many products | `ProductRepository.find_by_brand`, `find_by_category`, `find_by_color`, `find_filtered`. Filter path: `PostgresCatalogCandidateFilter.filter_candidate_ids` loads the candidate id set. | |
| Read vectors | `search_products_by_embedding` and `PostgresProductEmbeddingProvider` / `PostgresSeedEmbeddingProvider`. | |
| Count | `ProductRepository.count`, `count_catalog_products`, `count_products_with_embeddings`. | |
| Delete product rows | No application method deletes `products` rows. | A SQL `DELETE` is not part of the loader or the API. |
| Drop HNSW | `drop_product_embedding_hnsw_index`, called only when `create_product_embedding_hnsw_index(rebuild=True)` and the index already exists. | Default production load uses `rebuild=False`. |

Sessions: `create_session_factory` in `src/productiq/database/session.py`. Production search opens a session per filter call and per ranking-context load, then closes it. Product reads open and close one session per lookup. Recommendations open one session per HTTP request inside `_PerRequestRecommendationServingService.recommend`.

## 10. Frontend-to-backend communication

`apiBaseUrl` (`frontend/lib/config.ts`) uses `NEXT_PUBLIC_PRODUCTIQ_API_URL` and otherwise `http://localhost:8000`. `requestJson` sends JSON with `fetch`, aborts after `REQUEST_TIMEOUT_MS`, and throws `ProductIqApiError` for HTTP, network, timeout, and malformed bodies.

| UI function | HTTP | Next step in the UI |
| --- | --- | --- |
| `searchProducts` | `POST /api/v1/search` | `loadProductCards` → `getProduct` → `ProductCard` |
| `getProduct` | `GET /api/v1/products/{id}` | `productToCard` or the detail view |
| `getRecommendations` | `POST /api/v1/recommendations` | `withoutSeed`, then `loadProductCards` |
| `getHealth`, `getReady` | `GET /api/v1/health`, `GET /api/v1/ready` | `StatusIndicator` through `frontend/lib/catalog-status.ts` |

The browser calls the API directly. CORS is configured in `_configure_cors`. Development defaults come from `default_cors_origins_for_environment` in `src/productiq/config/cors.py`.

Search pages do not display `recommendation_score`. Product cards use `description` as the visible title.

## 11. Source and test index

Request path:

- `frontend/app/search/page.tsx`
- `frontend/app/products/[id]/page.tsx`
- `frontend/components/SearchExperience.tsx`
- `frontend/components/ProductDetailView.tsx`
- `frontend/components/ProductCard.tsx`
- `frontend/lib/api.ts`
- `frontend/lib/catalog.ts`
- `frontend/lib/types.ts`
- `src/productiq/api/app.py`
- `src/productiq/api/lifespan.py`
- `src/productiq/api/routes/search.py`
- `src/productiq/api/routes/products.py`
- `src/productiq/api/routes/recommendations.py`
- `src/productiq/api/services/production_stack.py`
- `src/productiq/serving/search_service.py`
- `src/productiq/serving/product_service.py`
- `src/productiq/serving/recommendation_service.py`
- `src/productiq/retrieval/production_pipeline.py`
- `src/productiq/retrieval/bm25_retriever.py`
- `src/productiq/retrieval/semantic_retriever.py`
- `src/productiq/retrieval/rrf_hybrid_retriever.py`

Tests that lock these boundaries:

- `tests/api/test_fastapi_app.py`
- `tests/api/test_production_stack_contract.py`
- `tests/api/test_search_integration.py`
- `tests/api/test_recommendation_route.py`
- `tests/api/test_readiness.py`
- `tests/serving/test_search_service.py`
- `tests/serving/test_product_service.py`
- `tests/serving/test_recommendation_service.py`
- `tests/serving/test_serving_mappers.py`
- `tests/retrieval/test_bm25.py`
- `tests/retrieval/test_bm25_retriever.py`
- `tests/retrieval/test_semantic_retriever.py`
- `tests/retrieval/test_rrf_fusion.py`
- `tests/ranking/test_ranking_contract.py`
- `tests/ranking/test_ltr_inference_and_comparison.py`
- `tests/recommendation/test_recommendation_pipeline.py`
- `tests/database/test_product_repository.py`
- `tests/database/test_catalog_integration.py`
- `tests/docker/test_phase_15c_compose_contract.py`
- `frontend/tests/api.test.ts`
- `frontend/tests/search-experience.test.tsx`
- `frontend/tests/product-detail.test.tsx`
- `frontend/tests/product-card.test.tsx`

Evaluation reports already in the tree, not rewritten here:

- `resources/benchmark/phase_15b_database_audit.md`
- `resources/benchmark/phase_15c_serving_audit.md`
- `resources/benchmark/full_catalog_preflight_2026-10-22.md`
- `resources/benchmark/full_catalog_search_verification_2026-10-23.md`

## 12. Unresolved questions

- No one function in `src/` calls `AjioDataLoader`, `AjioDataCleaner`, `generate_representation_dataset`, `generate_product_embeddings_from_representation_dataset`, and `build_bm25_lexical_index_from_representation_dataset` in sequence. The stage order in section 7 is inferred from inputs and outputs. The notebooks were not executed or read cell by cell for this map.
- `docs/architecture/system.md` draws a Redis box. The production path in `create_app` and `build_production_application_services` does not import Redis. Audit modules describe distributed rate limiting as deferred. Whether any notebook or script uses Redis was not searched beyond `src/`.
- `ProductRepository` is used by the catalog loader for counts and by database tests. Which other production callers, if any, use `find_filtered` during a live search was not found on the HTTP path. Search filtering uses `PostgresCatalogCandidateFilter`.
- The exact SQL text inside `search_products_by_embedding` was not copied into this map. The call is `PgVectorProductVectorIndex.search` → `search_products_by_embedding`.
- `ServingConfig.api_max_top_k` and `api_max_query_length` are read at validation time. Their numeric defaults were not copied here.
- Client-side `withoutSeed` runs after the server already excludes the seed in `exclude_seed_product` and `_exclude_seed_features`. Both exist. This map does not claim one makes the other redundant.
