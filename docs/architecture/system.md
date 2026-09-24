# ProductIQ — System Architecture

**Project:** ProductIQ  
**Phase:** Phase 0 — System Architecture  
**Version:** v1.0  
**Status:** FROZEN

---

# 1. Architectural Objective

ProductIQ is designed as an AI-powered fashion product search, discovery, and recommendation system.

The architecture must support:

1. Natural-language query understanding
2. Structured constraint extraction
3. Semantic product retrieval
4. Lexical product retrieval
5. Hybrid candidate generation
6. Hard constraint filtering
7. Candidate ranking
8. Product recommendations
9. Offline evaluation
10. Low-latency online serving
11. Future scalability without unnecessary infrastructure

The architecture follows:

> **Understand → Retrieve → Filter → Rank → Serve**

---

# 2. High-Level Architecture

ProductIQ is divided into two major systems:

```text
                    PRODUCTIQ
                        │
            ┌───────────┴───────────┐
            │                       │
            ▼                       ▼
        OFFLINE                  ONLINE
        SYSTEM                   SYSTEM
            │                       │
            ▼                       ▼
      Product Data             User Query
            │                       │
            ▼                       ▼
    Data Processing          Query Understanding
            │                       │
            ▼                       ▼
 Product Understanding      Filters + Embedding
            │                       │
      ┌─────┴─────┐                 ▼
      ▼           ▼          Hybrid Retrieval
 PostgreSQL    Search Indexes       │
      │           │                ▼
      │           │              Ranking
      │           │                │
      └─────┬─────┘                ▼
            │                     Top-K
            │                       │
            │                     Redis
            │                       │
            └───────────────────────┤
                                    ▼
                                  FastAPI
                                    │
                                    ▼
                                  Next.js
                                    │
                                    ▼
                                   User
```

---

# 3. Offline vs Online Architecture

A fundamental architectural distinction is:

## Offline System

Responsible for preparing the product catalog and models/indexes before users search.

Examples:

- Data ingestion
- Data cleaning
- Normalization
- Deduplication
- Product representation
- Embedding generation
- BM25 index construction
- Vector index preparation
- Evaluation
- Model experimentation

---

## Online System

Responsible for answering user queries.

Examples:

- Query understanding
- Query embedding
- Retrieval
- Filtering
- Ranking
- Caching
- API response

---

# 4. Why Separate Offline and Online Work?

Some operations are expensive and do not need to happen for every user query.

For example, suppose we have:

```text
1,000,000 products
```

We should not generate a new product embedding for every product whenever a user searches.

Instead:

```text
OFFLINE

Product
   ↓
Clean
   ↓
Represent
   ↓
Embed
   ↓
Store
```

Then at query time:

```text
ONLINE

User query
   ↓
Query embedding
   ↓
Search existing product embeddings
```

This dramatically reduces online computation.

---

# 5. Offline Data Pipeline

The initial catalog pipeline is:

```text
Raw Product Data
       │
       ▼
Data Ingestion
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
Canonical Product Representation
       │
       ├───────────────┐
       ▼               ▼
 PostgreSQL       Product Text
       │               │
       │               ▼
       │          Embedding Model
       │               │
       │               ▼
       │          Product Embeddings
       │               │
       ├───────────────┤
       │               │
       ▼               ▼
 Structured Data   Vector Search
                       │
                       ▼
                  pgvector / FAISS
```

In parallel:

```text
Product Text
     ↓
Tokenization
     ↓
BM25 Index
```

---

# 6. PostgreSQL — Source of Truth

PostgreSQL is the primary product database.

It stores structured product information such as:

```text
product_id
title
description
brand
category
price
color
size
attributes
availability
rating
metadata
```

The database is the **source of truth** for product records.

---

# 7. pgvector

pgvector extends PostgreSQL with vector storage and similarity search capabilities.

A product can conceptually contain:

```text
Product
├── structured fields
│   ├── title
│   ├── brand
│   ├── category
│   ├── price
│   └── attributes
│
└── embedding
```

This gives ProductIQ a unified architecture:

```text
                 PostgreSQL
                 /        \
                /          \
     Structured Data      pgvector
                              │
                         Embeddings
```

This is particularly useful because search results often require both:

```text
vector similarity
+
structured filtering
```

For example:

```text
semantic similarity
AND
brand = Nike
AND
price <= 5000
AND
availability = true
```

Keeping these concerns close to the same data system simplifies the initial architecture.

---

# 8. Product Representation

A product is represented through both:

### Structured representation

```text
brand
category
color
price
size
availability
attributes
```

### Semantic representation

A text representation is constructed from relevant product information and transformed into an embedding.

Conceptually:

```text
Product
   ↓
Title + Description + Attributes + Category
   ↓
Product Text
   ↓
Sentence Transformer
   ↓
Embedding
```

The exact product-text construction will be determined during the data-engineering phase.

---

# 9. BM25 Retrieval

BM25 provides lexical retrieval.

It is useful when exact or near-exact terms matter.

Examples:

```text
Nike
Pegasus 41
Air Max
running
black
```

Conceptually:

```text
Product catalog
      ↓
Tokenization
      ↓
BM25 index
```

At query time:

```text
User query
     ↓
BM25
     ↓
Lexical candidates
```

BM25 is particularly valuable for terms where semantic similarity alone may not preserve the exact lexical requirement.

---

# 10. Semantic Retrieval

Semantic retrieval uses Transformer-based embeddings.

Offline:

```text
Product
   ↓
Sentence Transformer
   ↓
Product embedding
   ↓
Vector index
```

Online:

```text
User query
   ↓
Sentence Transformer
   ↓
Query embedding
   ↓
Vector similarity search
```

The system can then retrieve products whose representations are semantically close to the query.

Cosine similarity is one possible similarity measure.

---

# 11. Hybrid Retrieval

ProductIQ does not rely exclusively on either BM25 or vector search.

Instead:

```text
                       Query
                         │
              ┌──────────┴──────────┐
              ▼                     ▼
            BM25               Vector Search
              │                     │
              ▼                     ▼
       Lexical candidates     Semantic candidates
              │                     │
              └──────────┬──────────┘
                         ▼
                  Candidate Union
                         │
                         ▼
                  Candidate Pool
```

This improves coverage across different types of queries.

---

# 12. Query Understanding

Before retrieval, ProductIQ analyzes the user's query.

Example:

```text
"black Nike running shoes under ₹5,000"
```

Conceptually:

```text
Raw Query
   ↓
Query Understanding
   ↓
{
    category: running shoes,
    brand: Nike,
    color: black,
    max_price: 5000
}
```

The system also maintains a semantic representation of the query.

Therefore the query produces two important outputs:

```text
Structured intent
+
Semantic representation
```

---

# 13. Hard Filters vs Soft Ranking Signals

This is one of the most important architectural decisions.

## Hard constraints

Conditions that the product must satisfy.

Examples:

```text
price <= 5000
brand = Nike
availability = true
```

These should be enforced as filters when appropriate.

---

## Soft signals

Signals that help determine ordering.

Examples:

```text
semantic similarity
lexical relevance
popularity
rating
attribute match
price compatibility
```

These belong primarily in candidate scoring/ranking.

---

# 14. Online Search Pipeline

The complete online pipeline is:

```text
User
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
 │
 ├───────────────┐
 ▼               ▼
Structured       Semantic
Constraints      Query Embedding
 │               │
 │               │
 ▼               ▼
Filters      ┌── BM25
             │
             └── Vector Search
                    │
                    ▼
              Candidate Union
                    │
                    ▼
              Hard Constraints
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
               API Response
                    │
                    ▼
                  Next.js
                    │
                    ▼
                   User
```

---

# 15. Why Retrieval Comes Before Ranking

Suppose the catalog contains:

```text
1,000,000 products
```

Ranking every product for every query is unnecessarily expensive.

Instead:

```text
1,000,000
     ↓
Retrieval
     ↓
500 candidates
     ↓
Ranking
     ↓
20 results
```

Retrieval focuses on:

> **Candidate recall**

Ranking focuses on:

> **Candidate ordering**

This separation allows expensive ranking logic to operate on a much smaller candidate set.

---

# 16. Candidate Pool

The retrieval stage produces a candidate pool.

For example:

```text
BM25 → 300 candidates
Vector → 300 candidates
```

The candidate sets may overlap.

After merging:

```text
Unique candidates → ~400–500
```

The exact candidate count will be determined experimentally.

We will **not hard-code "500" as an architectural requirement**.

---

# 17. Ranking Layer

The ranking layer receives candidates and generates a final ordering.

Conceptually:

```text
Candidate
   ↓
Feature Generation
   ↓
Ranking Model
   ↓
Relevance Score
   ↓
Sorted Candidates
   ↓
Top-K
```

Potential ranking features:

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

The initial ranking approach may be a deterministic/weighted baseline.

A learning-to-rank model can be introduced after sufficient evaluation data exists.

---

# 18. Recommendation Architecture

Search and recommendation are separate capabilities.

## Search

```text
User Query
    ↓
Query Understanding
    ↓
Retrieval
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
Similarity Search
   ↓
Similar Products
```

Future personalized recommendation:

```text
User
 │
 ├── clicks
 ├── views
 ├── wishlist
 ├── cart
 └── purchases
       │
       ▼
User Preference Signals
       │
       ▼
Recommendation Model
       │
       ▼
Recommended Products
```

Personalized recommendation is not required for the MVP.

---

# 19. Redis

Redis is an acceleration layer, not the source of truth.

Conceptually:

```text
                  Search Request
                       │
                       ▼
                     Redis
                    /     \
              Cache Hit   Cache Miss
                  │          │
                  │          ▼
                  │       Search Pipeline
                  │          │
                  │          ▼
                  │       Results
                  │          │
                  └──────┬───┘
                         ▼
                       User
```

Potential cached information includes:

- Repeated search results
- Frequently requested queries
- Short-lived application state
- Other carefully selected low-latency data

If Redis is unavailable, the system should ideally fall back to the primary search path rather than treating Redis as the source of truth.

---

# 20. FastAPI

FastAPI is the serving layer between the frontend and the search/recommendation system.

Its responsibilities include:

```text
HTTP request handling
Input validation
Authentication/authorization where needed
Service orchestration
Response serialization
Error handling
```

FastAPI should **not contain the entire search implementation inside route functions**.

Conceptually:

```text
FastAPI Route
      ↓
Search Service
      ↓
Query Understanding
      ↓
Retrieval
      ↓
Ranking
      ↓
Response
```

---

# 21. Next.js

Next.js is responsible for the user-facing application.

Responsibilities include:

```text
Search interface
Product cards
Filters
Product pages
Recommendation UI
Loading/error states
User interactions
```

The ML/search logic remains on the backend.

---

# 22. Data Ownership

Each major component has a clear responsibility.

| Component | Responsibility |
|---|---|
| PostgreSQL | Product/source-of-truth data |
| pgvector | Product/query vector similarity |
| BM25 | Lexical retrieval |
| Sentence Transformers | Embedding generation |
| Ranking layer | Candidate ordering |
| Redis | Low-latency caching |
| FastAPI | Backend/API serving |
| Next.js | User interface |
| FAISS | Offline vector-search experiments |
| Docker | Reproducible environments |

---

# 23. Offline Evaluation Architecture

Evaluation is an independent concern.

```text
Evaluation Queries
       │
       ▼
Search System
       │
       ▼
Retrieved Results
       │
       ▼
Ground-Truth Relevance
       │
       ▼
Metrics
       │
 ┌─────┼─────┬─────┐
 ▼     ▼     ▼     ▼
Recall Precision MRR NDCG
```

We should be able to compare:

```text
BM25
Vector Search
Hybrid Search
Hybrid + Filters
Hybrid + Ranking
```

---

# 24. Failure Boundaries

The architecture must anticipate failures.

### Query failure

```text
Invalid / empty query
        ↓
Validation
        ↓
Informative response
```

### No results

```text
Valid query
     ↓
No candidates
     ↓
Graceful zero-result response
```

### Redis failure

```text
Redis unavailable
     ↓
Bypass cache
     ↓
Execute normal search path
```

### Ranking failure

The system should have a defined fallback ranking strategy.

For example:

```text
Ranking model unavailable
        ↓
Fallback ranking
        ↓
Return candidates
```

The exact fallback will be defined during implementation.

### Database failure

```text
Database unavailable
       ↓
Controlled API error
       ↓
No fabricated product response
```

### Embedding failure

The system must not silently produce invalid embeddings.

It should either:

- use an appropriate fallback retrieval path, or
- return a controlled error,

depending on the failure context.

---

# 25. Architectural Principles

## Principle 1 — PostgreSQL is the source of truth

Search indexes and caches can be rebuilt.

The canonical product data lives in PostgreSQL.

---

## Principle 2 — Retrieval and ranking are separate

Retrieval finds candidates.

Ranking orders candidates.

---

## Principle 3 — Semantic similarity does not replace structured filtering

Price, availability, and other hard constraints must be treated appropriately as structured constraints.

---

## Principle 4 — BM25 and semantic retrieval are complementary

Neither retrieval method is assumed to solve every query type.

---

## Principle 5 — Expensive computation belongs where it makes sense

Product embeddings and indexes are primarily prepared offline.

Query embeddings and retrieval happen online.

---

## Principle 6 — Evaluation drives model complexity

We do not introduce a sophisticated ranker simply because it sounds impressive.

We introduce it when evaluation demonstrates that it provides value.

---

## Principle 7 — Infrastructure must have a reason

We will not introduce:

- Kubernetes
- Kafka
- Airflow
- Elasticsearch
- dedicated vector databases
- microservices

unless a concrete requirement justifies them.

---

# 26. Initial Technology Architecture

```text
                     ┌─────────────────────┐
                     │       Next.js       │
                     │      Frontend       │
                     └──────────┬──────────┘
                                │
                                ▼
                     ┌─────────────────────┐
                     │       FastAPI       │
                     │       Backend       │
                     └──────────┬──────────┘
                                │
                       ┌────────┴────────┐
                       ▼                 ▼
                Query/Search         Redis
                  Services           Cache
                       │
             ┌─────────┴─────────┐
             ▼                   ▼
          BM25              Vector Search
             │                   │
             │              pgvector
             │                   │
             └─────────┬─────────┘
                       ▼
                    Ranking
                       │
                       ▼
                  PostgreSQL
                       │
                       ▼
                 Product Data
```

Offline:

```text
                    Product Data
                         │
                         ▼
                  Data Processing
                         │
             ┌───────────┴───────────┐
             ▼                       ▼
        Product Text            Structured Data
             │                       │
             ▼                       ▼
      Sentence Transformer      PostgreSQL
             │
             ▼
        Embeddings
             │
             ▼
          pgvector

Product Text
     │
     ▼
    BM25
     │
     ▼
 BM25 Index
```

---

# 27. What Is Intentionally Not Fixed Yet

The architecture is frozen at the **component level**, but some implementation choices remain experimental.

We will determine experimentally:

- Exact embedding model
- Embedding dimension
- Exact BM25 implementation
- Candidate pool size
- Similarity thresholds
- Score normalization method
- Initial ranking formula
- Learning-to-rank algorithm
- pgvector index configuration
- Redis TTL
- API latency targets
- Product-text construction strategy

This is intentional.

Architecture should be stable while model parameters remain experimental.

---

# 28. Architectural Decision Summary

ProductIQ will initially use:

```text
PostgreSQL
        +
pgvector
        +
BM25
        +
Transformer embeddings
        +
Hybrid retrieval
        +
Structured filtering
        +
Ranking
        +
Redis
        +
FastAPI
        +
Next.js
        +
Docker
```

The architecture deliberately avoids unnecessary distributed infrastructure during the MVP.

---

# 29. End-to-End Mental Model

The entire system can be remembered as:

```text
             PRODUCT CATALOG
                    │
             Offline Processing
                    │
       ┌────────────┴────────────┐
       ▼                         ▼
 Structured Data             Embeddings
       │                         │
 PostgreSQL                  pgvector
       │
       └──────────┐
                  ▼
                BM25


             USER QUERY
                  │
                  ▼
          Query Understanding
                  │
          ┌───────┴────────┐
          ▼                ▼
      Constraints       Embedding
          │                │
          ▼                ▼
       Filters       Vector Retrieval
          │                │
          └───────┬────────┘
                  ▼
             BM25 Retrieval
                  │
                  ▼
           Candidate Pool
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

# 30. Architecture Status

| Architecture Component | Status |
|---|---|
| Offline / online separation | ✅ Frozen |
| Data flow | ✅ Frozen at conceptual level |
| PostgreSQL role | ✅ Frozen |
| pgvector role | ✅ Frozen |
| BM25 role | ✅ Frozen |
| Semantic retrieval | ✅ Frozen |
| Hybrid retrieval | ✅ Frozen |
| Filtering | ✅ Frozen |
| Ranking | ✅ Frozen |
| Redis role | ✅ Frozen |
| FastAPI role | ✅ Frozen |
| Next.js role | ✅ Frozen |
| Recommendation boundary | ✅ Frozen |
| Evaluation boundary | ✅ Frozen |
| Failure boundaries | ✅ Defined |
| Exact model/index parameters | 🔬 Experimental |

**System Architecture v1.0 is now frozen at the component and responsibility level.**