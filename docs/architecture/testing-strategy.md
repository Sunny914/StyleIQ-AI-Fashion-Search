# ProductIQ — Testing Strategy

**Version:** 1.0  
**Phase:** Phase 0 — System Specification  
**Status:** Frozen for MVP architecture

---

# 1. Purpose

ProductIQ is a multi-stage AI search system. Testing must therefore verify more than whether individual functions execute successfully.

The testing strategy must establish that:

1. individual components behave correctly
2. components integrate correctly
3. retrieved products are relevant
4. explicit constraints are respected
5. returned products are grounded in the catalog
6. failures degrade safely
7. model and index changes do not silently reduce search quality
8. the complete search pipeline produces reproducible results

The testing philosophy is:

> **Test correctness first, relevance second, performance third, and optimization continuously.**

---

# 2. Testing Pyramid

ProductIQ will use multiple levels of testing.

```text
                    ┌───────────────────────┐
                    │   System / E2E Tests  │
                    └───────────┬───────────┘
                                │
                       ┌────────┴────────┐
                       │ Evaluation Tests│
                       └────────┬────────┘
                                │
                    ┌───────────┴───────────┐
                    │  Integration Tests    │
                    └───────────┬───────────┘
                                │
                 ┌──────────────┴──────────────┐
                 │       Unit Tests             │
                 └─────────────────────────────┘
```

The majority of deterministic logic should be covered by unit tests.

Search quality requires a separate evaluation framework.

---

# 3. Testing Categories

ProductIQ will use:

- Unit testing
- Integration testing
- Retrieval testing
- Ranking testing
- Contract testing
- Data-quality testing
- End-to-end testing
- Failure testing
- Regression testing
- Performance testing
- Evaluation testing
- Security/robustness testing

---

# 4. Unit Testing

Unit tests verify individual functions or classes in isolation.

Examples:

```text
normalize_query()
parse_price_filter()
extract_brand()
normalize_product()
deduplicate_products()
build_product_text()
calculate_features()
apply_filters()
normalize_scores()
rank_candidates()
build_response()
```

A unit test should generally test one behavior rather than an entire search pipeline.

---

# 5. Query Understanding Tests

Query understanding is one of the most important test areas.

Example:

```text
"black Nike running shoes under ₹5000"
```

Expected structured representation:

```text
brand = Nike
category = running shoes
color = black
max_price = 5000
```

The test should verify:

- extracted entities
- operators
- values
- normalized representation
- semantic query
- hard vs soft constraint classification

---

# 6. Query Test Categories

The test suite should include:

### Exact queries

```text
Nike Air Max 270
```

### Brand queries

```text
Nike running shoes
```

### Category queries

```text
men's running shoes
```

### Attribute queries

```text
black waterproof running shoes
```

### Price queries

```text
shoes under ₹5000
```

### Multi-constraint queries

```text
black Nike running shoes under ₹5000
```

### Semantic queries

```text
shoes for jogging
```

### Paraphrased queries

```text
footwear suitable for daily running
```

### Ambiguous queries

```text
black shoes
```

### Difficult queries

```text
lightweight black Nike shoes for long-distance running below five thousand
```

---

# 7. Query Edge Cases

Tests should include:

```text
""
"   "
very long query
uppercase query
mixed case
Unicode
₹5000
Rs 5000
INR 5000
5k
decimal prices
multiple price constraints
unknown brand
misspelled brand
contradictory filters
```

The goal is to verify that the parser does not silently invent constraints.

---

# 8. Product Data Tests

Every product ingestion pipeline must validate the canonical product schema.

Required fields:

```text
product_id
title
brand
category
price
availability
```

Tests should verify:

- missing fields
- null values
- invalid types
- negative price
- malformed identifiers
- duplicate IDs
- duplicate products
- invalid categories
- invalid availability values
- malformed URLs
- malformed metadata

---

# 9. Data Quality Tests

Data-quality testing should occur before products reach search indexes.

Example rules:

```text
product_id must be unique
price >= 0
title must not be empty
brand must be normalized
category must be valid
availability must use allowed values
```

A product violating a critical rule should not silently enter production indexes.

---

# 10. Product Text Generation Tests

Product text is used for:

- embeddings
- BM25
- semantic retrieval
- lexical retrieval

Example:

```text
Nike Air Zoom Pegasus 41
Nike
Running Shoes
Black
Men
₹4,999
```

Tests should verify:

- required fields appear
- null fields do not produce malformed text
- duplicate text is avoided where unnecessary
- normalization is deterministic

Given the same canonical product, product-text generation should produce the same output.

---

# 11. Embedding Tests

Embedding tests must verify:

### Dimension

```text
len(vector) == configured_dimension
```

### Validity

```text
no NaN
no Inf
non-empty
```

### Compatibility

Query and product embeddings must originate from compatible models/configurations.

---

# 12. Embedding Regression Tests

When changing the embedding model:

```text
Model A
    ↓
evaluation dataset
    ↓
baseline metrics

Model B
    ↓
same evaluation dataset
    ↓
new metrics
```

The model should not be adopted solely because it is newer.

It must demonstrate acceptable retrieval quality.

---

# 13. BM25 Tests

BM25 tests should verify:

- exact product-name retrieval
- brand retrieval
- rare-term retrieval
- tokenization
- normalization
- zero-result behavior
- index loading
- index version compatibility

Example:

```text
Query:
"Nike Pegasus 41"
```

The exact product should appear among lexical candidates when it exists in the catalog.

---

# 14. Vector Retrieval Tests

Vector retrieval tests should verify:

- semantic similarity
- top-K behavior
- vector dimensions
- similarity calculation
- filtering compatibility
- zero-result behavior
- index availability
- index version

Example:

```text
Query:
"shoes for jogging"
```

should retrieve products semantically related to running footwear even when the exact word "jogging" is absent.

---

# 15. Hybrid Retrieval Tests

Hybrid retrieval is a core ProductIQ capability.

Test cases should verify:

```text
BM25 only
Vector only
BM25 + Vector
```

Candidate union must:

- preserve unique product IDs
- retain retrieval-source information
- retain component scores
- avoid accidental duplication

Example:

```text
BM25:
P1 P2 P3

Vector:
P2 P3 P4

Expected candidates:
P1 P2 P3 P4
```

---

# 16. Hard Filter Tests

Hard filtering requires particularly strong coverage.

Example:

```text
Query:
Nike shoes under ₹5000
```

Test:

```text
Product A
Nike
₹4,500
→ PASS

Product B
Nike
₹5,500
→ FAIL

Product C
Adidas
₹4,000
→ FAIL
```

Filtering must be deterministic.

---

# 17. Filter Ordering Test

The architecture requires:

```text
Retrieval
    ↓
Hard Filtering
    ↓
Ranking
```

Tests must verify that a ranking score cannot cause an invalid product to survive filtering.

Example:

```text
Invalid product:
semantic_score = 0.99
price = ₹7,000

Valid product:
semantic_score = 0.75
price = ₹4,500
```

The invalid product must still be removed.

---

# 18. Ranking Tests

Ranking tests should verify:

- feature calculation
- score calculation
- deterministic ordering
- missing-feature handling
- tie handling
- invalid-score handling
- fallback ranking

Example:

```text
Candidate A
semantic = 0.90
lexical = 0.70

Candidate B
semantic = 0.80
lexical = 0.90
```

The expected ordering depends on the defined ranking strategy and must be tested against that specification.

---

# 19. Ranking Regression Tests

When ranking logic changes:

```text
Previous ranking
        ↓
evaluation dataset
        ↓
metrics

New ranking
        ↓
same dataset
        ↓
metrics
```

Compare:

- NDCG@K
- MRR
- Precision@K
- Recall@K

Also inspect query-type-specific performance.

---

# 20. API Contract Tests

The API contract must be tested independently.

Example response:

```json
{
  "query": "...",
  "results": [
    {
      "product_id": "...",
      "rank": 1,
      "score": 0.91
    }
  ]
}
```

Tests should verify:

- required fields exist
- types are correct
- rank ordering is valid
- product IDs are valid
- errors use defined schemas
- unexpected fields do not break clients

---

# 21. Interface Contract Tests

Each major interface must have a stable contract.

Examples:

```text
QueryUnderstanding
Retrieval
Filtering
Ranking
ProductRepository
Cache
EmbeddingService
```

If one component changes its output structure, integration tests should detect the incompatibility.

---

# 22. Database Integration Tests

Tests should run against a controlled test database.

Verify:

- product insertion
- product retrieval
- filtering
- product existence
- transaction behavior
- duplicate constraints
- query correctness

Production data should never be modified by automated tests.

---

# 23. pgvector Integration Tests

Verify:

- vector insertion
- vector retrieval
- dimension enforcement
- similarity ordering
- filtering combined with vector search
- index compatibility

Test vectors should be deterministic where possible.

---

# 24. Redis Integration Tests

Verify:

- cache set
- cache get
- cache miss
- TTL
- serialization/deserialization
- cache invalidation
- incorrect/malformed cache data

Redis should be treated as optional from a correctness perspective.

---

# 25. End-to-End Search Tests

An E2E test exercises:

```text
User Query
↓
API
↓
Query Understanding
↓
Retrieval
↓
Filtering
↓
Ranking
↓
Database verification
↓
Response
```

Example:

```text
"black Nike running shoes under ₹5000"
```

Expected properties:

- response succeeds
- results exist if matching products exist
- every result is a catalog product
- every result satisfies hard constraints
- results contain required fields
- ranking order is valid

---

# 26. Recommendation Tests

Recommendation must be tested separately from search.

Example:

```text
Input:
Product P123

Expected:
similar products
```

Tests should verify:

- source product exists
- source product is not returned unless explicitly allowed
- recommended products exist
- similarity/relevance is valid
- duplicate recommendations are removed

---

# 27. Failure Injection Tests

The system should deliberately simulate failures.

Examples:

```text
database unavailable
Redis unavailable
BM25 unavailable
vector search unavailable
embedding unavailable
ranking unavailable
timeout
malformed response
invalid embedding
```

Expected behavior should match the Failure Handling specification.

---

# 28. Fallback Tests

Example:

```text
BM25 = unavailable
Vector = available
```

Expected:

```text
Vector retrieval
→ filtering
→ ranking
→ response
```

Another:

```text
Vector = unavailable
BM25 = available
```

Expected:

```text
BM25 retrieval
→ filtering
→ ranking
→ response
```

Another:

```text
Ranking = unavailable
```

Expected:

```text
Candidates
→ deterministic fallback ranking
→ response
```

---

# 29. Grounding Tests

Grounding is a core ProductIQ correctness requirement.

For every returned result:

```text
returned.product_id
        ↓
canonical catalog
        ↓
must exist
```

Additionally:

```text
returned.price == catalog.price
returned.brand == catalog.brand
returned.title == catalog.title
```

where those fields are included in the response.

The API must not return generated values that disagree with the canonical catalog.

---

# 30. Retrieval Evaluation

Retrieval should be evaluated independently from ranking.

Primary metrics:

```text
Recall@K
```

The central question:

> Did the retrieval stage bring the relevant product into the candidate set?

Example:

```text
Relevant products:
P1 P2 P3

Retrieved:
P1 P4 P5 P2

Recall@4 = 2/3
```

Ranking should not be blamed for a product that retrieval never produced.

---

# 31. Ranking Evaluation

Ranking asks:

> Given the candidates, did the system put the best products near the top?

Metrics:

```text
MRR
NDCG@K
Precision@K
```

Ranking evaluation should use the same candidate set when comparing ranking strategies where appropriate.

---

# 32. End-to-End Evaluation

End-to-end evaluation measures the actual user-facing system.

Example:

```text
Query
↓
Understanding
↓
Retrieval
↓
Filtering
↓
Ranking
↓
Top-K
```

Metrics should measure overall search quality.

The system should also separately record:

- query-understanding failures
- retrieval failures
- filtering failures
- ranking failures
- infrastructure failures

This allows quality problems to be localized.

---

# 33. Evaluation Dataset

The evaluation dataset should contain:

```text
query_id
query
product_id
relevance
query_category
dataset_version
```

Relevance scale:

```text
0 = not relevant
1 = slightly relevant
2 = relevant
3 = highly relevant
```

---

# 34. Query Distribution

The evaluation dataset should intentionally contain different query types.

| Query Type | Example |
|---|---|
| Exact | Nike Pegasus 41 |
| Brand | Nike running shoes |
| Category | running shoes |
| Attribute | black waterproof shoes |
| Price | shoes under ₹5000 |
| Multi-constraint | black Nike running shoes under ₹5000 |
| Semantic | shoes for jogging |
| Paraphrased | footwear for daily running |
| Ambiguous | black shoes |
| Difficult | lightweight black Nike running shoes for long-distance running |

This prevents the system from appearing strong simply because it performs well on one easy query type.

---

# 35. Regression Test Set

A curated set of important queries should become a permanent regression suite.

Example:

```text
REG-001:
black Nike running shoes under ₹5000

REG-002:
shoes for jogging

REG-003:
Nike Pegasus 41

REG-004:
men's waterproof running shoes

REG-005:
black shoes
```

Every significant retrieval/ranking/model change should run this suite.

---

# 36. Performance Testing

Performance testing should measure:

```text
request latency
retrieval latency
embedding latency
database latency
ranking latency
cache latency
throughput
memory usage
CPU usage
```

Do not choose arbitrary performance targets before establishing a baseline.

The process should be:

```text
Implement
↓
Measure
↓
Identify bottleneck
↓
Optimize
↓
Measure again
```

---

# 37. Latency Breakdown

Every search should ideally provide internal timing information such as:

```text
Query Understanding:  X ms
Embedding:            X ms
BM25:                 X ms
Vector Search:        X ms
Filtering:            X ms
Ranking:              X ms
Database:             X ms
Serialization:        X ms
--------------------------------
Total:                X ms
```

This makes optimization evidence-driven.

---

# 38. Load Testing

Load testing should eventually simulate:

- multiple simultaneous users
- repeated queries
- unique queries
- cache-heavy traffic
- cache-miss traffic
- expensive semantic queries

Measure:

- throughput
- latency distribution
- error rate
- database utilization
- Redis utilization
- CPU/memory
- retrieval performance

---

# 39. Security Testing

Minimum security testing should cover:

### SQL injection

```text
' OR 1=1 --
```

### Excessive input

Very large query payloads.

### Malformed JSON

Invalid API payloads.

### Rate abuse

Repeated requests against expensive endpoints.

### Unauthorized access

Protected administrative/internal endpoints must not be publicly accessible.

---

# 40. Property-Based Testing

Some logic is suitable for property-based testing.

Examples:

### Filtering

For every returned product:

```text
product.price <= max_price
```

when `max_price` is specified.

### Ranking

For every ranked result list:

```text
rank_1 < rank_2 < rank_3 ...
```

### Product IDs

Within a result set:

```text
product_id must be unique
```

### Grounding

For every result:

```text
result.product_id ∈ catalog
```

These properties should hold regardless of the specific input example.

---

# 41. Determinism

Given identical:

```text
query
dataset version
model version
retrieval configuration
ranking configuration
```

the system should produce reproducible results wherever deterministic behavior is expected.

If stochastic models are used, randomness must be controlled where required for evaluation.

---

# 42. Test Data Management

Testing must use versioned datasets.

Example:

```text
data/
├── raw/
├── processed/
└── evaluation/
```

Evaluation datasets should not silently change between experiments.

Every experiment should record:

```text
dataset_version
model_version
embedding_model
retrieval_config
ranking_config
```

---

# 43. Test Environment

ProductIQ should maintain conceptual separation between:

```text
Development
Testing
Evaluation
Production
```

Tests should not depend on production infrastructure or production user data.

---

# 44. CI Testing

The future CI pipeline should approximately follow:

```text
Push / Pull Request
        ↓
Lint
        ↓
Type checks
        ↓
Unit tests
        ↓
Integration tests
        ↓
API contract tests
        ↓
Selected retrieval tests
        ↓
Build
```

Expensive evaluation and load tests may run separately rather than on every commit.

---

# 45. Model Change Testing

Changing any of the following should trigger evaluation:

```text
embedding model
embedding dimension
query understanding model
ranking model
ranking weights
retrieval parameters
BM25 configuration
vector index configuration
product representation
```

A model should not be promoted based solely on qualitative examples.

---

# 46. Retrieval Ablation Tests

Compare:

```text
BM25
Vector
Hybrid
Hybrid + Filters
Hybrid + Ranking
```

This answers:

> Which component is actually contributing to search quality?

The experiment should use the same evaluation dataset.

---

# 47. Ranking Ablation Tests

Remove ranking signals one at a time where practical.

Example:

```text
Full ranking
↓
remove semantic score
↓
remove lexical score
↓
remove brand match
↓
remove category match
```

Compare resulting metrics.

This helps determine whether ranking features provide measurable value.

---

# 48. Failure Acceptance Criteria

A failure-handling implementation is considered correct when:

1. invalid requests are rejected safely
2. invalid products do not enter production indexes
3. BM25 failure can degrade to vector retrieval
4. vector failure can degrade to BM25
5. ranking failure has a deterministic fallback
6. Redis failure does not break correctness
7. database failure does not produce fabricated products
8. hard filters cannot be bypassed by ranking
9. every result can be traced to the catalog
10. infrastructure failures are distinguishable from genuine no-results cases

---

# 49. Definition of a Passing Search Test

A search test passes when:

```text
Request valid
      ↓
Pipeline executes
      ↓
Relevant candidates retrieved
      ↓
Hard constraints respected
      ↓
Results grounded in catalog
      ↓
Ranking valid
      ↓
API contract valid
      ↓
Expected quality behavior observed
```

A successful HTTP `200` alone does **not** mean the search test passed.

---

# 50. Test Ownership by Component

| Component | Primary Tests |
|---|---|
| Query Understanding | Unit + Contract + Evaluation |
| Data Pipeline | Unit + Data Quality + Integration |
| Embeddings | Unit + Integration + Regression |
| BM25 | Unit + Retrieval Evaluation |
| Vector Search | Integration + Retrieval Evaluation |
| Hybrid Retrieval | Integration + Evaluation |
| Filters | Unit + Property-based |
| Ranking | Unit + Ranking Evaluation |
| PostgreSQL | Integration |
| Redis | Integration + Failure |
| FastAPI | Contract + Integration + E2E |
| Next.js | UI + API integration |
| Recommendation | Unit + Evaluation + E2E |
| Full System | E2E + Performance |

---

# 51. Testing Workflow

For every new feature:

```text
Define behavior
      ↓
Define failure cases
      ↓
Write unit tests
      ↓
Implement
      ↓
Integration tests
      ↓
Evaluation
      ↓
Regression check
      ↓
Performance measurement
      ↓
Document result
```

Testing should therefore be part of implementation rather than something added after the system is complete.

---

# 52. Testing Philosophy

ProductIQ has three distinct notions of correctness:

### Software correctness

Does the code behave according to its specification?

### Search correctness

Does the system retrieve and rank appropriate products?

### Product correctness

Are the returned product facts actually grounded in the catalog?

All three must be tested.

---

# 53. Final Testing Architecture

```text
                       ProductIQ
                           │
          ┌────────────────┼────────────────┐
          ↓                ↓                ↓
     Code Testing     Search Testing    Data Testing
          │                │                │
       Unit Tests      Retrieval Eval    Schema Tests
       Contract       Ranking Eval      Quality Tests
       Integration    E2E Evaluation    Consistency
          │                │                │
          └────────────────┼────────────────┘
                           ↓
                  Regression Testing
                           ↓
                   Performance Tests
                           ↓
                    Production CI/CD
```

---

# 54. Final Principle

> **ProductIQ is not considered correct merely because its API returns a response.**

A correct ProductIQ system must demonstrate:

```text
Correct code
    +
Correct data
    +
Correct retrieval
    +
Correct filtering
    +
Correct ranking
    +
Grounded results
    +
Safe failure behavior
    +
Measured performance
```

Only when these properties are verified should the system move from specification into implementation.