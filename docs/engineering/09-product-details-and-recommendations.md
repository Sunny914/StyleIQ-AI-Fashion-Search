# Product details and recommendations

This note follows two requests that start on the product page: load one product, then ask for similar products.

A product-detail request reads one row by id. A recommendation request starts from that id, called the seed, and returns other ids. They are separate because the page can show the product even when recommendations fail, and because the recommendation work is a pipeline rather than a lookup.

Search retrieval is not repeated here. Where the two paths differ, section 9 names the difference.

The functions below were read. Tests were not executed.

## 1. Two different operations

| | Product detail | Recommendations |
| --- | --- | --- |
| Question | What is this product? | Which other products are similar to it? |
| HTTP | `GET /api/v1/products/{product_id}` | `POST /api/v1/recommendations` |
| Service | `ProductionProductServingService.get_product` | `ProductionRecommendationServingService.recommend`, called from `_PerRequestRecommendationServingService` |
| Database | One `SELECT` by primary key | Seed `SELECT`, generator reads, then more lookups for features |
| Result | Display fields for one row | Ranked neighbor ids |

The storefront uses both. `ProductDetailView` loads the product first. Only after that succeeds does it post the product id as `seed_product_id`.

## 2. Product-detail request

`ProductPage` in `frontend/app/products/[id]/page.tsx` awaits the route param, decodes it, and renders `ProductDetailView`. That component runs in the browser.

1. **Open the page.** A card link is `/products/{id}` with `encodeURIComponent`. The page passes `decodeURIComponent(id)` into `ProductDetailView`. Input: the path segment. Output: `productId`.
2. **Request.** `getProduct` calls `requestJson` with `GET /api/v1/products/{id}`. The id is encoded again. There is no JSON body. `apiBaseUrl()` is `NEXT_PUBLIC_PRODUCTIQ_API_URL` or `http://localhost:8000`.
3. **Match the route.** `get_product` in `src/productiq/api/routes/products.py` takes `product_id: str`. FastAPI does not run a Pydantic body model. An unknown path is not this step.
4. **Dependency.** `ProductServiceDep` calls `get_product_service`, which reads `app.state.product_service`. Production startup stored `ProductionProductServingService` around `PostgresProductCatalogReadProvider`. A missing service raises `ConfigurationError`.
5. **Service.** `get_product` strips the id. An empty string raises `ValueError` (`product_id must not be empty`). It then calls the provider.
6. **Read.** `PostgresProductCatalogReadProvider.get_product` opens a session, runs `select(Product).where(Product.product_id == product_id)`, and closes the session in `finally`. It does not `commit()`.
7. **Narrow the row.** A missing row returns `None`. A row becomes `ProductCatalogReadModel` with eight fields: `product_id`, `brand`, `brand_normalized`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`.
8. **Public model.** If the provider returns `None`, the service raises `ProductNotFoundError("Product not found.")`. Otherwise `product_read_model_to_api` builds `ProductApiResponse` and adds `request_id`. It does not copy `brand_normalized`.
9. **JSON.** The route declares `response_model=ProductApiResponse`, so FastAPI serializes that model.
10. **Render.** `ProductDetailView` calls `productToCard`. `description` is the title. Brand, image, type, and gender come from the same object. `request_id` is not copied onto the card.

The handler is a normal `def`. The browser call is `async`.

## 3. From the row to the card

| Object | Role | What it keeps |
| --- | --- | --- |
| `Product` | SQLAlchemy row in `src/productiq/database/models/product.py` | Every catalog column, including `embedding`, both prices, color, and garment attributes. `brand` is non-null on the table |
| `ProductCatalogReadModel` | Serving read boundary in `product_schema.py` | The eight fields listed above. `brand` is typed as optional |
| `ProductApiResponse` | HTTP JSON | Those fields except `brand_normalized`, plus required `request_id` |
| `ProductResponse` | TypeScript description in `frontend/lib/types.ts` | The same JSON names. It is not checked field-by-field at runtime |
| `ProductCardModel` | UI object from `productToCard` | CamelCase display fields and an optional `rank` or `unavailable` flag |

`embedding` and the price columns stop in the provider. `brand_normalized` stops in `product_read_model_to_api`. The card then drops `request_id`.

`ProductRepository.get_by_id` can also load a `Product`, but `get_product` does not call it.

## 4. Missing product

The provider returns `None` when `session.scalar` finds no row. The service raises `ProductNotFoundError`. `productiq_error_handler` calls `map_http_exception_to_api_error`, which maps that type to code `NOT_FOUND` and the fixed message `Product not found.` `http_status_for_api_error` maps the code to `404`.

The body is `{"error": {"code": "NOT_FOUND", "message": "Product not found.", "request_id": ...}}`. `tests/api/test_product_route.py` asserts that message. It was not re-run.

`ProductDetailView` treats `ProductIqApiError` with `status === 404` as a missing state and shows `error.message`. Other failures use that message or `Could not load this product.` A network failure or timeout is not a `404`.

An empty id after `strip` is a `ValueError` from the service, which maps to `400` `INVALID_REQUEST`, not to not-found. The storefront does not send that case on purpose.

## 5. Recommendation request and seed

A seed is the product the neighbors are computed from. The storefront sends the id it just loaded.

`getRecommendations` posts `{ seed_product_id, top_k }` to `/api/v1/recommendations`. It omits `recommendation_type`, so `RecommendationApiRequest` uses the default `similar`. `ProductDetailView` passes `RECOMMENDATION_TOP_K`, which is `8`. It does not send `filters`.

Illustrative body, matching the schema and that caller:

```json
{ "seed_product_id": "462494766003", "top_k": 8 }
```

`post_recommendations` receives the body, `RecommendationServiceDep`, and the request id. `get_recommendation_service` reads `app.state.recommendation_service`. On the production branch that object is `_PerRequestRecommendationServingService`, not a pipeline built at startup.

`recommend` opens one session from `create_session_factory`, calls `build_production_recommendation_pipeline` with that session, then `ProductionRecommendationServingService.recommend`. The `finally` block closes the session. Vector search and embedding reads use `engine.connect()` on the same engine. They do not use this session.

`ProductionRecommendationServingService.recommend` builds a `RecommendationRequest` from the public fields. That model strips `seed_product_id`. It then calls `self._pipeline.recommend_with_metadata`.

Seed lookup is `PostgresRecommendationCatalog.resolve_seed_product`, which delegates to `PostgresSeedProductResolver`. The statement is `select(Product).where(Product.product_id == seed_product_id)`. No row raises `CatalogValidationError` whose text contains `catalog row missing for seed product_id`. `map_http_exception_to_api_error` turns that into HTTP `404` and the message `Seed product not found`. `test_missing_seed_product_not_found` asserts the message and that the id is absent from the body. The pipeline calls this resolver, and `generate_recommendation_candidates` calls `resolve_seed_product` again on the same catalog and session.

A present row becomes a `ProductRepresentation` through `product_orm_to_canonical_record` and `build_product_representation`.

`assert_production_recommendation_request` allows only `RecommendationType.SIMILAR` and rejects `continue_on_generator_failure=True`.

## 6. Recommendation pipeline

`recommend_with_metadata` in `src/productiq/recommendation/recommendation_pipeline.py` is the live sequence.

1. Validate the request, the implemented type, and the production guardrails. The pool must be at least `request.top_k`. The default pool is `DEFAULT_CANDIDATE_POOL_TOP_K` (`50`). The storefront's `8` is under that.
2. Resolve the seed, as above.
3. `generate_recommendation_candidates`.
4. If the candidate tuple is empty, return `RecommendationResponse` with an empty `recommendations` tuple and the requested `top_k`. That is a successful empty result.
5. Otherwise load candidate context, compute content similarity, extract `RecommendationFeatures`, rank, then `select_recommendations_for_request`.

Production builds the generators in this order, in `build_production_recommendation_generators`:

| Order | Class | How it gets candidates |
| --- | --- | --- |
| 1 | `VectorRecommendationCandidateGenerator` | Loads the seed embedding with `PostgresSeedEmbeddingProvider` (`SELECT embedding::text ... WHERE product_id = :id AND embedding IS NOT NULL`). Searches the same pgvector index as search, with `top_k` of pool plus one. Drops the seed hit. Keeps at most `50`, with `candidate_generation_score` set to similarity. Source `vector` |
| 2 | `AttributeRecommendationCandidateGenerator` | Calls `PostgresRecommendationCatalog.list_catalog_products()`, which runs `select(Product)` with no `WHERE`. Scores every other product with `attribute_generation_score`, drops scores at or below `0`, sorts, and keeps `50`. Source `attribute` |
| 3 | `BM25RecommendationCandidateGenerator` | Builds lexical text from the seed, takes the posting union, drops the seed id, scores with `BM25Scorer`, and keeps `pool_top_k`. Source `bm25` |

`generate_recommendation_candidates` loops that sequence. The config flags `enable_vector_generator`, `enable_attribute_generator`, and `enable_bm25_generator` are defined on `RecommendationCandidateGenerationConfig` and default to true. Nothing in `src/productiq/recommendation` reads them except the field definitions. The live path runs the three generators because they were placed in the tuple, not because those flags are checked.

`continue_on_generator_failure` defaults to `False`. The production assert rejects `True`. A generator exception therefore becomes `RecommendationError` and does not continue with the other generators. There is no silent skip on the production request.

After the loop:

- `merge_recommendation_candidates` unions by `product_id`. It does not add scores across sources. One id keeps the sources that found it. `candidate_generation_score` is taken from the first present source in the order vector, BM25, attribute.
- `exclude_seed_product` drops the seed. It runs again after filtering.
- `filter_recommendation_candidates` applies `request.filters` only when a constraint is non-null. The storefront sends no filters, so this returns the merged tuple unchanged.
- `sort_candidate_pool_deterministically` sorts by `product_id`.
- `apply_candidate_pool_top_k` then keeps the first `50` of that id-sorted tuple.

The second seed exclusion is the same predicate: `product_id != seed_product_id`. Generators also skip the seed themselves. The ranker drops the seed from features a third time in `_exclude_seed_features`, and `validate_seed_product_excluded` checks the ranked tuple.

The attribute generator's full-table `SELECT` is part of this request. It is not limited to the vector hits.

## 7. Baseline recommendation ranking

This ranker is `BaselineRecommendationRanker` and `rank_recommendations` in `src/productiq/recommendation/baseline_ranker.py`. It is not `run_baseline_ranking_stage`. Search uses that other function on fused search candidates. Recommendations use this one on `RecommendationFeatures`.

The pipeline calls `rank_recommendations` with `self.ranker.config`. `BaselineRecommendationRanker.rank` is a wrapper around the same function. Production constructs `BaselineRecommendationRanker()` with the default config.

Input is a sequence of `RecommendationFeatures`. Each row has:

- `generation`: which generators found the id, source count, and `candidate_generation_score`
- `similarity`: `semantic_similarity` and `lexical_similarity` from `ContentSimilarityEngine`
- `structured`: overlaps and matches for brand, gender, type, color, pattern, material, fit, sleeve, neckline, features, and style
- `catalog`: prices and price deltas from the seed, when the context has them

`compute_baseline_recommendation_score` multiplies normalized feature values by `BaselineRecommendationRankerConfig` weights and sums them. The numeric defaults of those weights were not copied here. The sort key is that score, with `product_id` as the tie break. The call in the pipeline passes `top_k=pool_top_k` (`50`), so this step can return up to the pool, not only `8`.

Each output row is a `RankedRecommendation`: `product_id`, `rank`, `recommendation_score`, and the optional nested candidate.

`select_recommendations_for_request` then keeps at most `request.top_k` (`8` from the storefront). The default `RecommendationSelectionConfig` sets `max_per_brand` and `max_per_product_type` to `None`, which the field text describes as disabling those caps. `strict_constraints` defaults to true. With no request filters, the generation filter already skipped constraint checks.

`recommendation_response_to_api` copies `recommendation_score` onto `RecommendationResultItem`. The public JSON includes it. The nested candidate, sources, and `candidate_generation_score` stay off the response.

## 8. Response and the product page

Internal result: `RecommendationResponse` inside `RecommendationPipelineResult`. The HTTP mapper keeps seed id, type, `top_k`, items of `product_id`, `rank`, and `recommendation_score`, plus `request_id` and `returned_count`.

`ProductDetailView` calls `getRecommendations` only after `getProduct` succeeds. It drops any item whose `product_id` equals the seed, even though the server also excludes the seed. An empty list sets the note `No similar pieces were returned for this product.` Otherwise it calls `loadProductCards` with `{ productId, rank }` and `withoutSeed`. The score is not passed to `productToCard` or `ProductCard`. `ProductCard` has no score field.

A recommendation `ProductIqApiError` does not replace the product. The view stores `error.message` as `recommendationNote` and still renders the product. That split is why the two HTTP calls are separate.

## 9. Search versus recommendations

| | Live search | Recommendations |
| --- | --- | --- |
| Purpose | Ids for a text query | Ids similar to one product |
| Input | `query`, `top_k`, optional `filters` | `seed_product_id`, `top_k`, optional type and filters |
| Candidate sources | `BM25Retriever` and `SemanticRetriever` on the query text | Vector search from the seed embedding, attribute scores over the catalog, BM25 on seed text |
| Combination | Reciprocal rank fusion, `k` of `60` | Union by `product_id`, no score sum |
| Filtering | After fusion, when constraints are active | After the merge, when request filters are active. The storefront sends none |
| Ranking | `run_baseline_ranking_stage` then `rank_candidates` | `rank_recommendations`, then `select_recommendations_for_request` |
| Seed | None | Required. Removed before the public list |
| Output | `product_id`, `rank` | `product_id`, `rank`, `recommendation_score` |
| Public scores | None on `SearchResultItem` | `recommendation_score` is in the JSON and not on the card |
| Pipeline | `ProductionRetrievalPipeline.retrieve_ranked` | `RecommendationPipeline.recommend_with_metadata` |
| Endpoint | `POST /api/v1/search` | `POST /api/v1/recommendations` |
| When built | Search pipeline at startup | Recommendation pipeline inside each `recommend` call, one new session |

## 10. Error handling

| Case | Behavior |
| --- | --- |
| Invalid recommendation JSON, non-`similar` type, `top_k` of `0` or above the API cap | `RequestValidationError` before the handler. HTTP `400`, message `Request validation failed` |
| Seed id missing from `products` | `CatalogValidationError`, HTTP `404`, message `Seed product not found` |
| Product detail id missing | `ProductNotFoundError`, HTTP `404`, message `Product not found.` |
| No candidates after generation | HTTP `200` and an empty `recommendations` list. The page keeps the product and shows the empty note |
| A generator raises, with the default `continue_on_generator_failure=False` | `RecommendationError`. HTTP `500` `INTERNAL_ERROR`. Later generators do not run |
| `continue_on_generator_failure=True` | `assert_production_recommendation_configuration` raises `RecommendationError` before generation. Production does not use the skip path |
| `RecommendationError` from ranking or selection | HTTP `500` `INTERNAL_ERROR` |
| `CatalogValidationError` that is not the missing-seed text, including a missing embedding or missing filter row | HTTP `503` `SERVICE_UNAVAILABLE` |
| Any other exception | HTTP `500`, message `An unexpected error occurred` |
| Recommendation service not configured | HTTP `503` `CONFIGURATION_ERROR` |
| Recommendation HTTP failure in the browser | Product stays visible. The note is the API message, or `Recommendations are unavailable.` |

`loadProductCards` still turns a failed neighbor `GET` into an unavailable card, except for network and timeout, which abort the group. That is the same helper search uses.

## 11. Interview questions and answers

**What is a seed product?** The product the recommendation request is about. The JSON field is `seed_product_id`. `PostgresSeedProductResolver` loads that row and builds a `ProductRepresentation`.

**Why use several generators?** Each one proposes neighbors differently: nearest embeddings, shared attributes, and BM25 over the seed text. `merge_recommendation_candidates` keeps one row per id and records which sources found it.

**What is candidate generation?** The step that proposes ids before scoring the final list. `generate_recommendation_candidates` runs the generators, merges, drops the seed, and sorts by id.

**How does seed exclusion work?** Generators skip the seed. `exclude_seed_product` removes it twice around filtering. `_exclude_seed_features` removes it again before scoring. `validate_seed_product_excluded` checks the ranked output. The page also filters the seed id before drawing cards.

**How is recommendation ranking different from search ranking?** Search calls `run_baseline_ranking_stage` on fused `RetrievalCandidate`s. Recommendations call `rank_recommendations` on `RecommendationFeatures`, which include similarity to the seed and attribute overlap. The public recommendation item includes `recommendation_score`. The search item does not.

**What if the seed does not exist?** The resolver raises `CatalogValidationError`. The HTTP mapper returns `404` and `Seed product not found`. The product page shows that message as the recommendation note if the product request itself succeeded, or as a missing product if `getProduct` was the call that 404'd.

**Why separate product details from recommendations?** Detail is one indexed lookup and can render alone. Recommendations can fail, return an empty list, or take longer. `ProductDetailView` catches the recommendation error and still shows the product.

**What is the read provider?** `PostgresProductCatalogReadProvider` is the object `get_product` uses. It returns `ProductCatalogReadModel` or `None`. It is not `ProductRepository`.

**Why can the JSON contain a score the UI hides?** `recommendation_response_to_api` copies `recommendation_score`. `ProductDetailView` passes only `product_id` and `rank` into `loadProductCards`. `ProductCard` has nowhere to show the score.

**What does one recommendation request do in the database?** It opens one session for the seed row, the full catalog scan inside the attribute generator, and later context lookups. Embedding and vector search use separate `engine.connect()` calls.

**What is the pool versus `top_k`?** Generators and the ranker use `candidate_pool_top_k`, default `50`. Selection then keeps at most the request `top_k`, which the page sets to `8`.

**What happens when a generator throws?** With the production default, the pipeline raises `RecommendationError` and the client gets `500`. The code does not fill in results from the generators that already finished.

**Does an empty recommendation list mean the product is missing?** No. An empty list is HTTP `200`. A missing product detail is HTTP `404`. A missing seed is also `404`, with a different message.

**Which ranker is on this path?** `BaselineRecommendationRanker` via `rank_recommendations`. `assert_no_experimental_recommendation_rankers` returns without loading another model. Learning-to-rank is not called here.

## 12. Practical exercises

**1. Trace one detail read.** Start at `get_product` in `products.py`. Hint: the provider constructor lists eight fields, and the mapper omits `brand_normalized`. Outcome: you can list what the browser cannot see from the row.

**2. Find the 404.** Follow `ProductNotFoundError` into `map_http_exception_to_api_error`. Hint: the message is a fixed string in that function, and the status comes from `HTTP_STATUS_BY_API_ERROR`. Outcome: you can separate not-found from an unexpected exception.

**3. Name the three generators in order.** Open `build_production_recommendation_generators`. Hint: vector, then attribute, then BM25. Outcome: you can say what each one queries.

**4. Count the seed exclusions.** Search for `exclude_seed_product` and `_exclude_seed_features`. Hint: generation excludes twice, and ranking excludes features before scoring. Outcome: you can explain why the seed should not appear in `recommendations`.

**5. See the hidden score.** Open `recommendation_response_to_api` and the `getRecommendations` handler in `ProductDetailView`. Hint: the mapper copies `recommendation_score`, and the view's `loadProductCards` input does not. Outcome: you can explain a public field the card does not render.

## 13. Source-reading order

1. `frontend/app/products/[id]/page.tsx` — the id enters `ProductDetailView`.
2. `frontend/components/ProductDetailView.tsx` — `getProduct`, then `getRecommendations`.
3. `frontend/lib/api.ts`, `getProduct` and `getRecommendations` — the two calls.
4. `src/productiq/api/routes/products.py`, `get_product` — the detail handler.
5. `src/productiq/serving/product_service.py`, `get_product` — strip, lookup, not-found.
6. `src/productiq/serving/postgres_catalog_provider.py` — the `SELECT` and the eight fields.
7. `src/productiq/serving/mappers.py`, `product_read_model_to_api` — the public product fields.
8. `src/productiq/api/routes/recommendations.py`, `post_recommendations` — the recommendation handler.
9. `src/productiq/api/services/production_stack.py`, `_PerRequestRecommendationServingService.recommend` — one session per request.
10. `src/productiq/serving/performance/recommendation_production_wiring.py`, `build_production_recommendation_pipeline` — catalog, three generators, ranker.
11. `src/productiq/serving/recommendation_service.py`, `recommend` — public request to `RecommendationRequest`.
12. `src/productiq/recommendation/recommendation_pipeline.py`, `recommend_with_metadata` — seed, generation, features, rank, selection.
13. `src/productiq/recommendation/candidate_generation.py` — generator loop, merge, `exclude_seed_product`.
14. `src/productiq/recommendation/generators/vector.py`, `attribute.py`, and `bm25.py` — how each list is built.
15. `src/productiq/recommendation/seed_product.py`, `PostgresSeedProductResolver` and `list_catalog_products`.
16. `src/productiq/recommendation/baseline_ranker.py`, `rank_recommendations` — score, seed drop, order.
17. `src/productiq/serving/mappers.py`, `recommendation_response_to_api` — the public score.
18. `frontend/lib/catalog.ts`, `productToCard` and `loadProductCards` — cards for the neighbor ids.

## 14. Accuracy and unresolved questions

Verified by reading the functions above. No test was executed. `tests/api/test_product_route.py` and `tests/api/test_recommendation_route.py` were read in the HTTP note for the not-found messages. They were not re-run.

Confirmed:

- Detail uses `PostgresProductCatalogReadProvider`, one session per lookup, eight columns, then the API mapper.
- Production recommendations build the pipeline inside `recommend` and close that session in `finally`.
- The generator order is vector, attribute, BM25.
- `continue_on_generator_failure` defaults to false, and production rejects true.
- The attribute generator selects every `Product` row.
- `recommendation_score` is on the HTTP item and not on `ProductCard`.
- Empty recommendations are a normal `RecommendationResponse`, not an exception.

Not established here:

- The numeric default weights in `BaselineRecommendationRankerConfig`. The scorer uses them. Their values were not copied.
- Whether `enable_vector_generator` and the sibling flags affect any caller outside `src/productiq/recommendation`. Inside that package they are only field defaults. The production tuple does not consult them.
- How many rows `attribute_generation_score` keeps before the pool cut, for a real seed. The code scores the catalog, then slices to `50`.
- The stage timings inside `RecommendationPipelineResult.execution`. The HTTP mapper does not copy that object. This note does not claim the client can read it.
