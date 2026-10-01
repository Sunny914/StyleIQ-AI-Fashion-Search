# Phase 14B — Runtime artifact & database deployment contract

**Status:** Runtime dependencies resolved from Phase 14A `Settings`; validation and manifests for Docker prep (Phase 15).

## Runtime dependency graph

```text
FastAPI (create_app)
    ├── Settings / ServingConfig (14A)
    ├── RuntimeArtifactPaths (14B — path resolution only at app build)
    ├── Product API (optional) ──► processed catalog parquet (first-use load)
    ├── Search / Recommendation (optional) ──► PostgreSQL + pgvector + BM25 index artifacts
    └── Health /ready ──► configured services (no automatic DB probe in default API)
```

```text
Application services
        ↓
PostgreSQL (DATABASE_URL)
        ↓
pgvector extension + products.embedding vector(384)
        ↓
HNSW index (cosine) + catalog tables
```

Lexical search paths consume **BM25 pickle** artifacts; semantic/RRF paths consume **PostgreSQL pgvector** state (often loaded from **embeddings parquet** via existing loaders — unchanged in 14B).

## Artifact ownership

| Artifact | Typical path (dev default) | Manifest | Checksum in manifest |
|----------|----------------------------|----------|----------------------|
| Processed catalog | `resources/processed/product_catalog.parquet` | `product_catalog.manifest.json` | sha256 when present |
| BM25 index | `resources/processed/bm25_lexical_index.pkl` | `bm25_lexical_index.manifest.json` | sha256 when present |
| Embeddings | `resources/processed/product_embeddings.parquet` | `product_embeddings.manifest.json` | sha256 when present |
| Model artifacts | `resources/models/` | none standard | unspecified |

14B does **not** regenerate artifacts or verify checksums against file bytes unless a manifest is present (metadata read only).

## Artifact resolution

Code: `productiq.config.runtime_artifacts.resolve_runtime_artifact_paths(settings)`.

- Catalog, embeddings, model dir: direct `Settings` fields.
- BM25: accepts configured directory, `.pkl` file, or legacy pickle beside catalog parent (ProductIQ repo layout).

`create_app` stores resolved paths on `app.state.runtime_artifact_paths` (no file I/O).

Product wiring: `resolved_processed_catalog_path()` / `create_product_serving_service_from_settings()`.

## Validation behavior

Code: `productiq.config.runtime_validation`.

| Check | When | Loads content? |
|-------|------|----------------|
| Path exists (file/dir) | Deployment check / explicit call | No |
| Manifest metadata | Manifest read | JSON only |
| Catalog parquet | Product provider construct | Yes (first use) |

Missing artifacts → `ConfigurationError` with role labels (no absolute paths/passwords to API clients).

## Database contract

Code: `productiq.config.database_runtime.postgres_runtime_contract()`.

- Driver: `postgresql+psycopg` (via existing engine normalization)
- Extension: `vector` (pgvector)
- Table: `products`, column `embedding`, dimension **384**
- Index: `ix_products_embedding_hnsw_cosine` (`vector_cosine_ops`)
- Schema versions: catalog DB `1.0.0`, vector catalog `1.1.0` (existing constants)

Connection configuration remains **DATABASE_URL** or 14A component fields.

## Startup / lazy loading

Importing `create_app` must not:

- open PostgreSQL
- load BM25 / embeddings / models
- download models

Lifespan (Phase 13) still only logs configured service names.

## Deployment manifest

- JSON builder: `build_deployment_manifest(settings=...)`
- Committed template: `resources/deployment/productiq_deployment_manifest.json`
- Includes application entrypoint, DB/pgvector contract, artifact paths, env var names, `/health` and `/ready`

No Docker Compose / Kubernetes in 14B.

## Development vs production

| | Development | Production |
|---|-------------|------------|
| Artifact paths | Relative defaults under `resources/` | Set `PRODUCTIQ_*` paths to mounted volumes |
| Database | Local DSN default if unset | Explicit `DATABASE_URL` / secrets |
| Validation | Opt-in deployment checks | Run manifest + artifact checks before rollout |

See also [deployment-configuration.md](deployment-configuration.md) (14A).
