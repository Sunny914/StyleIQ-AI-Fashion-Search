# ProductIQ — Data Flow

**Project:** ProductIQ  
**Phase:** Phase 0 — Data Flow  
**Version:** v1.0  
**Status:** FROZEN

---

# 1. Purpose

This document defines how data moves through ProductIQ from product ingestion to search results and recommendations.

The primary goal is to establish a clear flow between:

- Product data
- Data processing
- Product representation
- Embeddings
- Search indexes
- User queries
- Query understanding
- Retrieval
- Filtering
- Ranking
- Caching
- API serving
- Frontend presentation
- User feedback

---

# 2. Two Major Data Flows

ProductIQ has two fundamentally different flows:

```text
                    PRODUCTIQ DATA FLOW
                           │
              ┌────────────┴────────────┐
              │                         │
              ▼                         ▼
        OFFLINE DATA FLOW         ONLINE QUERY FLOW
              │                         │
              ▼                         ▼
       Prepare the catalog        Answer the query
              │                         │
              ▼                         ▼
       Build search assets          Retrieve/rank
```

The offline flow prepares the system.

The online flow uses those prepared assets to answer user requests.

---

# 3. Offline Data Flow

The offline pipeline begins with raw product data.

```text
Raw Product Data
       ↓
Ingestion
       ↓
Cleaning
       ↓
Normalization
       ↓
Deduplication
       ↓
Product Understanding
       ↓
Canonical Product Representation
       ↓
 ┌─────┴─────────┐
 ▼               ▼
Database      Product Text
                  │
          ┌───────┴────────┐
          ▼                ▼
      Embedding          BM25
       Model             Index
          │
          ▼
      Embeddings
          │
          ▼
      pgvector
```

---

# 4. Step-by-Step Offline Flow

## Step 1 — Raw Product Data

The system receives product information from a controlled catalog.

Example:

```text
product_id: P10234
title: Nike Revolution 7
brand: Nike
category: Running Shoes
color: Black
price: 4299
description: Lightweight running shoes...
availability: true
```

At this stage the data may be:

- Incomplete
- Inconsistent
- Duplicated
- Incorrectly formatted
- Missing attributes

Therefore it cannot immediately be used for production search.

---

# 5. Step 2 — Data Ingestion

Raw data enters the ProductIQ data pipeline.

Conceptually:

```text
External Dataset / Catalog
          ↓
       Ingestion
          ↓
      Raw Dataset
```

The ingestion layer should preserve the original data as much as practical.

This allows us to reproduce and debug downstream transformations.

---

# 6. Step 3 — Data Cleaning

Cleaning removes or handles invalid records and fields.

Potential problems include:

```text
Missing product ID
Invalid price
Negative price
Malformed text
Missing category
Duplicate records
Invalid availability value
```

Example:

```text
price = "₹4,299"
```

may need to become:

```text
price = 4299
```

---

# 7. Step 4 — Normalization

Different products may represent the same concept differently.

Examples:

```text
"NIKE"
"Nike"
"nike"
```

should generally normalize to a consistent representation.

Likewise:

```text
"Running Shoe"
"running shoes"
"RUNNING SHOES"
```

may require normalization into a canonical representation.

Normalization improves:

- Filtering
- Lexical retrieval
- Deduplication
- Query matching
- Data quality

---

# 8. Step 5 — Deduplication

Duplicate products should be identified and handled.

For example:

```text
P101
Nike Air Max
₹4999

P102
Nike Air Max
₹4999
```

may represent the same catalog item.

The deduplication strategy will depend on available identifiers and product metadata.

Potential signals include:

- Product ID
- SKU
- Brand
- Title
- Model
- URL
- Attributes

---

# 9. Step 6 — Product Understanding

The cleaned product is transformed into a representation useful for search.

Example:

```text
Raw Product
     ↓
Product Understanding
     ↓
{
    brand: Nike,
    category: Running Shoes,
    color: Black,
    gender: Men,
    attributes: {...}
}
```

The objective is to create a consistent representation of product meaning and attributes.

---

# 10. Step 7 — Canonical Product Representation

After processing, each product should have a canonical representation.

Conceptually:

```text
Product
├── identity
│   └── product_id
│
├── textual fields
│   ├── title
│   └── description
│
├── categorical fields
│   ├── brand
│   ├── category
│   └── color
│
├── numerical fields
│   └── price
│
├── availability
│
└── additional attributes
```

This becomes the foundation for downstream retrieval.

---

# 11. Step 8 — Product Text Construction

Relevant product information is combined into a semantic text representation.

Example:

```text
Nike Revolution 7.
Nike.
Men's running shoes.
Black.
Lightweight athletic footwear designed for running.
```

This text is passed to the embedding model.

The exact template will be determined experimentally during the data-engineering phase.

---

# 12. Step 9 — Embedding Generation

The product text is passed through a Sentence Transformer or equivalent embedding model.

```text
Product Text
      ↓
Embedding Model
      ↓
Dense Vector
```

For example:

```text
Product
   ↓
[0.12, -0.41, 0.83, ...]
```

The vector dimension depends on the selected model.

The exact embedding model and dimension are intentionally not frozen yet.

---

# 13. Step 10 — Vector Storage

The generated product embedding is associated with the corresponding product.

Conceptually:

```text
Product ID
    +
Embedding
    ↓
PostgreSQL + pgvector
```

This allows the system to perform vector similarity search.

---

# 14. Step 11 — BM25 Index Construction

Product text is also used to construct a lexical search index.

```text
Product Text
      ↓
Tokenization / Processing
      ↓
BM25 Index
```

The BM25 index enables lexical retrieval for terms such as:

```text
Nike
Pegasus
Air Max
running
black
```

---

# 15. Offline Data State

At the end of the offline pipeline, ProductIQ has:

```text
                    PRODUCT CATALOG
                          │
              ┌───────────┴───────────┐
              ▼                       ▼
        Structured Data          Search Assets
              │                       │
              ▼               ┌───────┴───────┐
        PostgreSQL             ▼               ▼
                              BM25          Embeddings
                                               │
                                               ▼
                                           pgvector
```

The system is now prepared to answer user queries.

---

# 16. Online Query Flow

Now consider:

> **"black Nike running shoes under ₹5,000"**

The online flow begins when the user submits this query.

```text
User
 ↓
Next.js
 ↓
FastAPI
 ↓
Query Validation
 ↓
Query Understanding
 ↓
Structured Constraints + Semantic Query
 ↓
BM25 + Vector Retrieval
 ↓
Candidate Union
 ↓
Hard Filtering
 ↓
Feature Generation
 ↓
Ranking
 ↓
Top-K
 ↓
Redis
 ↓
FastAPI Response
 ↓
Next.js
 ↓
User
```

---

# 17. Step 1 — User Query

The user enters:

```text
black Nike running shoes under ₹5,000
```

The frontend sends the query to the backend.

---

# 18. Step 2 — Frontend Request

Next.js sends an HTTP request to FastAPI.

Conceptually:

```text
Next.js
   │
   │ search query
   ▼
FastAPI
```

The frontend is responsible for collecting and displaying the request.

It does not perform the core retrieval/ranking logic.

---

# 19. Step 3 — API Validation

FastAPI validates the incoming request.

Potential validation problems:

```text
Empty query
Malformed request
Invalid parameters
Unsupported values
```

If validation succeeds, the request enters the search service.

---

# 20. Step 4 — Query Understanding

The raw query:

```text
black Nike running shoes under ₹5,000
```

is transformed into structured information.

Conceptually:

```text
{
    brand: Nike,
    category: running shoes,
    color: black,
    max_price: 5000
}
```

The system also creates a semantic representation of the complete query.

Therefore:

```text
Raw Query
    ↓
Query Understanding
    ├── Structured constraints
    └── Semantic query
```

---

# 21. Step 5 — Query Embedding

The semantic query is passed through the same or compatible embedding model used for product embeddings.

```text
Query
 ↓
Embedding Model
 ↓
Query Vector
```

Conceptually:

```text
"black Nike running shoes under 5000"
                ↓
       [0.14, -0.37, ...]
```

This vector is used for semantic retrieval.

---

# 22. Step 6 — BM25 Retrieval

The query is also passed to BM25.

```text
Query
 ↓
BM25
 ↓
Lexical Candidates
```

BM25 may identify products containing strong lexical matches such as:

```text
Nike
black
running
```

---

# 23. Step 7 — Vector Retrieval

The query embedding is compared against product embeddings.

Conceptually:

```text
Query Vector
      ↓
Vector Similarity Search
      ↓
Semantically Similar Products
```

Cosine similarity may be used as the similarity measure.

The result is a semantic candidate set.

---

# 24. Step 8 — Candidate Union

The lexical and semantic candidates are combined.

```text
BM25 Candidates
       +
Vector Candidates
       ↓
Candidate Union
       ↓
Unique Candidate Pool
```

For example:

```text
BM25 → 300
Vector → 300

After deduplication:
~400 unique candidates
```

The exact candidate sizes are experimental parameters.

---

# 25. Step 9 — Hard Filtering

The structured constraints extracted from the query are applied.

Example:

```text
brand = Nike
category = running shoes
color = black
price <= 5000
availability = true
```

The candidate pool becomes:

```text
Candidate Pool
      ↓
Hard Filters
      ↓
Eligible Candidates
```

This step is critical.

A product with extremely high semantic similarity should not be returned if it violates a hard constraint such as:

```text
price > ₹5,000
```

when the query explicitly specifies a maximum price.

---

# 26. Step 10 — Feature Generation

For each remaining candidate, ProductIQ calculates ranking features.

Possible features:

```text
semantic_score
lexical_score
brand_match
category_match
color_match
price_compatibility
popularity
rating
availability
```

Conceptually:

```text
Candidate
    ↓
Feature Generation
    ↓
Feature Vector
```

---

# 27. Step 11 — Ranking

The ranking layer receives the candidate features.

```text
Candidates
    ↓
Ranking Model
    ↓
Relevance Scores
    ↓
Sorted Candidates
```

The initial ranking system may use a weighted scoring baseline.

Later, this can be replaced or supplemented with learning-to-rank.

---

# 28. Step 12 — Top-K Selection

After ranking:

```text
Ranked Candidates
      ↓
Top-K
      ↓
20 products
```

The value of K should be configurable.

For example:

```text
top_k = 20
```

The architecture does not require exactly 20.

---

# 29. Step 13 — Redis

Before or after executing the search pipeline, ProductIQ can use Redis as a cache.

Conceptually:

```text
Query
 ↓
Cache lookup
 ├── HIT  → Return cached results
 │
 └── MISS → Execute search
              ↓
          Store result
              ↓
          Return result
```

Caching strategy, TTL, and cache key structure will be determined during implementation.

---

# 30. Step 14 — API Response

FastAPI converts the ranked results into a structured response.

Conceptually:

```text
{
    query: "...",
    results: [
        product_1,
        product_2,
        ...
    ]
}
```

The exact API schema will be defined during the interface-design stage.

---

# 31. Step 15 — Frontend Rendering

Next.js receives the response.

It renders:

```text
Search Results
├── Product Card
├── Product Card
├── Product Card
└── ...
```

Each product card may display:

- Product image
- Product name
- Brand
- Price
- Relevant attributes
- Rating
- Availability

The frontend does not generate product facts.

---

# 32. Step 16 — User Interaction

The user can interact with the returned products.

Potential signals:

```text
impression
click
view
wishlist
add_to_cart
purchase
```

These events can eventually flow back into the backend.

```text
User Interaction
       ↓
Event Logging
       ↓
Feedback Dataset
       ↓
Evaluation / Ranking / Recommendation
```

This creates the foundation for a future learning loop.

---

# 33. Complete Search Data Flow

The complete flow can be summarized as:

```text
                       USER
                         │
                         ▼
              "black Nike running
                shoes under ₹5000"
                         │
                         ▼
                      Next.js
                         │
                         ▼
                      FastAPI
                         │
                         ▼
                Query Validation
                         │
                         ▼
               Query Understanding
                    /          \
                   /            \
                  ▼              ▼
          Structured Intent   Semantic Intent
                  │              │
                  ▼              ▼
              Filters        Query Embedding
                                 │
                         ┌───────┴───────┐
                         ▼               ▼
                       BM25       Vector Search
                         │               │
                         ▼               ▼
                   Lexical          Semantic
                  Candidates       Candidates
                         │               │
                         └───────┬───────┘
                                 ▼
                         Candidate Union
                                 │
                                 ▼
                          Hard Filtering
                                 │
                                 ▼
                         Feature Generation
                                 │
                                 ▼
                              Ranking
                                 │
                                 ▼
                              Top-K
                                 │
                                 ▼
                              Redis
                                 │
                                 ▼
                             FastAPI
                                 │
                                 ▼
                              Next.js
                                 │
                                 ▼
                                USER
```

---

# 34. Complete Offline + Online Flow

The entire ProductIQ system can be represented as:

```text
                         OFFLINE
                            │
                    Raw Product Data
                            │
                            ▼
                       Ingestion
                            │
                            ▼
                     Data Cleaning
                            │
                            ▼
                      Normalization
                            │
                            ▼
                      Deduplication
                            │
                            ▼
                  Product Understanding
                            │
                            ▼
               Canonical Product Data
                     /            \
                    ▼              ▼
              PostgreSQL      Product Text
                                  │
                           ┌──────┴──────┐
                           ▼             ▼
                     Embeddings        BM25
                           │             │
                           ▼             ▼
                       pgvector      BM25 Index


                         ONLINE
                            │
                            ▼
                           USER
                            │
                            ▼
                      Natural Query
                            │
                            ▼
                     Query Understanding
                       /            \
                      ▼              ▼
               Constraints       Embedding
                      │              │
                      │        ┌─────┴─────┐
                      │        ▼           ▼
                      │      BM25       Vector
                      │        │           │
                      │        └─────┬─────┘
                      │              ▼
                      └───────► Candidate Pool
                                    │
                                    ▼
                               Hard Filters
                                    │
                                    ▼
                              Feature Generation
                                    │
                                    ▼
                                  Ranking
                                    │
                                    ▼
                                  Top-K
                                    │
                                    ▼
                                  Redis
                                    │
                                    ▼
                                 FastAPI
                                    │
                                    ▼
                                 Next.js
                                    │
                                    ▼
                                   USER
```

---

# 35. Data Ownership and Transformation

At each stage, data changes form.

```text
Raw Product
    ↓
Clean Product
    ↓
Canonical Product
    ↓
Product Text
    ↓
Product Embedding
    ↓
Indexed Product
```

For queries:

```text
Raw Query
    ↓
Validated Query
    ↓
Structured Query + Semantic Query
    ↓
Query Embedding
    ↓
Candidates
    ↓
Filtered Candidates
    ↓
Ranked Candidates
    ↓
Top-K Response
```

This transformation chain should remain explicit throughout implementation.

---

# 36. Critical Data Invariants

ProductIQ should maintain several important invariants.

## Invariant 1

Every searchable product must have a valid product identifier.

## Invariant 2

Every vector must be associated with the correct product.

## Invariant 3

Query and product embeddings must be compatible with the selected embedding model.

## Invariant 4

Hard filters must be applied consistently.

## Invariant 5

Returned products must exist in the canonical product catalog.

## Invariant 6

Ranking must operate only on retrieved candidates.

## Invariant 7

Cached results must not become the source of truth.

---

# 37. Search vs Recommendation Data Flow

## Search

```text
Query
 ↓
Query Understanding
 ↓
Retrieval
 ↓
Filtering
 ↓
Ranking
 ↓
Results
```

## Similar Product Recommendation

```text
Product
 ↓
Product Representation
 ↓
Embedding
 ↓
Vector Retrieval
 ↓
Optional Filtering
 ↓
Ranking
 ↓
Recommendations
```

## Future Personalized Recommendation

```text
User
 ↓
Interaction History
 ↓
User Preference Representation
 ↓
Candidate Generation
 ↓
Ranking
 ↓
Recommendations
```

---

# 38. Failure-Aware Data Flow

Data should never silently become invalid.

For example:

```text
Embedding Generation
       │
       ├── Success → Store embedding
       │
       └── Failure → Record failure
                       │
                       ▼
                 Do not index
                 invalid vector
```

Likewise:

```text
Database
   │
   ├── Available → Continue
   │
   └── Unavailable → Controlled error
```

and:

```text
Redis
   │
   ├── Available → Use cache
   │
   └── Unavailable → Bypass cache
```

---

# 39. Data Flow Principles

### Principle 1

Data should have a clear owner at every stage.

### Principle 2

Transformations should be reproducible.

### Principle 3

Raw data should not be silently overwritten by processed data.

### Principle 4

Search indexes should be rebuildable from canonical data.

### Principle 5

Caches should be disposable.

### Principle 6

Product facts should originate from catalog data.

### Principle 7

Search quality should be measurable from query → result data.

### Principle 8

Offline preparation should minimize online computation.

---

# 40. Data Flow Status

| Data Flow | Status |
|---|---|
| Offline catalog flow | ✅ Frozen |
| Data cleaning flow | ✅ Frozen |
| Product representation | ✅ Frozen |
| Embedding flow | ✅ Frozen |
| BM25 indexing flow | ✅ Frozen |
| Vector storage flow | ✅ Frozen |
| Online query flow | ✅ Frozen |
| Query understanding flow | ✅ Frozen |
| Hybrid retrieval flow | ✅ Frozen |
| Filtering flow | ✅ Frozen |
| Ranking flow | ✅ Frozen |
| Top-K flow | ✅ Frozen |
| Redis flow | ✅ Frozen |
| API flow | ✅ Frozen |
| Frontend flow | ✅ Frozen |
| Feedback flow | 🟡 Future |
| Personalized recommendation flow | 🟡 Future |

**Data Flow v1.0 is now frozen.**