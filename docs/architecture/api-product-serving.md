# Phase 13.5 — Product / Catalog API Serving

**Status:** Product read HTTP endpoint wired through catalog provider boundary  
**Builds on:** Phase 13.1 product contracts, Phase 13.2–13.4 HTTP patterns  
**Defers:** PostgreSQL repository reads, Redis caching, default app loading of full Parquet

## Endpoint

| Method | Route | Handler |
|--------|-------|---------|
| GET | `/api/v1/products/{product_id}` | `ProductServingService.get_product()` |

## Request lifecycle

```text
GET /api/v1/products/{product_id}
    ↓
ProductServiceDep + RequestIdDep
    ↓
ProductionProductServingService.get_product()
    ↓
ProductCatalogReadProvider.get_product()
    ↓
ProductCatalogReadModel | None
    ↓
product_read_model_to_api()
    ↓
ProductApiResponse JSON
```

## Serving components

| Layer | Module |
|-------|--------|
| Read provider protocol | `productiq.serving.catalog_read.ProductCatalogReadProvider` |
| In-memory provider | `InMemoryProductCatalogReadProvider` |
| Processed Parquet provider | `ProcessedParquetProductCatalogReadProvider` |
| Service | `ProductionProductServingService` |
| HTTP route | `productiq.api.routes.products` |
| Wiring | `productiq.api.services.product_wiring` |

## Catalog components reused

- **Processed schema columns** aligned with `data.export.schema` / `productiq.database.catalog_contract` (`product_id`, display facets)
- **Canonical row shape** consistent with `make_product_record` / processed export tests
- **ORM mapping reference** — `product_orm_to_canonical_record` field names inform read columns (no ORM in HTTP path for 13.5)
- **Phase 13.1** — `ProductCatalogReadModel`, `ProductApiResponse`, `product_read_model_to_api`

## Storage boundary

- Provider owns storage access; routes and serving service do not read Parquet/SQL directly.
- `ProcessedParquetProductCatalogReadProvider` reads the processed catalog **once** at construction, indexes by `product_id`, serves O(1) lookups.
- Uses processed Parquet subset columns only (no embeddings, attributes blob, or price columns in public API).

## Product ID semantics

- `product_id` is a non-empty string matching processed catalog identities (e.g. `"123456789001"`).
- HTTP path parameter is stripped before lookup; empty → **400** `INVALID_REQUEST`.

## Not-found behavior

Absent `product_id` → `ProductNotFoundError` → **404** `NOT_FOUND`, message **Product not found.** (no storage details).

## Error semantics

| Case | HTTP | Code |
|------|------|------|
| Missing product | 404 | `NOT_FOUND` |
| Empty product_id | 400 | `INVALID_REQUEST` |
| Unconfigured service | 503 | `CONFIGURATION_ERROR` |
| `CatalogLoadError` | 503 | `SERVICE_UNAVAILABLE` |
| Unexpected | 500 | `INTERNAL_ERROR` |

## Dependency injection

`create_app(product_service=...)` sets `app.state.product_service`. Unset → **503** on product routes.

## Public vs internal fields

**Public:** `product_id`, `brand`, `description`, `image_url`, `product_url`, `category_gender`, `product_type`, `request_id`.

**Not exposed:** `brand_normalized`, embeddings, retrieval/ranking features, attribute/engine columns, database paths.

## Lifecycle / reuse

Construct provider (and service) at application startup; reuse across requests. Do not read full Parquet per HTTP request.

## Limitations

- Default `create_app()` does not load processed catalog; inject `product_service` explicitly.
- Parquet provider loads entire catalog into memory (acceptable for Phase 13.5; PostgreSQL/Redis deferred).
- No list/search/browse endpoints.

## Future compatibility

- Swap `ProductCatalogReadProvider` implementation for `ProductRepository` / PostgreSQL without changing routes.
- Add Redis in front of provider in a later performance phase.

## Related

- Notebook: `notebooks/data_engineering/70_api_product_serving.ipynb`
