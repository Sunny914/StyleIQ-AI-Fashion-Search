# ProductIQ — Definition of Done

**Version:** 1.0  
**Phase:** Phase 0 — System Specification  
**Status:** Frozen for MVP architecture

---

# 1. Purpose

The Definition of Done establishes the conditions that must be satisfied before ProductIQ can be considered complete for a given development stage.

ProductIQ will not be considered complete merely because:

- the code runs
- the API responds
- products appear on the screen
- embeddings have been generated
- a dashboard/frontend exists

A feature is done only when its:

```text
Implementation
+
Correctness
+
Testing
+
Evaluation
+
Observability
+
Documentation
```

are sufficiently complete for its intended stage.

---

# 2. Definition of Done Hierarchy

ProductIQ uses four levels of completion:

```text
Level 1 → Component Done
Level 2 → Pipeline Done
Level 3 → MVP Done
Level 4 → Portfolio / Production-Ready Demonstration
```

These levels should not be confused.

A component can be technically complete while the overall search system is not.

---

# 3. Level 1 — Component Done

A component is considered done when:

- its responsibility is clearly defined
- its interface is documented
- its implementation exists
- unit tests exist
- expected failure cases are handled
- input/output contracts are respected
- logging is present where appropriate
- documentation exists
- no known critical correctness issue remains

Example:

```text
Query Understanding
        ↓
Implementation
        ↓
Unit Tests
        ↓
Failure Tests
        ↓
Contract Verified
        ↓
Component Done
```

---

# 4. Level 2 — Pipeline Done

A complete subsystem is done when its components work together.

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
Results
```

The pipeline is done when:

- components integrate successfully
- interfaces are compatible
- error handling works
- fallback behavior works
- integration tests pass
- representative queries work
- outputs are grounded
- performance has been measured

---

# 5. Level 3 — MVP Done

The ProductIQ MVP is complete when the following end-to-end system works:

```text
Product Catalog
      ↓
Data Cleaning
      ↓
Normalization
      ↓
Deduplication
      ↓
Product Representation
      ↓
Embeddings
      ↓
BM25 + Vector Index
      ↓
Query Understanding
      ↓
Hybrid Retrieval
      ↓
Hard Filtering
      ↓
Ranking
      ↓
Top-K Results
      ↓
FastAPI
      ↓
Frontend
```

Every critical stage must be operational.

---

# 6. Product Catalog Definition of Done

The catalog is done when:

- required fields are defined
- schema validation exists
- product IDs are unique
- duplicate products are handled
- prices are valid
- categories are normalized
- brands are normalized
- availability is represented consistently
- missing optional fields have defined behavior
- dataset versioning exists
- data-quality statistics are available

Required product fields:

```text
product_id
title
brand
category
price
availability
```

---

# 7. Data Pipeline Definition of Done

The data pipeline is done when:

```text
Raw Data
   ↓
Cleaning
   ↓
Normalization
   ↓
Deduplication
   ↓
Canonical Product
```

is reproducible.

The pipeline must:

- be runnable from a clean environment
- produce deterministic transformations where expected
- record dataset version
- report failed records
- report processed record counts
- prevent invalid records from silently entering indexes

---

# 8. Product Representation Definition of Done

Product representation is done when every indexed product has a consistent representation for:

### Structured retrieval

```text
brand
category
price
availability
attributes
```

### Lexical retrieval

```text
product_text
```

### Semantic retrieval

```text
embedding
```

The representation must be generated from the canonical product record.

---

# 9. Embedding Pipeline Definition of Done

The embedding pipeline is done when:

- embedding model is explicitly specified
- model version is recorded
- vector dimension is known
- product embeddings are generated
- invalid embeddings are rejected
- query/product embedding compatibility is verified
- embedding generation is reproducible where required
- embedding failures are observable
- embedding metadata is stored

The exact model remains an implementation/experiment decision unless explicitly frozen later.

---

# 10. BM25 Definition of Done

BM25 retrieval is done when:

- product text is indexed
- query tokenization works
- exact product names can be retrieved
- brand names can be retrieved
- rare product terms can be retrieved
- zero-result behavior is defined
- index versioning exists
- index loading works
- retrieval latency can be measured

---

# 11. Vector Search Definition of Done

Vector retrieval is done when:

- product embeddings are stored
- query embeddings can be generated
- vector dimensions match
- similarity search works
- top-K retrieval works
- index version is tracked
- zero-result behavior works
- vector failures are handled
- retrieval latency is measured

---

# 12. Hybrid Retrieval Definition of Done

Hybrid retrieval is done when:

```text
BM25
 +
Vector Search
      ↓
Candidate Union
```

works correctly.

It must:

- deduplicate candidates
- preserve product IDs
- preserve retrieval-source information
- preserve component scores
- handle one retriever failing
- have a defined fusion strategy
- have retrieval evaluation results

---

# 13. Query Understanding Definition of Done

Query understanding is done when ProductIQ can reliably process representative queries involving:

- brands
- categories
- colors
- prices
- availability
- multiple constraints
- semantic intent
- paraphrases

Example:

```text
"black Nike running shoes under ₹5000"
```

should produce a representation containing appropriate structured constraints and semantic intent.

It must also avoid inventing unsupported constraints.

---

# 14. Hard Filtering Definition of Done

Hard filtering is one of the MVP's correctness gates.

It is done when:

- explicit constraints are extracted correctly
- filters are applied deterministically
- invalid products are removed
- ranking cannot override hard constraints
- filter tests pass
- property-based tests pass where appropriate
- filter failures are observable

Example:

```text
User:
Nike shoes under ₹5000

Returned:
Nike
Price ≤ ₹5000
```

must always hold.

---

# 15. Ranking Definition of Done

Ranking is done when:

- ranking features are defined
- feature calculation works
- ranking logic is implemented
- missing features are handled
- invalid scores are rejected
- ranking is deterministic where expected
- fallback ranking exists
- ranking evaluation has been performed

The exact ranking algorithm may evolve through experimentation.

---

# 16. Search API Definition of Done

The FastAPI search endpoint is done when it:

- validates input
- invokes the search pipeline
- returns structured results
- follows the API contract
- returns appropriate errors
- handles timeouts
- exposes request identifiers
- does not leak internal exceptions
- has integration tests
- has contract tests

---

# 17. Recommendation Definition of Done

The initial recommendation capability is done when ProductIQ can accept a product or supported context and return related catalog products.

It must:

- use catalog products only
- exclude duplicates
- handle missing source products
- return ranked recommendations
- have basic evaluation
- clearly distinguish recommendations from search results

Advanced personalization is not required for MVP completion.

---

# 18. Redis Definition of Done

Redis is done when:

- search result caching works
- cache keys are deterministic
- TTL behavior works
- serialization works
- cache misses work
- stale entries are handled
- Redis failure bypasses the cache safely

Redis is an optimization layer.

Its failure must not invalidate search correctness.

---

# 19. Frontend Definition of Done

The frontend is done when a user can:

1. enter a natural-language query
2. submit the query
3. see loading state
4. receive search results
5. see relevant product information
6. handle no results
7. handle API errors
8. retry failed requests
9. navigate to the product where supported

The frontend must never fabricate missing product information.

---

# 20. Grounding Definition of Done

Grounding is a hard requirement.

Every returned product must satisfy:

```text
returned.product_id
        ↓
canonical catalog
        ↓
exists
```

Displayed fields must correspond to the canonical product record.

For example:

```text
Returned price
      ==
Catalog price
```

where price is displayed.

---

# 21. Evaluation Definition of Done

ProductIQ must have a versioned evaluation dataset.

The dataset should include:

- query
- relevant product
- relevance grade
- query category
- dataset version

The system must have baseline measurements for:

```text
BM25
Vector
Hybrid
Hybrid + Filters
Hybrid + Ranking
```

At minimum, evaluation should include:

```text
Recall@K
Precision@K
MRR
NDCG@K
```

Exact acceptance thresholds should be established after baseline measurements rather than invented before experimentation.

---

# 22. Query-Type Evaluation Definition of Done

Evaluation must not rely only on an aggregate score.

Results should be broken down by:

```text
Exact
Brand
Category
Attribute
Price
Multi-constraint
Semantic
Paraphrased
Ambiguous
Difficult
```

This allows us to identify where ProductIQ actually succeeds or fails.

---

# 23. Regression Testing Definition of Done

A permanent regression suite must exist.

It should contain representative high-value queries.

Example:

```text
black Nike running shoes under ₹5000
shoes for jogging
Nike Pegasus 41
men's waterproof running shoes
black shoes
```

Important changes must run this suite.

Changes include:

- embedding model
- ranking logic
- retrieval configuration
- query parser
- product representation
- index configuration

---

# 24. Failure Handling Definition of Done

The system must have tested behavior for:

```text
Invalid query
Empty query
Database failure
Redis failure
BM25 failure
Vector failure
Embedding failure
Ranking failure
Timeout
Invalid product data
Index mismatch
No results
Partial pipeline failure
```

Each critical failure must have:

```text
Detection
↓
Classification
↓
Fallback or controlled failure
↓
Logging
```

---

# 25. Observability Definition of Done

The system must make it possible to determine:

- what query was executed
- when it was executed
- which dataset was used
- which model was used
- which retrieval systems ran
- how long each stage took
- whether cache was used
- whether fallback occurred
- whether an error occurred

At minimum, searches should be associated with:

```text
request_id
query_id
dataset_version
model_version
index_version
```

---

# 26. Performance Definition of Done

Performance must be measured before optimization.

At minimum measure:

```text
end-to-end latency
query-understanding latency
embedding latency
BM25 latency
vector latency
filter latency
ranking latency
database latency
cache latency
```

Performance work follows:

```text
Measure
 ↓
Profile
 ↓
Identify bottleneck
 ↓
Optimize
 ↓
Measure again
```

---

# 27. Reproducibility Definition of Done

Another engineer should be able to reproduce the system from the repository.

The repository must contain or document:

- dependencies
- environment setup
- configuration
- data preparation
- database setup
- index creation
- embedding generation
- application startup
- testing commands

Docker should eventually provide a reproducible environment for the application stack.

---

# 28. Documentation Definition of Done

The following documentation must exist:

```text
README.md

docs/
├── product/
│   └── requirements.md
│
└── architecture/
    ├── system.md
    ├── data-flow.md
    ├── technology-decisions.md
    ├── interfaces.md
    ├── evaluation.md
    ├── failure-handling.md
    └── testing-strategy.md
```

The README must explain:

- what ProductIQ is
- problem being solved
- architecture
- technology stack
- how to run it
- how to test it
- example query
- evaluation approach

---

# 29. Code Quality Definition of Done

Code must:

- follow project conventions
- have meaningful names
- have clear module boundaries
- avoid unnecessary duplication
- separate business logic from API routes
- avoid hard-coded secrets
- use configuration appropriately
- contain appropriate type hints
- contain tests for important logic

The goal is maintainable engineering rather than maximum abstraction.

---

# 30. Security Definition of Done

Before MVP completion:

- secrets are not committed
- `.env` is ignored
- `.env.example` exists
- SQL queries are parameterized
- API input is validated
- request sizes are controlled
- sensitive internal errors are not returned
- dependencies are managed explicitly

---

# 31. Git Definition of Done

The repository should maintain meaningful history.

Commits should represent logical units such as:

```text
feat: add product schema
feat: implement product normalization
feat: add BM25 retrieval
feat: add vector retrieval
feat: add hybrid candidate generation
test: add retrieval evaluation
fix: handle missing product price
```

Avoid one enormous commit containing the entire project.

---

# 32. MVP Acceptance Test

The MVP should pass an end-to-end demonstration such as:

### Query

```text
black Nike running shoes under ₹5000
```

### Expected pipeline

```text
Query
 ↓
Query Understanding
 ↓
Extract:
brand = Nike
category = running shoes
color = black
max_price = ₹5000
 ↓
BM25 Retrieval
+
Vector Retrieval
 ↓
Candidate Union
 ↓
Hard Filtering
 ↓
Ranking
 ↓
Top-K
 ↓
Catalog Verification
 ↓
API
 ↓
Frontend
```

Every returned result must:

```text
be a real catalog product
AND
satisfy explicit constraints
AND
have valid product information
```

---

# 33. MVP Acceptance Checklist

## Product

- [ ] Natural-language product search works
- [ ] Product catalog exists
- [ ] Product schema validated
- [ ] Product data normalized
- [ ] Duplicate products handled

## Query Understanding

- [ ] Query normalization works
- [ ] Brand extraction works
- [ ] Category extraction works
- [ ] Attribute extraction works
- [ ] Price extraction works
- [ ] Multi-constraint queries work
- [ ] Unsupported assumptions are avoided

## Retrieval

- [ ] BM25 works
- [ ] Vector search works
- [ ] Hybrid retrieval works
- [ ] Candidate deduplication works
- [ ] Retrieval failures have fallback behavior

## Filtering

- [ ] Hard filters work
- [ ] Filter correctness tested
- [ ] Ranking cannot bypass filters

## Ranking

- [ ] Ranking works
- [ ] Ranking features defined
- [ ] Fallback ranking works
- [ ] Ranking evaluated

## Grounding

- [ ] Every result maps to catalog
- [ ] Product fields match catalog
- [ ] No fabricated products

## API

- [ ] API contract implemented
- [ ] Input validation works
- [ ] Error handling works
- [ ] Timeout handling works

## Frontend

- [ ] Search interface works
- [ ] Results display correctly
- [ ] Empty state works
- [ ] Error state works

## Infrastructure

- [ ] PostgreSQL works
- [ ] pgvector works
- [ ] Redis works
- [ ] Redis failure is safe
- [ ] Docker setup works

## Testing

- [ ] Unit tests
- [ ] Integration tests
- [ ] Contract tests
- [ ] Retrieval evaluation
- [ ] Ranking evaluation
- [ ] E2E tests
- [ ] Failure tests
- [ ] Regression tests

## Documentation

- [ ] README
- [ ] Architecture documentation
- [ ] API documentation
- [ ] Setup instructions
- [ ] Evaluation documentation
- [ ] Known limitations documented

---

# 34. Portfolio-Ready Definition of Done

Because ProductIQ is also a portfolio project, an additional layer is required.

The project should demonstrate that the developer understands:

```text
Data Engineering
        ↓
NLP / Query Understanding
        ↓
Embeddings
        ↓
Information Retrieval
        ↓
Hybrid Search
        ↓
Ranking
        ↓
Evaluation
        ↓
Backend Engineering
        ↓
Caching
        ↓
Deployment
```

The portfolio version should therefore include evidence of engineering decisions rather than only a working UI.

---

# 35. Portfolio Evidence

The repository should ideally demonstrate:

### Architecture

Clear system architecture diagram.

### Data

Clear product schema and data pipeline.

### Retrieval

BM25 vs vector vs hybrid comparison.

### Evaluation

Metrics and query-level analysis.

### Ranking

Explanation of ranking features and experiments.

### Engineering

FastAPI, PostgreSQL, pgvector, Redis, Docker.

### Reliability

Failure handling and fallback behavior.

### Reproducibility

Clear setup and execution instructions.

---

# 36. What Does NOT Define Done

The following are not sufficient by themselves:

```text
Code runs
API returns 200
Frontend looks good
Embeddings exist
Docker starts
GitHub repository exists
One example query works
```

These demonstrate functionality, not completion.

---

# 37. MVP Completion Gate

ProductIQ may move from MVP development to final portfolio polishing only when:

```text
                    MVP
                     │
        ┌────────────┼────────────┐
        ↓            ↓            ↓
    Functional    Correct      Evaluated
        │            │            │
        └────────────┼────────────┘
                     ↓
                  Tested
                     ↓
                Observable
                     ↓
               Reproducible
                     ↓
                Documented
                     ↓
              MVP COMPLETE
```

---

# 38. Final Definition

ProductIQ MVP is **Done** when:

> **A reproducible end-to-end system can accept natural-language fashion queries, understand structured and semantic intent, retrieve candidates using lexical and semantic retrieval, enforce explicit constraints, rank grounded catalog products, return them through an API and frontend, handle defined failures safely, and demonstrate its search quality through a versioned evaluation and testing framework.**

---

# 39. Phase Transition Rule

Phase 0 is complete only when:

```text
Product Specification       ✅
System Architecture         ✅
Data Flow                   ✅
Technology Decisions        ✅
Interfaces / Contracts      ✅
Evaluation Strategy         ✅
Failure Handling            ✅
Testing Strategy            ✅
Definition of Done          ✅
```

After this point:

```text
SPECIFICATION
     ↓
ARCHITECTURE REVIEW
     ↓
IMPLEMENTATION
```

No major architecture component should be added casually during implementation.

If a major change becomes necessary, it should be documented as an architecture decision/change rather than silently modifying the original design.

---

# 40. Engineering Principle

> **Done means proven, not merely implemented.**

ProductIQ should move forward based on evidence:

```text
Build
 ↓
Test
 ↓
Measure
 ↓
Evaluate
 ↓
Understand failures
 ↓
Improve
 ↓
Re-test
```

This loop is the foundation of the project's engineering methodology.