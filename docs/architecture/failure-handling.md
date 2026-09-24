# ProductIQ — Failure Cases & Failure Handling

**Version:** 1.0  
**Phase:** Phase 0 — System Specification  
**Status:** Frozen for MVP architecture

---

## 1. Purpose

ProductIQ is a multi-stage search and recommendation system. Failures can occur at any stage:

```text
User Query
    ↓
Query Understanding
    ↓
Retrieval
    ↓
Filtering
    ↓
Feature Generation
    ↓
Ranking
    ↓
Response
```

The purpose of this document is to define:

- expected failure modes
- failure severity
- system behavior during failures
- safe fallback strategies
- conditions under which the system must fail rather than return potentially incorrect results
- observability requirements
- recovery principles

The central reliability principle is:

> **ProductIQ must prefer an incomplete or degraded result over an invented or factually incorrect product result.**

---

# 2. Failure Handling Principles

## 2.1 Never fabricate catalog products

Every returned product must exist in the canonical product catalog.

The system must never generate:

```text
Product name
Price
Brand
Availability
Rating
Product URL
```

unless those values originate from the catalog.

---

## 2.2 Fail closed for hard constraints

Hard constraints represent requirements that must not be violated.

Examples:

```text
Nike
under ₹5,000
running shoes
available
```

If the user explicitly specifies:

```text
Nike shoes under ₹5,000
```

the system must not return:

```text
Adidas shoes
₹6,000 Nike shoes
```

simply because they have high semantic similarity.

If filtering cannot be reliably performed, the system should not silently bypass the constraint.

---

## 2.3 Fail open for acceleration components

Some components improve performance but are not the source of truth.

Examples:

- Redis
- FAISS experimentation
- ranking model
- cache

If Redis fails, ProductIQ should normally bypass Redis and continue.

If the ranking model fails, ProductIQ may fall back to a deterministic ranking strategy.

---

## 2.4 Degrade gracefully

A component failure should not automatically bring down the entire search system if a safe fallback exists.

Example:

```text
BM25 unavailable
       ↓
Vector retrieval
       ↓
Hard filters
       ↓
Fallback ranking
       ↓
Results
```

However:

```text
PostgreSQL unavailable
       ↓
Cannot verify canonical products
       ↓
Do not return unverified products
```

---

# 3. Failure Severity

ProductIQ uses four conceptual severity levels.

## P0 — Critical

The system cannot safely return product results.

Examples:

- canonical database unavailable
- corrupted product catalog
- product identity cannot be verified
- severe data/index mismatch

Expected behavior:

```text
Fail request safely
↓
Return controlled error
↓
Log incident
↓
Alert operations
```

---

## P1 — Major

Core functionality is degraded but a safe fallback may exist.

Examples:

- vector retrieval unavailable
- BM25 unavailable
- ranking model unavailable
- embedding service unavailable

Expected behavior:

```text
Use safe fallback
↓
Record degradation
↓
Continue serving if result quality remains acceptable
```

---

## P2 — Moderate

A specific request or subsystem is affected.

Examples:

- malformed query
- invalid filter
- recommendation unavailable
- cache serialization failure

Expected behavior:

```text
Handle locally
↓
Return appropriate response
↓
Log diagnostic information
```

---

## P3 — Minor

Non-critical functionality is affected.

Examples:

- product image unavailable
- optional metadata missing
- analytics event failed

Expected behavior:

```text
Continue primary operation
↓
Record failure
```

---

# 4. Query-Level Failures

## 4.1 Empty query

Example:

```text
""
```

Behavior:

```text
Reject request
```

Do not perform an unrestricted expensive search unless explicitly supported by the product.

Response:

```text
InvalidQuery
```

---

## 4.2 Query contains only whitespace

Example:

```text
"      "
```

Normalize first.

If empty after normalization:

```text
InvalidQuery
```

---

## 4.3 Extremely long query

Very large input can cause:

- unnecessary embedding cost
- excessive latency
- resource exhaustion

Behavior:

```text
Validate length
↓
Reject if above configured maximum
```

The limit should be configurable rather than hard-coded into the architecture specification.

---

## 4.4 Unsupported characters

Most natural-language characters should be accepted.

The system should not reject legitimate queries merely because they contain:

- punctuation
- currency symbols
- Unicode
- accented characters

However, dangerous input must still be handled safely.

Database queries must always use parameterized queries.

---

## 4.5 Misspelled product or brand

Example:

```text
"nik running shoes"
```

Possible behavior:

- lexical retrieval may partially match
- semantic retrieval may recover intent
- normalization may correct known entities
- query understanding may identify likely brand/category

The system should avoid confidently inventing a correction.

---

## 4.6 Ambiguous query

Example:

```text
"black shoes"
```

This is valid but underspecified.

ProductIQ should still perform search using the available information.

It should not invent:

```text
running shoes
men's shoes
Nike
under ₹5,000
```

unless those attributes are actually present in the query or supported by an explicitly defined personalization mechanism.

---

## 4.7 Contradictory constraints

Example:

```text
Nike Adidas shoes
```

or:

```text
under ₹5,000 above ₹10,000
```

The query-understanding layer should detect contradictions where possible.

Behavior:

```text
Detect contradiction
↓
Do not silently choose one interpretation
↓
Return clarification/error response
```

---

# 5. Query Understanding Failures

## 5.1 Incorrect brand extraction

User:

```text
"running shoes similar to Nike Pegasus"
```

Potential mistake:

```text
brand = Nike
```

when Nike may be part of a reference product rather than a strict brand filter.

The query understanding system must distinguish:

- entity mention
- hard constraint
- semantic reference

---

## 5.2 Incorrect price extraction

Example:

```text
"shoes below 5000"
```

Expected:

```text
price < 5000
```

Potential failures:

- interpreting 5000 as ₹50,000
- incorrect currency
- incorrect operator
- treating price as semantic text instead of structured constraint

Price constraints must be represented structurally.

---

## 5.3 Unknown entities

Example:

```text
"dark moonstone running shoes"
```

If `moonstone` is not recognized:

Do not invent an entity.

It may remain part of the semantic query.

---

## 5.4 Query parser failure

If structured parsing fails:

```text
Raw query
    ↓
Semantic retrieval fallback
```

However, the system must not fabricate structured filters.

Example:

If the parser cannot determine whether:

```text
under 5000
```

is a price constraint, it must not randomly create one.

---

# 6. Product Data Failures

Product data is foundational because every downstream component depends on it.

## 6.1 Missing required fields

Required fields include:

```text
product_id
title
brand
category
price
availability
```

If a required field is missing:

```text
Do not index product normally
```

The product should enter a data-quality quarantine or rejected-data pipeline.

---

## 6.2 Invalid price

Examples:

```text
price = -500
price = "unknown"
price = null
```

Behavior:

```text
Reject from price-sensitive search
```

Do not silently convert invalid prices to zero.

---

## 6.3 Duplicate products

Duplicates can originate from:

- repeated ingestion
- multiple catalog records
- data-source duplication

Deduplication should occur before indexing.

Otherwise:

```text
Top 10 results
↓
same product repeated 4 times
```

can occur.

---

## 6.4 Stale product data

Possible stale fields:

- price
- availability
- product URL
- metadata

The system should track dataset/index versions.

Where freshness matters, the response should be based on the latest valid catalog version.

---

## 6.5 Malformed product text

Examples:

```text
title = "Nike ### ###"
description = corrupted
```

The product may still be stored, but indexing should follow data-quality rules.

---

## 6.6 Missing optional fields

Examples:

```text
rating = null
image_url = null
description = null
```

These should not cause the entire product to fail.

Optional fields must have defined null behavior.

Example:

```text
missing rating
↓
ranking feature = unavailable
↓
ranking fallback
```

---

# 7. Embedding Failures

## 7.1 Embedding model unavailable

Possible causes:

- model download failure
- service failure
- dependency failure
- hardware failure

Offline pipeline:

```text
Fail embedding generation
↓
Do not create invalid index entries
↓
Record failed products
```

Online query:

```text
Embedding unavailable
↓
Use BM25-only retrieval if available
```

---

## 7.2 Embedding dimension mismatch

Example:

```text
Stored vectors: 384 dimensions
Query vector: 768 dimensions
```

This is a hard compatibility error.

Do not attempt to search.

The system should raise:

```text
EmbeddingError
```

and use a safe fallback only if one exists.

---

## 7.3 Invalid embedding

Reject embeddings containing:

```text
NaN
Inf
wrong dimension
empty vector
```

Invalid vectors must never enter the vector index.

---

## 7.4 Model version mismatch

Example:

```text
Product embeddings:
model = model-A

Query embedding:
model = model-B
```

Unless compatibility has been explicitly validated, these should not be compared.

Track:

```text
model_id
model_version
dimension
```

with embeddings.

---

# 8. BM25 Failures

## 8.1 BM25 index unavailable

If vector retrieval works:

```text
BM25 unavailable
↓
Vector retrieval
↓
Hard filters
↓
Ranking
```

The system should record that lexical retrieval was unavailable.

---

## 8.2 Empty BM25 index

Possible cause:

- indexing failure
- empty catalog
- corrupted deployment

Behavior:

```text
Return no lexical candidates
```

Do not interpret this as evidence that no products exist.

---

## 8.3 Stale BM25 index

The system must track the dataset/index version.

Example:

```text
Database version = v15
BM25 index = v12
```

This mismatch should be detected.

---

# 9. Vector Retrieval Failures

## 9.1 pgvector unavailable

If BM25 is available:

```text
Vector retrieval unavailable
↓
BM25-only retrieval
```

The response may be degraded but remains grounded.

---

## 9.2 Vector index unavailable

Possible causes:

- index not created
- deployment error
- corruption
- incompatible schema

Behavior:

```text
Do not perform unsafe vector search
↓
Fallback to lexical retrieval
```

---

## 9.3 Vector search timeout

Use a bounded timeout.

If timeout occurs:

```text
Cancel/stop retrieval
↓
Use safe fallback if available
```

Never allow one retrieval subsystem to consume unlimited request time.

---

## 9.4 Zero vector results

Zero vector results do not necessarily mean:

```text
No products exist
```

It may indicate:

- poor query embedding
- threshold too strict
- wrong model
- incomplete catalog
- index problem

The system should distinguish:

```text
No candidates found
```

from:

```text
Retrieval system failed
```

---

# 10. Hybrid Retrieval Failures

## 10.1 Duplicate candidates

BM25 and vector retrieval may return the same product.

Candidate generation must deduplicate by:

```text
product_id
```

Example:

```text
BM25:
P1 P2 P3

Vector:
P2 P3 P4

Union:
P1 P2 P3 P4
```

---

## 10.2 Score scale mismatch

BM25 and vector similarity scores may exist on different scales.

Do not directly assume:

```text
BM25 score + vector score
```

is meaningful.

Hybrid fusion must explicitly define normalization or fusion methodology.

---

## 10.3 One retriever fails

ProductIQ should support degraded hybrid retrieval.

```text
BM25 + Vector
       ↓
Vector unavailable
       ↓
BM25
```

or:

```text
BM25 + Vector
       ↓
BM25 unavailable
       ↓
Vector
```

The degraded mode should be observable.

---

## 10.4 Candidate explosion

A poorly configured retrieval system may return too many candidates.

This can cause:

- high memory usage
- ranking latency
- database load

Candidate count must be bounded.

---

# 11. Hard Filtering Failures

Filtering is a correctness boundary.

## 11.1 Incorrect filter application

Example:

User:

```text
Nike shoes under ₹5,000
```

Returned:

```text
Nike shoes ₹5,999
```

This is a correctness failure.

The filter layer must be tested independently.

---

## 11.2 Filter bypass

A ranking component must never be able to override hard filters.

Correct:

```text
Retrieve
↓
Hard filter
↓
Rank
```

Not:

```text
Retrieve
↓
Rank
↓
Filter
```

for the core MVP path.

---

## 11.3 Overly restrictive filter

Example:

```text
Nike running shoes under ₹5,000
```

returns zero products.

The system may broaden semantic retrieval, but it must not violate explicit constraints.

Safe:

```text
Expand semantic search
while preserving:
Nike
running shoes
under ₹5,000
```

Unsafe:

```text
Remove price constraint
```

without user authorization.

---

# 12. Ranking Failures

## 12.1 Ranking model unavailable

Fallback:

```text
Candidate set
↓
Deterministic ranking
```

Possible deterministic signals:

1. semantic score
2. lexical score
3. exact attribute matches
4. popularity/rating where available

The exact fallback should be versioned and tested.

---

## 12.2 Missing ranking features

Example:

```text
rating = null
```

The ranking system should have explicit handling for missing values.

Do not replace missing information with an arbitrary misleading value.

---

## 12.3 Invalid ranking score

Reject:

```text
NaN
Inf
null
```

scores.

---

## 12.4 Ranking timeout

If ranking exceeds the request budget:

```text
Stop expensive ranking
↓
Use deterministic fallback
```

---

# 13. PostgreSQL Failures

PostgreSQL is the source of truth.

## 13.1 Database unavailable

If canonical product verification cannot occur:

```text
Do not return unverified products
```

Return a controlled service error.

---

## 13.2 Connection pool exhaustion

Possible causes:

- too many concurrent requests
- leaked connections
- slow queries

Required protections:

- connection pool limits
- query timeouts
- proper connection release

---

## 13.3 Slow database query

Queries should have bounded execution time.

Slow queries must be observable through:

```text
query timing
query type
request ID
```

---

## 13.4 Transaction failure

Offline ingestion must avoid leaving partially committed inconsistent state.

Where required:

```text
transaction
↓
commit
```

or:

```text
rollback
```

---

# 14. Redis Failures

Redis is an acceleration layer, not the source of truth.

## 14.1 Redis unavailable

Behavior:

```text
Cache unavailable
↓
Bypass cache
↓
Query underlying systems
```

The search service should remain functionally correct.

---

## 14.2 Cache miss

A cache miss is not a failure.

```text
Cache miss
↓
Perform normal search
↓
Optionally populate cache
```

---

## 14.3 Stale cache

Cache entries require controlled expiration/invalidation.

A stale cache must never override critical product truth when freshness is required.

---

## 14.4 Incorrect cache key

Example:

```text
"nike shoes under 5000"
```

and:

```text
"nike shoes under 10000"
```

must never resolve to the same cached result.

Cache keys should include all relevant request dimensions.

---

## 14.5 Cache stampede

Many identical requests arriving simultaneously may all miss the cache.

Possible future mitigation:

- request coalescing
- locks
- short-lived protection
- controlled refresh

This is not required for the initial MVP unless load testing demonstrates the need.

---

# 15. API Failures

## 15.1 Malformed request

Return:

```text
4xx
```

with a structured error response.

---

## 15.2 Internal dependency failure

Do not expose internal stack traces to users.

Instead:

```text
controlled API error
+
request ID
```

Detailed diagnostics remain in logs.

---

## 15.3 Request timeout

Every major dependency should have bounded timeouts.

The API should not wait indefinitely for:

- embeddings
- database
- retrieval
- ranking
- cache

---

## 15.4 Rate limiting

Protect the API against excessive requests.

Rate limiting is especially important for:

- embedding generation
- expensive search requests
- recommendation requests

---

# 16. Frontend Failures

The frontend must handle:

```text
API unavailable
API timeout
empty result
partial metadata
missing image
invalid response
```

Example:

```text
Search failed
↓
Display controlled error
↓
Allow retry
```

The frontend must not invent product information when fields are missing.

---

# 17. Offline Pipeline Failures

## 17.1 Ingestion failure

If ingestion fails:

```text
Do not publish partial dataset as complete dataset
```

Track:

```text
dataset_version
ingestion_status
record_count
failure_count
timestamp
```

---

## 17.2 Partial processing

Example:

```text
100,000 products
80,000 embedded
20,000 failed
```

The pipeline must explicitly record the partial state.

It should not silently claim:

```text
100% indexed
```

---

## 17.3 Index/data mismatch

Example:

```text
PostgreSQL catalog = v10
Vector index = v8
BM25 index = v9
```

This should be detected before production serving.

---

## 17.4 Failed deployment

A new model/index should not replace a working version until validation succeeds.

Conceptually:

```text
Build
↓
Validate
↓
Publish
↓
Activate
```

rather than:

```text
Build
↓
Immediately replace production
```

---

# 18. Evaluation Failures

Evaluation itself can produce misleading conclusions.

## 18.1 Incorrect relevance labels

Poor labels produce unreliable metrics.

Evaluation datasets should be versioned.

---

## 18.2 Data leakage

Training/development information must not unintentionally contaminate the test set.

---

## 18.3 Metric implementation error

Metrics such as:

```text
Recall@K
MRR
NDCG@K
Precision@K
```

must have tested implementations.

---

## 18.4 Dataset drift

A model may perform well on an old evaluation dataset but poorly on newer query patterns.

Therefore evaluation datasets should evolve while preserving historical benchmark sets.

---

# 19. Security & Robustness Failures

## 19.1 SQL injection

User query must never be concatenated directly into SQL.

Use parameterized queries.

---

## 19.2 Input abuse

Protect against:

- excessively large queries
- repeated expensive requests
- malformed payloads
- excessive concurrent requests

---

## 19.3 Untrusted metadata

Product descriptions and metadata must be treated as data, not executable instructions.

ProductIQ's search pipeline should not execute arbitrary content from product descriptions.

---

# 20. Safe Fallback Matrix

| Failure | Safe fallback |
|---|---|
| Query parser fails | Semantic/lexical search using raw query |
| BM25 unavailable | Vector retrieval |
| Vector retrieval unavailable | BM25 retrieval |
| Both retrieval systems unavailable | Controlled failure |
| Redis unavailable | Bypass cache |
| Ranking model unavailable | Deterministic ranking |
| Optional field missing | Continue with missing-feature handling |
| Image unavailable | Return product without image |
| Embedding unavailable for query | BM25-only |
| PostgreSQL unavailable | Controlled failure |
| Hard-filter validation fails | Do not return potentially invalid results |
| No results | Return empty result set / controlled broadening where safe |
| Frontend API failure | Retry/error UI |
| Recommendation unavailable | Keep search functionality available |

---

# 21. No-Results Handling

A no-result response must distinguish between:

### Case A — genuinely no matching products

```text
Query
↓
Valid retrieval
↓
Valid filtering
↓
0 products
```

This is a legitimate empty result.

### Case B — infrastructure failure

```text
Vector database unavailable
↓
0 results
```

This must **not** be represented to the user as:

> "No products found."

Instead, it should be treated as a service failure or degraded mode.

### Case C — overly restrictive query

If explicit constraints eliminate every candidate:

```text
No matching products satisfy the requested constraints.
```

The system may optionally suggest relaxing constraints in a future UX layer.

It must not automatically violate explicit constraints.

---

# 22. Observability Requirements

Every search request should have a traceable identifier.

At minimum, capture:

```text
request_id
query_id
timestamp
query latency
query-understanding latency
embedding latency
BM25 latency
vector latency
filter latency
ranking latency
database latency
cache status
retrieval mode
ranking mode
dataset version
embedding model version
index version
error type
```

---

# 23. Error Taxonomy

Errors should be classified by subsystem.

```text
QUERY_ERROR
UNDERSTANDING_ERROR
DATA_ERROR
EMBEDDING_ERROR
LEXICAL_RETRIEVAL_ERROR
VECTOR_RETRIEVAL_ERROR
FILTER_ERROR
RANKING_ERROR
DATABASE_ERROR
CACHE_ERROR
API_ERROR
FRONTEND_ERROR
EVALUATION_ERROR
```

This makes production debugging much easier than a generic:

```text
Internal Server Error
```

---

# 24. Retry Policy

Retries should only be used for potentially transient failures.

Potential retry candidates:

- temporary database connection failure
- transient model-service failure
- temporary network failure

Do not blindly retry:

- malformed queries
- invalid filters
- dimension mismatch
- corrupted data
- deterministic validation errors

Retries must be:

```text
bounded
time-limited
observable
```

---

# 25. Failure Boundary Architecture

ProductIQ should conceptually separate:

```text
                ┌──────────────────┐
                │   User Request   │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Query Validation │
                └────────┬─────────┘
                         ↓
                ┌──────────────────┐
                │ Query Understanding│
                └────────┬─────────┘
                         ↓
              ┌──────────┴──────────┐
              ↓                     ↓
          BM25                  Vector Search
              │                     │
              └──────────┬──────────┘
                         ↓
                  Candidate Union
                         ↓
                  Hard Filtering
                         ↓
                    Ranking
                         ↓
                  Product DB
                         ↓
                    Response
```

Each boundary should have:

- timeout
- validation
- error classification
- fallback where safe
- observability

---

# 26. Core Reliability Rule

ProductIQ follows this hierarchy:

```text
Correctness
    ↓
Grounding
    ↓
Constraint compliance
    ↓
Availability
    ↓
Latency
    ↓
Optimization
```

This means the system should not sacrifice product correctness simply to achieve lower latency.

For example:

```text
Fast but incorrect product
```

is worse than:

```text
slightly slower but correctly grounded product
```

---

# 27. MVP Failure-Handling Scope

The MVP must explicitly handle:

- invalid queries
- missing required product data
- duplicate products
- embedding failures
- embedding dimension mismatch
- BM25 failure
- vector retrieval failure
- hard-filter failures
- ranking failure
- PostgreSQL failure
- Redis failure
- API timeout
- empty results
- index/data version mismatch
- partial offline processing

The following can remain future enhancements:

- sophisticated circuit breakers
- request coalescing
- advanced load shedding
- multi-region failover
- distributed tracing infrastructure
- automated rollback orchestration
- advanced anomaly detection

---

# 28. Definition of Safe Behavior

A ProductIQ response is considered **safe** when:

1. Every returned product exists in the catalog.
2. Explicit hard constraints are respected.
3. Product attributes come from trusted catalog data.
4. Retrieval failures are distinguishable from genuine no-result cases.
5. Degraded modes are observable.
6. Failed components do not silently produce fabricated results.
7. Expensive operations have bounded execution time.
8. Model and index versions are compatible.
9. Cache failures do not corrupt product truth.
10. Ranking cannot override correctness constraints.

---

# 29. Engineering Principle

The most important failure-handling distinction in ProductIQ is:

> **Some components affect performance; other components affect correctness.**

Performance components can often degrade gracefully:

```text
Redis
Ranking model
BM25
Vector retrieval
```

Correctness-critical components require stricter handling:

```text
Canonical product catalog
Hard filters
Product identity
Product attributes
Data/index compatibility
```

This distinction should guide every future implementation decision.

---

# 30. Final Failure-Handling Architecture

The intended behavior is:

```text
                   USER QUERY
                       │
                       ↓
                VALIDATE INPUT
                       │
              ┌────────┴────────┐
              │                 │
           Invalid            Valid
              │                 │
           Reject               ↓
                         QUERY UNDERSTANDING
                               │
                               ↓
                    ┌──────────┴──────────┐
                    ↓                     ↓
                  BM25              VECTOR SEARCH
                    │                     │
                    └──────────┬──────────┘
                               ↓
                         CANDIDATE UNION
                               │
                               ↓
                         HARD FILTERS
                               │
                       ┌───────┴───────┐
                       │               │
                    Failure          Valid
                       │               │
                   Fail safe           ↓
                                   RANKING
                                       │
                                ┌──────┴──────┐
                                │             │
                             Failure        Valid
                                │             │
                         Deterministic        ↓
                            fallback       TOP-K
                                              │
                                              ↓
                                     CANONICAL DB VERIFY
                                              │
                                       ┌──────┴──────┐
                                       │             │
                                    Failure        Valid
                                       │             │
                                  Fail safely        ↓
                                             API RESPONSE
```

**Final principle:**

> **ProductIQ should degrade in capability before it degrades in correctness.**