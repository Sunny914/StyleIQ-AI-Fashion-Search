# ProductIQ — Interfaces & Contracts

**Project:** ProductIQ  
**Phase:** Phase 0 — Interfaces & Contracts  
**Version:** v1.0  
**Status:** FROZEN

---

# 1. Purpose

This document defines the conceptual contracts between ProductIQ components.

The objective is to establish:

- What data each component receives
- What data each component produces
- Which fields are required
- Which fields are optional
- What guarantees each component provides
- How components communicate without depending on implementation details

The implementation language, classes, database schemas, and API code will be created later.

---

# 2. Contract Philosophy

Each component should have:

```text
Input
  ↓
Processing
  ↓
Output
  ↓
Guarantees
```

A component should not silently modify another component's responsibility.

For example:

```text
Query Understanding
        ↓
structured query
```

It should not also perform ranking.

Similarly:

```text
Retrieval
        ↓
candidate products
```

It should not secretly become the final ranking system.

---

# 3. Core Domain Objects

The initial ProductIQ system uses these conceptual objects:

```text
Product
Query
Filter
Candidate
RankingFeatures
RankedResult
SearchResponse
Recommendation
FeedbackEvent
```

---

# 4. Product Contract

A `Product` represents a canonical product in the ProductIQ catalog.

Conceptually:

```text
Product
├── identity
├── textual information
├── categorical attributes
├── numerical attributes
├── availability
├── metadata
└── embedding reference
```

### Required fields

```text
product_id
title
brand
category
price
availability
```

### Optional fields

```text
description
color
size
gender
rating
popularity
attributes
image_url
product_url
seller
metadata
embedding
```

### Conceptual contract

```text
Product {
    product_id
    title
    description?
    brand
    category
    price
    color?
    size?
    gender?
    attributes?
    availability
    rating?
    popularity?
    metadata?
}
```

The exact database schema will be defined during the data-engineering phase.

---

# 5. Product Invariants

A valid searchable product must satisfy:

1. `product_id` exists.
2. `title` is not empty.
3. `price` is valid when price is required by the catalog.
4. `category` is valid or explicitly marked unknown.
5. Availability has a defined state.
6. The product embedding, if present, corresponds to the correct product.
7. Product data is traceable to its source record.

---

# 6. Query Contract

A `Query` represents a user's search request after validation and query understanding.

Conceptually:

```text
Query
├── raw query
├── normalized query
├── intent
├── entities
├── filters
└── semantic representation
```

### Required fields

```text
raw_text
normalized_text
```

### Optional / derived fields

```text
intent
entities
filters
embedding
```

Example:

```text
Query {
    raw_text:
        "black Nike running shoes under 5000"

    normalized_text:
        "black nike running shoes under 5000"

    intent:
        product_search

    filters:
        brand = Nike
        category = running shoes
        color = black
        max_price = 5000
}
```

---

# 7. Query Invariants

A valid query must:

1. Preserve the original user input.
2. Have a normalized representation.
3. Never fabricate an extracted attribute.
4. Clearly distinguish explicit constraints from inferred semantic meaning.
5. Maintain the original query even if parsing fails.

If query understanding cannot confidently extract a field, the system should not invent it.

---

# 8. Filter Contract

A `Filter` represents a structured constraint.

Conceptually:

```text
Filter {
    field
    operator
    value
}
```

Examples:

```text
brand = Nike

price <= 5000

color = black

category = running shoes

availability = true
```

Possible operators include:

```text
=
!=
<
<=
>
>=
IN
NOT IN
```

The supported operators will be constrained by the actual product schema.

---

# 9. Hard vs Soft Constraints

A filter can represent a hard constraint.

Example:

```text
price <= 5000
```

Hard constraints must be enforced before final ranking.

Soft preferences should generally be represented as ranking features rather than mandatory filters.

Example:

```text
high rating
popular product
semantic similarity
```

---

# 10. Query Understanding Contract

The query-understanding component receives:

```text
Raw Query
```

and produces:

```text
Structured Query Information
+
Semantic Query Representation
```

Conceptually:

```text
Raw Query
    ↓
Query Understanding
    ↓
{
    normalized_text,
    intent,
    entities,
    filters,
    semantic_text
}
```

The component must not:

- Retrieve products
- Rank products
- Generate product facts
- Invent attributes

Its responsibility is understanding the query.

---

# 11. Embedding Contract

The embedding component converts text into a dense vector.

### Input

```text
text
```

### Output

```text
embedding
```

Conceptually:

```text
Embedding {
    vector
    dimension
    model_id
    model_version
}
```

The model metadata is important because embeddings generated by incompatible models should not be silently mixed.

---

# 12. Embedding Invariants

For a valid embedding:

1. The vector must have the expected dimension.
2. The embedding must be generated by a known model/version.
3. The vector must not contain invalid numerical values.
4. Query and product embeddings used for similarity search must be compatible.
5. The source text should be traceable.

---

# 13. Retrieval Contract

The retrieval layer receives:

```text
Query
+
retrieval configuration
```

and produces:

```text
Candidate Set
```

Retrieval may have multiple implementations:

```text
BM25 Retrieval
Vector Retrieval
Hybrid Retrieval
```

---

# 14. Candidate Contract

A `Candidate` represents a product retrieved as potentially relevant.

Conceptually:

```text
Candidate {
    product_id
    retrieval_sources
    lexical_score?
    semantic_score?
}
```

Example:

```text
Candidate {
    product_id: P10234
    retrieval_sources:
        [BM25, VECTOR]

    lexical_score:
        8.31

    semantic_score:
        0.84
}
```

---

# 15. Retrieval Invariants

Retrieval must:

1. Return only products that exist in the catalog.
2. Preserve product IDs.
3. Preserve retrieval provenance.
4. Return retrieval scores when available.
5. Avoid final ranking decisions.
6. Allow candidates from multiple retrieval systems to be merged.

---

# 16. Hybrid Retrieval Contract

Hybrid retrieval combines candidate sets from:

```text
BM25
+
Vector Search
```

Conceptually:

```text
Query
 │
 ├── BM25 → Candidates A
 │
 └── Vector → Candidates B
                  │
                  ▼
             Candidate Union
                  │
                  ▼
             Deduplicated Set
```

The exact hybrid score combination is not frozen yet.

Possible future strategies include:

- Score normalization + weighted combination
- Reciprocal Rank Fusion
- Learned fusion
- Retrieval-source-specific ranking

The initial implementation will establish a measurable baseline before adding complexity.

---

# 17. Filter Application Contract

The filtering layer receives:

```text
Candidate Set
+
Structured Filters
```

and produces:

```text
Eligible Candidate Set
```

Example:

```text
Candidates
    ↓
price <= 5000
brand = Nike
color = black
availability = true
    ↓
Filtered Candidates
```

The filtering layer must not modify the underlying product record.

---

# 18. Ranking Features Contract

Ranking features represent information used to order candidates.

Conceptually:

```text
RankingFeatures {
    semantic_score
    lexical_score
    brand_match
    category_match
    color_match
    price_compatibility
    popularity?
    rating?
}
```

The exact feature set will evolve through experiments.

---

# 19. Ranking Contract

The ranking component receives:

```text
Eligible Candidates
+
Ranking Features
```

and produces:

```text
Ranked Results
```

Conceptually:

```text
Candidates
   ↓
Feature Generation
   ↓
Ranking
   ↓
Sorted Results
```

---

# 20. Ranking Invariants

Ranking must:

1. Only rank candidates supplied by retrieval.
2. Respect hard filtering decisions.
3. Produce a deterministic result for the same inputs when deterministic configuration is used.
4. Preserve product identity.
5. Produce a comparable ranking score.
6. Support configurable top-K selection.

---

# 21. RankedResult Contract

A `RankedResult` represents a candidate after ranking.

Conceptually:

```text
RankedResult {
    product_id
    rank
    score
    features?
}
```

Example:

```text
RankedResult {
    product_id: P10234
    rank: 1
    score: 0.91
}
```

The system may retain ranking features internally for debugging and evaluation.

---

# 22. SearchResponse Contract

The search service ultimately returns a `SearchResponse`.

Conceptually:

```text
SearchResponse {
    query
    results
    total_candidates?
    retrieval_metadata?
    latency_metadata?
}
```

Example:

```text
SearchResponse {
    query:
        "black Nike running shoes under 5000"

    results:
        [
            RankedResult(...),
            RankedResult(...),
            ...
        ]
}
```

Internal debugging metadata should not automatically be exposed to end users.

---

# 23. Top-K Contract

The search system accepts a configurable `K`.

Example:

```text
K = 20
```

The ranking system produces:

```text
rank 1
rank 2
...
rank K
```

The system must not return more than K results unless explicitly requested.

---

# 24. Recommendation Contract

A `Recommendation` represents a product recommended in a recommendation context.

Conceptually:

```text
Recommendation {
    product_id
    score
    reason?
    source
}
```

Potential recommendation sources:

```text
content_similarity
semantic_similarity
popularity
collaborative_filtering
hybrid
```

For the MVP, recommendation will primarily use content/semantic similarity.

---

# 25. Recommendation Input Contract

A similar-product recommendation may receive:

```text
Product ID
+
Recommendation configuration
```

and return:

```text
Recommended Products
```

Conceptually:

```text
Product
   ↓
Product Embedding
   ↓
Vector Retrieval
   ↓
Candidates
   ↓
Ranking
   ↓
Recommendations
```

---

# 26. Feedback Event Contract

Future user feedback will be represented as an event.

Conceptually:

```text
FeedbackEvent {
    event_id
    user_id?
    session_id?
    product_id
    query?
    event_type
    timestamp
    metadata?
}
```

Possible event types:

```text
impression
click
view
wishlist
add_to_cart
purchase
```

User identity fields may be optional depending on privacy and system requirements.

---

# 27. Search Service Contract

The search service is the primary backend orchestration boundary.

### Input

```text
SearchRequest
```

Conceptually:

```text
SearchRequest {
    query
    top_k?
    filters?
}
```

### Processing

```text
SearchRequest
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
Top-K
```

### Output

```text
SearchResponse
```

---

# 28. Search Service Responsibility

The search service coordinates the pipeline.

It should **not** implement every algorithm itself.

Conceptually:

```text
Search Service
 │
 ├── Query Understanding
 │
 ├── Retriever
 │    ├── BM25
 │    └── Vector
 │
 ├── Filter Engine
 │
 ├── Feature Generator
 │
 └── Ranker
```

This allows individual components to be tested and replaced independently.

---

# 29. Recommendation Service Contract

The recommendation service follows a similar orchestration model.

```text
Recommendation Service
 │
 ├── Candidate Generator
 │
 ├── Filtering
 │
 ├── Feature Generator
 │
 └── Ranker
```

Input:

```text
RecommendationRequest
```

Output:

```text
RecommendationResponse
```

---

# 30. Data Access Contract

The application should not scatter raw database queries throughout business logic.

Conceptually:

```text
Service
   ↓
Repository / Data Access Layer
   ↓
PostgreSQL
```

The data-access layer owns:

- Product retrieval
- Product persistence
- Structured filtering
- Database interactions

This keeps database details separate from search orchestration.

---

# 31. Cache Contract

The cache layer provides:

```text
get(key)
set(key, value, ttl)
delete(key)
```

Conceptually:

```text
Application
     ↓
Cache Interface
     ↓
Redis
```

The rest of the application should not need to know Redis-specific implementation details.

---

# 32. Component Contract Map

```text
                         SearchRequest
                              │
                              ▼
                      Search Service
                              │
                              ▼
                    Query Understanding
                              │
                    ┌─────────┴─────────┐
                    ▼                   ▼
              Structured Query      Query Embedding
                    │                   │
                    ▼                   ▼
                 Filters         Hybrid Retrieval
                                        │
                               ┌────────┴────────┐
                               ▼                 ▼
                             BM25             Vector
                               │                 │
                               └────────┬────────┘
                                        ▼
                                  Candidates
                                        │
                                        ▼
                                    Filtering
                                        │
                                        ▼
                                Feature Generation
                                        │
                                        ▼
                                     Ranking
                                        │
                                        ▼
                                  RankedResult
                                        │
                                        ▼
                                  SearchResponse
```

---

# 33. Contract Dependency Rules

The following dependency rules apply:

### Rule 1

The frontend communicates with the backend API.

### Rule 2

The API communicates with services.

### Rule 3

Services communicate with domain components.

### Rule 4

Domain components communicate through explicit interfaces.

### Rule 5

Search logic should not depend directly on frontend code.

### Rule 6

Ranking should not directly own database infrastructure.

### Rule 7

The cache should never become the canonical data source.

### Rule 8

Indexes should not become the authoritative product database.

---

# 34. Contract Versioning

Interfaces may evolve.

Breaking changes should be treated explicitly.

For example:

```text
SearchResponse v1
```

may later evolve into:

```text
SearchResponse v2
```

API changes should be documented rather than silently breaking clients.

---

# 35. Error Contracts

Components must communicate failures explicitly.

Conceptual errors include:

```text
InvalidQuery
ProductNotFound
NoResults
EmbeddingError
RetrievalError
RankingError
DatabaseError
CacheError
TimeoutError
```

The system should distinguish:

```text
No relevant products found
```

from:

```text
Search infrastructure failed
```

These are fundamentally different conditions.

---

# 36. No-Hallucination Contract

A core system contract is:

> **The search system may only return product entities that can be traced to the product catalog.**

Therefore:

```text
product_id
      ↓
PostgreSQL
      ↓
Canonical Product
```

must be resolvable for every returned product.

If a candidate cannot be resolved to a canonical product record, it should not be presented as a valid product result.

---

# 37. Contract Testing Strategy

Each contract should eventually have tests verifying:

### Input validation

Invalid input is rejected.

### Output schema

Output contains required fields.

### Invariants

Required guarantees remain true.

### Compatibility

Upstream and downstream components agree on data structure.

### Failure behavior

Errors are explicit rather than silently converted into invalid data.

---

# 38. Implementation Mapping

These conceptual contracts will eventually map to implementation modules such as:

```text
src/productiq/
├── query/
├── retrieval/
├── ranking/
├── recommendation/
├── embeddings/
├── db/
├── cache/
├── services/
└── api/
```

The exact file structure will be finalized when implementation begins.

---

# 39. What Is Frozen vs Experimental?

## Frozen

```text
Product
Query
Filter
Candidate
RankingFeatures
RankedResult
SearchResponse
Recommendation
FeedbackEvent
Search Service
Recommendation Service
Cache boundary
Data access boundary
```

## Experimental

```text
Exact embedding model
Exact embedding dimension
Exact ranking features
Hybrid fusion method
Ranking algorithm
Recommendation algorithm
Candidate count
Cache TTL
API schema details
```

This distinction prevents architecture from becoming unnecessarily rigid.

---

# 40. Final Contract Flow

The complete conceptual contract chain is:

```text
User Input
    ↓
SearchRequest
    ↓
Query
    ↓
Filters + Embedding
    ↓
Candidates
    ↓
Eligible Candidates
    ↓
RankingFeatures
    ↓
RankedResult
    ↓
SearchResponse
    ↓
Frontend
```

---

# 41. Status

| Contract | Status |
|---|---|
| Product | ✅ Frozen |
| Query | ✅ Frozen |
| Filter | ✅ Frozen |
| Candidate | ✅ Frozen |
| RankingFeatures | ✅ Frozen |
| RankedResult | ✅ Frozen |
| SearchResponse | ✅ Frozen |
| Recommendation | ✅ Frozen |
| FeedbackEvent | 🟡 Future-ready |
| Search Service | ✅ Frozen |
| Recommendation Service | ✅ Frozen |
| Data Access boundary | ✅ Frozen |
| Cache boundary | ✅ Frozen |
| Error contract | ✅ Defined |

**Interfaces & Contracts v1.0 is now frozen.**