# Database operations and transactions

This note explains how ProductIQ reads and writes the `products` table in PostgreSQL, including how a session and a transaction bound those writes.

It assumes the HTTP routes and the public models from the earlier engineering notes. It does not explain BM25 scoring, Reciprocal Rank Fusion, or the baseline ranker. Those steps are named only where they issue a database read.

The details were read from the current source. No query was sent to PostgreSQL, and no test was executed.

## 1. Why this database is here

PostgreSQL stores the catalog that search and product detail read at request time. The table is `products`. Each row is one catalog product, identified by `product_id`.

Two kinds of read use that table:

- Ordinary lookups compare `product_id`, or read columns such as `brand` and `description`. Product detail, search filtering, ranking context, and the recommendation seed use this kind of read.
- Vector search compares the `embedding` column. That column is a pgvector `vector(384)`. pgvector is the PostgreSQL extension that stores those vectors and can search them with an HNSW index. HNSW is a graph index for nearest-neighbor search. The search SQL orders rows by cosine distance (`<=>`) and returns `product_id` plus that distance.

The public search response is still only ids and ranks. The database work that produces those ids stays inside retrieval. Product text is a second query, by id, through `PostgresProductCatalogReadProvider`.

Starting the API does not load the Parquet catalog. `load_runtime_catalog` is a separate operator command. `build_production_application_services` only counts rows and embeddings before it serves traffic.

## 2. Database fundamentals

A small picture first. A notebook page has one line per shirt. The line number is unique. You can add a line, change a line, read a line, or remove a line. You can write ten lines and then decide those ten lines are finished. If the pen breaks before you decide they are finished, those ten lines are discarded. Lines you already marked finished stay on the page.

| Idea | Meaning | ProductIQ |
| --- | --- | --- |
| Table | The page | `products`, from `PRODUCTS_TABLE_NAME` |
| Row | One line | One `Product` instance |
| Column | One box on the line | `product_id`, `description`, `embedding`, and the other mapped columns |
| Primary key | The value that identifies one row | `product_id`, declared `primary_key=True` |
| SQL | The language sent to PostgreSQL | The string in `_UPDATE_EMBEDDING_SQL`, or a SQLAlchemy `select(Product)` |
| `SELECT` | Read rows | `select(Product).where(Product.product_id == product_id)` |
| `INSERT` | Add rows | The insert half of the catalog upsert |
| `UPDATE` | Change existing rows | `UPDATE products SET embedding = CAST(:embedding AS vector) WHERE product_id = :product_id` |
| `DELETE` | Remove rows | No application function deletes `products` rows |
| Session | A short-lived handle that groups ORM work | `sessionmaker(...)()` in the loader and in request helpers |
| Transaction | A group of statements that succeed or are undone together | The work between two `commit()` calls, or the block inside `engine.begin()` |
| `COMMIT` | Mark the current group as durable | `session.commit()` after a Parquet chunk |
| `ROLLBACK` | Undo the current group | `session.rollback()` in the loader's `except` block |
| Upsert | Insert a row, or update it when the key already exists | `insert(...).on_conflict_do_update(index_elements=[product_id], ...)` |
| Batch | A limited number of rows per step | Parquet chunks of `DEFAULT_CATALOG_LOAD_CHUNK_SIZE` (`10000`), then smaller statements under PostgreSQL's parameter limit |
| Index | An extra structure that speeds a lookup | B-tree indexes in `Product.__table_args__`, and the HNSW index `ix_products_embedding_hnsw_cosine` |
| Vector column | A column that stores a list of numbers | `embedding`, type `Vector(384)` |

A primary key is unique. ProductIQ uses that uniqueness as the conflict target of the upsert. There is also a check constraint, `ck_products_source_ajio`, which requires `source` to equal the AJIO source name. A check constraint limits allowed values. It is not a second identity for the row.

## 3. Data-access components

These objects all talk to `products`. They are separate because they do different jobs. The class name is a hint. The methods are the evidence.

| Component | File | What it actually does | Who calls it |
| --- | --- | --- | --- |
| `Product` | `src/productiq/database/models/product.py` | SQLAlchemy model of one row. SQLAlchemy is the library that maps Python objects to tables | Every query in this note |
| `ProductRepository` | `src/productiq/database/repository.py` | Read-only methods: `get_by_id`, `find_by_brand`, `find_by_category`, `find_by_color`, `find_filtered`, `count` | `ProductCatalogLoader.load_from_parquet` calls `count` before and after the load. Tests construct it directly. The product HTTP route does not |
| `PostgresProductCatalogReadProvider` | `src/productiq/serving/postgres_catalog_provider.py` | One `SELECT` by `product_id`, then a `ProductCatalogReadModel` with eight fields | `ProductionProductServingService`, wired in `build_production_application_services` |
| `ProductCatalogLoader` | `src/productiq/database/loaders/catalog_loader.py` | Chunked upsert from Parquet | `load_processed_catalog` |
| `load_product_embeddings_into_catalog` | `src/productiq/retrieval/vector_index_loader.py` | `UPDATE` of `embedding` for existing ids | `build_product_vector_index` |
| `create_product_catalog_tables` | `src/productiq/database/catalog_ddl.py` | `Base.metadata.create_all` for the `products` table, `checkfirst=True` | `load_processed_catalog` and `bootstrap_productiq_database` |
| `create_product_embedding_hnsw_index` | `src/productiq/database/vector_catalog.py` | `CREATE INDEX ... USING hnsw` unless the index already exists | `bootstrap_productiq_database` and `build_product_vector_index` |
| `create_engine_from_settings` | `src/productiq/database/engine.py` | Builds a SQLAlchemy engine from `settings.database_url`, with `pool_pre_ping=True` | Production startup and the load command |
| `create_session_factory` | `src/productiq/database/session.py` | Builds a `sessionmaker` with `autoflush=False`, `autocommit=False`, `expire_on_commit=False` | Production startup |

`ProductRepository` fits the usual meaning of a repository: a read API over the table. It has no insert, update, or delete method. `PostgresProductCatalogReadProvider` is a provider because it returns the serving read model, not the ORM row. The loader is neither. It owns the upsert.

`session_scope` in `session.py` is a helper that commits on success, rolls back on exception, and closes. The HTTP paths inspected below do not call it. They open a session and `close()` it themselves.

## 4. Read operations

None of these request paths call `ProductRepository`.

### Product details

`PostgresProductCatalogReadProvider.get_product` opens a session, runs `select(Product).where(Product.product_id == product_id)`, and closes the session in `finally`. No row returns `None`. The service then raises `ProductNotFoundError`. A row is copied into `ProductCatalogReadModel` using `product_id`, `brand`, `brand_normalized`, `description`, `image_url`, `product_url`, `category_gender`, and `product_type`. The provider does not `commit()`.

### Search filtering and ranking context

`_SessionFactoryCatalogFilter.filter_candidate_ids` opens a session and calls `PostgresCatalogCandidateFilter`. If the query has no active constraints, that method returns the candidate ids and does not query. If constraints are active, it runs `select(Product).where(Product.product_id.in_(candidate_product_ids))`. A missing id raises `CatalogValidationError`. The session is closed in `finally`.

`_SessionFactoryRankingContextProvider.load_contexts` does the same shape of lookup through `PostgresRankingProductContextProvider.load_contexts`, then builds `RankingProductContext` values. A missing id raises `CatalogValidationError`.

Vector search is separate. `search_products_by_embedding` uses `engine.connect()`, runs `SET hnsw.ef_search = ...`, then:

```sql
SELECT product_id,
       (embedding <=> CAST(:query_vector AS vector)) AS distance
FROM products
WHERE embedding IS NOT NULL
ORDER BY embedding <=> CAST(:query_vector AS vector), product_id ASC
LIMIT :top_k
```

The operator `<=>` is pgvector cosine distance. Rows with a null embedding are excluded. The function returns `VectorSearchPrimitiveHit` values (`product_id`, `distance`, `similarity`). It does not return catalog text.

### Recommendations

`_PerRequestRecommendationServingService.recommend` opens one session for the request and closes it in `finally`. Inside that session the pipeline uses:

- `PostgresSeedProductResolver.resolve_seed_product`: `select(Product).where(Product.product_id == seed_product_id)`. No row raises `CatalogValidationError` whose message contains `catalog row missing for seed product_id`. The HTTP layer maps that to `Seed product not found`.
- `PostgresSeedEmbeddingProvider`: `SELECT embedding::text FROM products WHERE product_id = :product_id AND embedding IS NOT NULL`, through `engine.connect()`.
- `AttributeRecommendationCandidateGenerator.generate`: calls `PostgresRecommendationCatalog.list_catalog_products()`, which runs `select(Product)` with no `WHERE`. That reads every catalog row in the session.
- `PostgresProductEmbeddingProvider.load_embeddings`: `SELECT product_id, embedding::text ... WHERE product_id IN :product_ids AND embedding IS NOT NULL`. A missing embedding raises `CatalogValidationError`.
- `PostgresRecommendationProductContextProvider` and `_LazyPostgresFilteringMap`: further `select(Product)` lookups by id on the same session.

Vector candidate generation uses the same `search_products_by_embedding` path as search, through the semantic retriever's vector index.

### Counts at startup

`inspect_catalog_runtime_status` calls `count_catalog_products` (`SELECT COUNT(*) FROM products`) and `count_products_with_embeddings` (`SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL`). When the product count is positive it also counts ids that start with `compose-demo-`. `build_production_application_services` stores that status. `build_readiness_response` later reports the stored counts. It does not run these statements again.

`ProductRepository.count` is the loader's before-and-after count. It is `select(func.count()).select_from(Product)` on the loader's session.

## 5. Catalog writes and upserts

`ProductCatalogLoader.load_from_parquet` is the metadata write.

1. When `validate_input` is true, `validate_processed_parquet` checks the file before any write.
2. `pq.ParquetFile` supplies `iter_batches(batch_size=self.chunk_size)`. The default `chunk_size` is `DEFAULT_CATALOG_LOAD_CHUNK_SIZE`, which is `10000`.
3. Each batch is reduced to `PROCESSED_COLUMN_ORDER`. That tuple has 22 names, from `product_id` through `style_attributes`. It does not include `embedding`.
4. `_dataframe_chunk_to_records` turns the batch into dictionaries. `pd.NA` and other pandas missing values become `None`.
5. One SQLAlchemy session is opened for the whole file. Its factory sets `autocommit=False`. `ProductRepository.count()` records the row count before any upsert.
6. `_upsert_records` builds a PostgreSQL insert of those dictionaries. The conflict target is `product_id`. On conflict, `set_` assigns every table column except `product_id` from the excluded row. The excluded row is the row PostgreSQL was about to insert.
7. A statement cannot exceed `POSTGRESQL_MAX_PARAMETERS` (`65535`). `MAX_UPSERT_ROWS_PER_STATEMENT` is `65535 // len(PROCESSED_COLUMN_ORDER)`. With 22 columns, that is `2978` rows per statement. A `10000`-row Parquet chunk is therefore several statements.
8. `session.commit()` runs once after every statement in that Parquet chunk has executed. It does not run after each 2978-row statement.
9. After the last chunk, `repository.count()` runs on the same session and the method returns a `CatalogLoadReport`.
10. On any exception, `session.rollback()` runs, then `CatalogLoadError` is raised with `Catalog load failed for table products`. The original exception is chained. `session.close()` runs in `finally` for both success and failure.

`rows_inserted` and `rows_updated` are computed only after a fully successful load. `rows_inserted` is the difference between the after count and the before count, floored at 0. `rows_updated` is derived from `rows_upserted` and that difference. The code does not ask PostgreSQL which rows were inserts and which were updates.

The conflict update lists every `Product` column except `product_id`, and the dictionaries do not contain `embedding`. For a column omitted from `INSERT`, PostgreSQL uses the column default in the proposed row. This model declares `embedding` nullable and does not set a server default, so the proposed value is null, and the conflict assignment writes that null. This follows from the statement the loader builds. It was not re-executed for this note. `load_runtime_catalog` then calls `build_product_vector_index`, which runs the embedding update after the catalog upsert.

`load_processed_catalog` calls `create_product_catalog_tables` first when `create_tables` is true, then the loader, then `validate_product_catalog`. Validation runs after the loader has returned, so after the chunk commits. A later `CatalogValidationError` does not roll those commits back. There is no rollback call between the loader and the validator.

The fixture path is different. `load_compose_integration_demo_catalog` builds three `compose-demo-*` rows and calls `session.merge` for each, including a 384-number embedding. One `session.commit()` follows the three merges. `merge` updates a row when the primary key already exists. It is not the Parquet upsert statement.

## 6. Embedding updates

`load_product_embeddings_into_catalog` updates vectors on rows that must already exist.

1. `ensure_product_vector_catalog_schema` makes sure the `vector` extension and the `embedding` column exist.
2. When `validate_catalog_alignment` is true, the function reads product ids from the Parquet file in batches of `DEFAULT_EMBEDDING_READ_BATCH_SIZE` and checks them with `SELECT product_id FROM products WHERE product_id = ANY(:product_ids)`. A duplicate id in the file, or an id missing from the table, raises `SemanticRetrievalError` before the updates start. The existence checks use batches of `_CATALOG_EXISTENCE_BATCH_SIZE` (`10000`).
3. Embeddings are then read in batches of `chunk_size`, default `DEFAULT_VECTOR_INDEX_LOAD_BATCH_SIZE` (`5000`).
4. `validate_embedding_vectors` checks the batch against `PRODUCTIQ_EMBEDDING_DIMENSION` (`384`).
5. Each batch runs inside `with engine.begin()`. For every row the code executes `_UPDATE_EMBEDDING_SQL`: `UPDATE products SET embedding = CAST(:embedding AS vector) WHERE product_id = :product_id`. The value is a text literal such as `[0.1,0.2,...]`, built by `_embedding_to_pgvector_literal`.
6. `rowcount` of `0` raises `SemanticRetrievalError` immediately, even though the alignment check already ran. That raise leaves the `engine.begin()` block by exception.
7. `engine.begin()` commits when the block finishes without an exception. An exception rolls that block's transaction back. The next Parquet batch uses a new `engine.begin()`.

`build_product_vector_index` calls this loader and then `create_product_embedding_hnsw_index(engine, rebuild=rebuild_hnsw)`. The default `rebuild_hnsw` is `False`. An existing index is left in place.

Before a full load, `validate_embedding_artifact_for_vector_index` also checks dimension `384`, the BGE model id, L2 normalization, cosine similarity, and, when `enforce_official_checksums` is true, the official checksum. `load_runtime_catalog` passes that flag through. The default in `load_runtime_catalog` is `False`. The default inside `build_product_vector_index` is `True` when a caller does not override it. The operator command turns the check on only with `--enforce-official-checksums`.

The column type `vector(384)` is the schema's dimension rule. The loader's `validate_embedding_vectors` is the application check on each batch. This note does not claim that PostgreSQL rejects a wrong-length literal beyond what that validator and the column type already express. The update path was not executed here.

## 7. CRUD support

PostgreSQL can delete a row. ProductIQ's application code and HTTP routes do not.

| Operation | Application code | HTTP endpoint |
| --- | --- | --- |
| Create the `products` table | Implemented. `create_product_catalog_tables` uses `create_all(..., checkfirst=True)`. It does not drop or alter an existing table | None |
| Create the `embedding` column when it is missing | Implemented. `ensure_product_embedding_column` runs `ALTER TABLE products ADD COLUMN embedding vector(384)` inside `engine.begin()` | None |
| Create the HNSW index | Implemented. `create_product_embedding_hnsw_index`. If the index exists and `rebuild` is false, the function returns. `rebuild=True` drops it first with `DROP INDEX IF EXISTS` | None |
| Insert or update catalog metadata | Implemented as upsert in `_upsert_records`. New ids insert. Existing ids update. The fixture path uses `session.merge` | None |
| Update embeddings | Implemented. `_UPDATE_EMBEDDING_SQL` | None |
| Read one product | Implemented. Provider `get_product` and repository `get_by_id` | `GET /api/v1/products/{product_id}` uses the provider |
| Read many products by id | Implemented. Filter, ranking context, recommendation context, and the attribute generator's full `select(Product)` | Indirectly, through `POST /api/v1/search` and `POST /api/v1/recommendations` |
| Read nearest vectors | Implemented. `search_products_by_embedding` | Indirectly, through search and recommendation vector generation |
| Count rows and non-null embeddings | Implemented. `count_catalog_products`, `count_products_with_embeddings`, `ProductRepository.count` | `GET /api/v1/ready` reports counts captured at startup. It does not query again |
| Delete product rows | Not implemented. No `DELETE FROM products` and no `session.delete` were found under `src/` | None |
| Change a product from the API | Not implemented. Search, product, and recommendation handlers do not commit catalog writes | None |

`drop_product_embedding_hnsw_index` deletes an index, not product rows. The default vector build does not call it.

## 8. Transactions and failures

A transaction here is the uncommitted work on one session, or the body of one `engine.begin()`.

### Catalog load timeline

Assume the default chunk size and a file with more than two chunks. This is the control flow in `load_from_parquet`, not a run against a database.

1. Open one session. Count rows. That read belongs to the session's first transaction.
2. Execute the upsert statements for Parquet chunk 1. They are still uncommitted.
3. `session.commit()`. Chunk 1 is durable. The next statement on this session starts later work.
4. Repeat for chunk 2. `commit()` makes chunk 2 durable.
5. Chunk 3's first statement executes. A later statement in chunk 3 raises.
6. The `except` block calls `session.rollback()`. That undoes chunk 3's uncommitted statements, including an earlier statement in the same chunk that had not reached `commit()`.
7. Chunks 1 and 2 remain committed. The function raises `CatalogLoadError` and does not return a report.
8. `finally` closes the session.

The whole file is not one transaction. A failed third chunk does not remove the first two. Recovery is another run of the same upsert: `ON CONFLICT (product_id) DO UPDATE` rewrites existing ids and inserts ids that never landed. Because the conflict update includes `embedding`, a rerun can clear embeddings that were loaded earlier, until the embedding step runs again. That consequence comes from the column list in `_upsert_records`, described in section 5.

`rows_inserted` is not available for a failed run. The variables used for the report are assigned only after the loop.

### Embedding-load timeline

Each `engine.begin()` block is its own transaction.

1. Alignment checks use `engine.connect()` and do not update rows.
2. Batch 1's updates run inside `engine.begin()`. The block ends, so that transaction commits.
3. Batch 2 hits `rowcount == 0` and raises `SemanticRetrievalError` inside its `engine.begin()` block.
4. That block rolls back. Batch 1 stays updated. The function does not return `VectorIndexLoadReport`.

Updates inside one batch are one transaction: the loop is inside a single `with engine.begin()`. They commit or roll back together. They are not one transaction per product id.

### Reads

The request helpers do not call `commit()` or `rollback()`. They call `session.close()` in `finally`, including when the query raises. `search_products_by_embedding` and the embedding providers use `engine.connect()` and do not call `commit()`. This note does not add a guarantee about pooled connection settings beyond the `SET hnsw.ef_search` statement those functions execute.

`session_scope` would commit on a clean exit. The paths above do not use it, so a read does not become a committed write.

## 9. Lifecycle and safety

`create_engine_from_settings` reads `settings.database_url` and rewrites a `postgresql://` prefix to `postgresql+psycopg://`. The engine uses `pool_pre_ping=True`, which checks a pooled connection before use. The URL itself is configuration. This note does not copy it.

`create_session_factory` does not open a connection by itself. A session is opened when code calls the factory, as the loader and the request helpers do.

When `PRODUCTIQ_ENABLE_PRODUCTION_SERVING` is on, `create_app` calls `build_production_application_services`. That function creates an engine, runs `inspect_catalog_runtime_status`, and raises `ConfigurationError` when the mode is `empty`. It does not call `load_runtime_catalog`. Fixture mode builds a BM25 index by selecting every `Product` once at startup, in `_bm25_from_postgres_descriptions`. Other modes load the BM25 artifact from disk.

During a request, search opens a session for filtering and another for ranking context, and the vector search opens a connection. Recommendations open one session for the pipeline and additional connections for seed embeddings, candidate embeddings, and vector search. Those sessions are closed when the helper's `finally` runs.

`build_lifespan` does not load the catalog. On shutdown, if `app.state.production_serving_runtime` is set, it calls `runtime.engine.dispose()`. `load_runtime_catalog`'s `main` also calls `engine.dispose()` in its own `finally`.

Commands that change the database:

- `python -m productiq.database.load_runtime_catalog`, default `--mode fixture`
- `load_processed_catalog` and `ProductCatalogLoader.load_from_parquet`
- `build_product_vector_index` and `load_product_embeddings_into_catalog`
- `bootstrap_productiq_database`, including index creation
- `load_compose_integration_demo_catalog`

Importing `create_app` with production serving disabled does not open PostgreSQL. Importing it with production serving enabled counts the catalog and can load models. It still does not upsert Parquet.

## 10. Read-only SQL examples

These statements match the table and column names in `Product` and `vector_catalog.py`. They are illustrations. They were not run.

Count rows, the same count `count_catalog_products` issues:

```sql
SELECT COUNT(*) FROM products;
```

Read one product by primary key:

```sql
SELECT product_id, brand, description, category_gender, product_type
FROM products
WHERE product_id = '462494766003';
```

Count stored embeddings, the same count `count_products_with_embeddings` issues:

```sql
SELECT COUNT(*) FROM products WHERE embedding IS NOT NULL;
```

Find ids that have no embedding:

```sql
SELECT product_id
FROM products
WHERE embedding IS NULL;
```

The last query can return a large result on a full catalog. It is still a read.

## 11. Interview questions and answers

**What is a transaction?** It is a group of database statements that commit together or are undone together. In the catalog loader, every upsert statement in one Parquet chunk shares the transaction that ends at `session.commit()`.

**What is an upsert?** It inserts a row, and if the key already exists it updates that row instead. ProductIQ does this with `on_conflict_do_update` on `product_id`.

**What is the difference between `commit()` and `rollback()`?** `commit()` makes the current transaction durable. `rollback()` discards that transaction. The loader commits after each Parquet chunk and rolls back in the `except` block when a later chunk fails.

**What is the difference between `UPDATE` and an upsert?** `UPDATE` changes rows that already match. The embedding loader is an `UPDATE` by `product_id`, and it raises when no row matches. An upsert can insert a new `product_id`. The catalog loader is the upsert.

**What is a SQLAlchemy session?** It is the object that holds ORM queries and their transaction. `create_session_factory` builds sessions with `autocommit=False`. The product provider creates one session per lookup and closes it.

**What is a repository or a provider?** `ProductRepository` is the read API that returns `Product` rows and counts. `PostgresProductCatalogReadProvider` is the HTTP read path. It returns `ProductCatalogReadModel` and is the object `get_product` uses. They are not two names for the same call.

**Why batch a large catalog load?** `iter_batches` keeps one Parquet chunk in memory at a time. The default chunk is `10000` rows. Each chunk is split again so one statement stays under `65535` parameters. The default embedding update batch is `5000` rows, and that batch is one transaction.

**What if chunk 3 fails after chunks 1 and 2 committed?** Chunks 1 and 2 stay written. `rollback()` undoes only the open work in chunk 3. The function raises `CatalogLoadError`. A later upsert can fill the missing ids. It can also overwrite columns, including `embedding`, for ids that already exist.

**Why can an API read products without offering product CRUD?** `GET /api/v1/products/{product_id}` only selects. The handlers do not call the loader or the embedding update. Create and update exist as operator functions, not as routes.

**How is an embedding stored and updated?** The column is `embedding vector(384)`. The loader sets it with `UPDATE products SET embedding = CAST(:embedding AS vector) WHERE product_id = :product_id`. Search reads it with cosine distance and ignores nulls.

**What does `engine.begin()` change compared with `session.commit()`?** Both end a transaction. The embedding loader uses `engine.begin()` around one Parquet batch of updates. The catalog loader uses one session and `commit()` after each metadata chunk. A failed embedding batch rolls back that batch only.

**Does validation failure undo a successful load?** `validate_product_catalog` runs after `load_from_parquet` returns. The loader has already committed its chunks. The validator's `CatalogValidationError` does not call `rollback()` on those commits.

**What index does vector search use?** `create_product_embedding_hnsw_index` creates `ix_products_embedding_hnsw_cosine` with `vector_cosine_ops`, `m` of `16`, and `ef_construction` of `64`, unless that index already exists. The query sets `hnsw.ef_search` and orders by `embedding <=> :query_vector`.

**What is closed at shutdown?** `build_lifespan` calls `runtime.engine.dispose()` when a production runtime exists. That releases the engine's connections. It does not delete rows.

**Which read loads every product?** `PostgresRecommendationCatalog.list_catalog_products` runs `select(Product)` with no filter. The attribute recommendation generator calls it. Separately, fixture startup builds BM25 by selecting every row once. Full-catalog serving loads BM25 from the artifact file instead.

## 12. Exercises

Do not change code, and do not run a statement that writes or deletes.

**1. Name the product-detail query.** Open `PostgresProductCatalogReadProvider.get_product` and write the `select` it runs. Then list the `Product` columns it does not pass to `ProductCatalogReadModel`. Hint: the constructor has eight fields. Outcome: you can show that the HTTP read is not `ProductRepository.get_by_id`.

**2. Mark the catalog transaction boundary.** In `load_from_parquet`, find `session.commit()`, `session.rollback()`, and `session.close()`. State which Parquet rows a failure in chunk 3 keeps. Hint: commit is inside the batch loop, and rollback is in the `except` that wraps the whole loop. Outcome: you can explain why the file is not one atomic transaction.

**3. Compare two writes.** Read `_upsert_records` and `_UPDATE_EMBEDDING_SQL`. Say which one can insert a new `product_id`, and which one raises when the id is missing. Hint: the embedding function checks `rowcount`. Outcome: you can tell an upsert from an update.

**4. Separate API startup from a load.** Find `load_runtime_catalog` and the call to `inspect_catalog_runtime_status` in `build_production_application_services`. State which function upserts Parquet and which function only counts. Hint: an empty catalog raises `ConfigurationError` and tells you to run the module. Outcome: you can explain why restarting the API does not reload the catalog.

**5. Find a full-table read.** Open `PostgresRecommendationCatalog.list_catalog_products` and `AttributeRecommendationCandidateGenerator.generate`. State the `select` and the method that calls it. Hint: the `select` has no `where`. Outcome: you can point at a recommendation read that is larger than a lookup by id.

## 13. Source-reading order

1. `src/productiq/database/models/product.py` — the row, the primary key, and the B-tree indexes.
2. `src/productiq/database/catalog_contract.py` — table name and the fact that `embedding` is outside the 22 processed columns.
3. `src/data/catalog/schema.py` and `src/data/attributes/schema.py` — the 22 column names.
4. `src/productiq/database/engine.py` — `create_engine_from_settings`.
5. `src/productiq/database/session.py` — `create_session_factory` and `session_scope`.
6. `src/productiq/database/repository.py` — the read API the HTTP product route does not use.
7. `src/productiq/serving/postgres_catalog_provider.py` — the product-detail query.
8. `src/productiq/database/loaders/catalog_loader.py` — `load_from_parquet` and `_upsert_records`.
9. `src/productiq/database/catalog_pipeline.py` — table creation, load, then validation.
10. `src/productiq/retrieval/vector_index_loader.py` — `_UPDATE_EMBEDDING_SQL` and `engine.begin()`.
11. `src/productiq/database/vector_catalog.py` — the embedding column, HNSW index, and counts.
12. `src/productiq/retrieval/pgvector_search.py` — `search_products_by_embedding`.
13. `src/productiq/database/load_runtime_catalog.py` — the operator entry point and startup counts.
14. `src/productiq/api/services/production_stack.py` — request sessions, and the proof that startup counts instead of loading.
15. `src/productiq/retrieval/catalog_candidate_filter.py` and `src/productiq/ranking/product_context_provider.py` — search reads by id.
16. `src/productiq/recommendation/seed_product.py`, `seed_embedding.py`, `catalog_embeddings.py`, and `generators/attribute.py` — recommendation reads, including the full-table select.
17. `src/productiq/api/lifespan.py` — `engine.dispose()` on shutdown.

## 14. Accuracy and open questions

Verified by reading the functions named above. Nothing was executed.

- `SET hnsw.ef_search` runs on the connection inside `engine.connect()`. This review did not check whether that setting is still present after the connection returns to the pool.
- `_upsert_records` stores `result.rowcount`. This review did not execute an upsert, so it does not claim what PostgreSQL returns in `rowcount` for every conflict case. The insert and update totals in `CatalogLoadReport` are derived from counts after a successful load.
- The conclusion that a catalog rerun assigns null to `embedding` follows from the conflict `set_` list, the Parquet columns, and PostgreSQL's rule for columns omitted from `INSERT`. It was not re-run.
- `AttributeRecommendationCandidateGenerator` is in the production generator tuple, and `generate_recommendation_candidates` calls `generate` on each generator. A generator exception can be recorded and skipped when `continue_on_generator_failure` is true. This review did not trace the default of that flag.
- `session.close()` on the read paths is explicit. Those paths do not call `rollback()` themselves. This note does not add a database observation of an interrupted read.
- No test file was executed. `tests/database/test_product_repository.py` and `tests/database/test_catalog_integration.py` construct `ProductRepository`. Their assertions were not re-read for this note.
