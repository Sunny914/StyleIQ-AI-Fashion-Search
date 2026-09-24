# ProductIQ — Technology Decisions

**Project:** ProductIQ  
**Phase:** Phase 0 — Technology Decisions  
**Version:** v1.0  
**Status:** FROZEN

---

# 1. Purpose

This document defines the technologies selected for ProductIQ and the architectural reasoning behind each choice.

The goal is to prevent technology selection from becoming arbitrary or driven by popularity.

Each technology must have a clear responsibility.

The core principle is:

> **Choose the simplest technology that satisfies the current requirement, and introduce additional infrastructure only when the system demonstrates a need for it.**

---

# 2. Initial Technology Stack

ProductIQ's initial stack is:

```text
Language
    Python

ML / Deep Learning
    PyTorch
    Hugging Face Transformers
    Sentence Transformers

Data
    PostgreSQL
    pgvector

Information Retrieval
    BM25
    FAISS

Backend
    FastAPI

Caching
    Redis

Frontend
    Next.js

Infrastructure
    Docker

Version Control
    Git / GitHub
```

---

# 3. Python

## Decision

**Python** is the primary backend, ML, data-processing, and experimentation language.

## Why?

ProductIQ is heavily dependent on:

- Machine learning
- NLP
- Embeddings
- Information retrieval
- Data processing
- Evaluation
- Model experimentation

Python provides a mature ecosystem across all of these areas.

Conceptually:

```text
Data
 ↓
Python
 ├── preprocessing
 ├── embeddings
 ├── retrieval
 ├── ranking
 ├── evaluation
 └── API
```

## Alternatives

Possible alternatives include:

- Go
- Java
- TypeScript

These may be appropriate for some production services, but Python provides the strongest unified environment for the ML/search-heavy MVP.

## Decision

Use Python initially.

A separate high-performance service will only be introduced if profiling demonstrates a real need.

---

# 4. PyTorch

## Decision

Use **PyTorch** for machine-learning experimentation and model development where custom ML components are required.

## Why?

ProductIQ may eventually require:

- Custom ranking models
- Fine-tuning
- Neural retrieval experiments
- Model evaluation
- Training pipelines

PyTorch provides the required flexibility.

However:

> ProductIQ will not train a custom deep-learning model simply for the sake of having one.

Pretrained models will be preferred when they are sufficient.

---

# 5. Hugging Face Transformers

## Decision

Use Hugging Face Transformers for access to pretrained Transformer models.

Potential applications include:

- Text representation
- Query understanding
- Classification
- Reranking
- Fine-tuning
- NLP experimentation

The exact models will be selected during experimentation.

---

# 6. Sentence Transformers

## Decision

Use Sentence Transformers for initial semantic embedding and semantic retrieval experiments.

## Why?

ProductIQ needs to convert:

```text
Product text
```

and

```text
User query
```

into vector representations.

Conceptually:

```text
Product text
      ↓
Sentence Transformer
      ↓
Product embedding

User query
      ↓
Sentence Transformer
      ↓
Query embedding
```

This provides a straightforward bi-encoder architecture for semantic retrieval.

---

# 7. PostgreSQL

## Decision

Use **PostgreSQL as the primary database and source of truth**.

## Why?

ProductIQ has highly structured product information:

```text
product_id
brand
category
price
color
size
availability
attributes
```

These naturally fit a relational database.

PostgreSQL also provides:

- Strong consistency
- SQL
- Transactions
- Indexing
- Constraints
- Mature tooling
- Relationships
- JSON/JSONB support where useful

Most importantly, ProductIQ frequently needs:

```text
structured filtering
+
vector similarity
```

within the same product data system.

---

# 8. Why Not MongoDB Initially?

MongoDB could represent product documents naturally.

However, ProductIQ's core workload benefits from:

```text
structured attributes
+
relational querying
+
filtering
+
vector search
```

PostgreSQL provides a strong unified foundation for these requirements.

Therefore MongoDB is not required for the initial architecture.

This is not a claim that MongoDB cannot work.

It simply isn't necessary for the current requirements.

---

# 9. pgvector

## Decision

Use **pgvector** for vector storage and vector similarity search alongside PostgreSQL.

## Why?

ProductIQ needs:

```text
Product metadata
+
Product embeddings
```

and frequently needs to combine them.

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

Keeping vectors alongside product records simplifies the initial architecture.

Conceptually:

```text
              PostgreSQL
             /          \
            /            \
     Product Data      pgvector
                         │
                     Embeddings
```

---

# 10. Why Not a Dedicated Vector Database Initially?

Possible dedicated vector databases include:

- Pinecone
- Weaviate
- Milvus
- Qdrant

These can become useful at larger scale or under specific operational requirements.

However, ProductIQ initially benefits from minimizing system complexity.

Using:

```text
PostgreSQL + pgvector
```

gives us one primary data system instead of:

```text
PostgreSQL
+
Vector Database
```

A dedicated vector database may be evaluated later if:

- Dataset size becomes very large
- Query throughput increases substantially
- Vector-specific operational requirements appear
- Filtering/search workloads justify separation
- Benchmarking demonstrates a meaningful advantage

---

# 11. BM25

## Decision

Use BM25 as the initial lexical retrieval method.

## Why?

Semantic retrieval is not sufficient for every search.

BM25 is useful for terms such as:

```text
Nike
Pegasus 41
Air Max
specific model numbers
rare attributes
exact product terminology
```

The system therefore combines:

```text
BM25
+
Vector Retrieval
```

---

# 12. Why Not Only Vector Search?

Pure vector search can struggle with exact lexical requirements.

For example:

```text
"Samsung Galaxy..."
```

or:

```text
"Nike Pegasus 41"
```

may contain important exact terms.

A hybrid architecture gives ProductIQ access to both:

```text
Lexical relevance
+
Semantic relevance
```

---

# 13. Why Not Only BM25?

Pure lexical retrieval can struggle with paraphrases.

For example:

```text
"shoes for daily jogging"
```

may need to retrieve:

```text
"running footwear"
```

even if the wording differs.

Therefore semantic retrieval complements BM25.

---

# 14. FAISS

## Decision

Use FAISS primarily as an **offline experimentation and benchmarking tool**, rather than making it the primary production database.

## Why?

FAISS is useful for:

- Approximate nearest-neighbor experiments
- Vector search benchmarking
- Index experimentation
- Retrieval experiments
- Comparing search strategies

Conceptually:

```text
Embedding Dataset
       ↓
FAISS
       ↓
ANN Experiments
       ↓
Recall / Latency / Memory Analysis
```

The production-oriented architecture will initially center around PostgreSQL + pgvector.

---

# 15. FastAPI

## Decision

Use FastAPI as the backend API layer.

## Responsibilities

FastAPI handles:

```text
HTTP requests
Request validation
Authentication/authorization where required
Service orchestration
Response serialization
Error handling
Health endpoints
```

It should not contain all business/search logic directly.

Instead:

```text
FastAPI Route
      ↓
Service Layer
      ↓
Search Components
```

---

# 16. Why FastAPI?

ProductIQ requires a Python-native backend closely integrated with:

- ML models
- Retrieval
- Ranking
- Data processing

FastAPI provides a natural boundary between the frontend and Python search system.

---

# 17. Redis

## Decision

Use Redis as a **low-latency caching layer**.

Redis is not the source of truth.

The architecture is:

```text
PostgreSQL → Source of Truth

Redis → Cache / Acceleration
```

Potential cache targets include:

- Repeated search queries
- Frequently accessed product results
- Short-lived application state
- Other expensive-to-compute transient results

---

# 18. Why Redis?

Consider:

```text
User A:
"black Nike running shoes under 5000"
```

The system performs:

```text
query understanding
+
embedding
+
BM25
+
vector retrieval
+
ranking
```

If the same query occurs repeatedly, Redis can avoid repeating some work.

Conceptually:

```text
Query
 ↓
Redis
 ├── HIT  → cached response
 │
 └── MISS → search pipeline
               ↓
             result
               ↓
          cache result
```

---

# 19. Redis Failure Philosophy

Redis should not become a single point of truth.

If Redis is unavailable:

```text
Redis unavailable
       ↓
Bypass cache
       ↓
Normal search pipeline
```

This may increase latency but should not require inventing or losing product data.

---

# 20. Next.js

## Decision

Use Next.js for the frontend.

## Responsibilities

Next.js handles:

- Search UI
- Product cards
- Product detail pages
- Filters
- Recommendations
- Loading states
- Error states
- User interaction

It does not own:

- Embedding generation
- BM25
- Vector retrieval
- Ranking
- Core recommendation logic

Those remain backend responsibilities.

---

# 21. Why Next.js?

ProductIQ needs a modern web interface capable of:

- Fast UI rendering
- Routing
- Interactive search
- Product pages
- Future personalization

Next.js provides an appropriate frontend framework without mixing frontend and ML responsibilities.

---

# 22. Docker

## Decision

Use Docker for reproducible development and deployment environments.

Initially, containers may include:

```text
PostgreSQL
Redis
Backend
Frontend
```

ML experimentation may run in a dedicated development environment depending on hardware.

---

# 23. Why Docker?

Without containerization, developers may encounter differences in:

```text
Python versions
Package versions
PostgreSQL versions
Redis versions
System dependencies
```

Docker makes the environment more reproducible.

---

# 24. Git + GitHub

## Decision

Use Git for version control and GitHub for repository hosting.

Git tracks:

- Source code
- Configuration
- Documentation
- Tests
- Architecture decisions

GitHub provides:

- Repository hosting
- Collaboration
- Issue tracking
- Pull requests
- CI/CD integration later

---

# 25. Technology Responsibility Map

| Technology | Primary Responsibility |
|---|---|
| Python | Application + ML ecosystem |
| PyTorch | ML experimentation/training |
| Transformers | Transformer models |
| Sentence Transformers | Semantic embeddings |
| PostgreSQL | Source-of-truth product data |
| pgvector | Vector storage/search |
| BM25 | Lexical retrieval |
| FAISS | Offline ANN experiments |
| FastAPI | Backend API |
| Redis | Caching |
| Next.js | Frontend |
| Docker | Environment/deployment reproducibility |
| Git/GitHub | Version control |

---

# 26. Technologies Deliberately Not Used Initially

The following are intentionally excluded from the MVP unless requirements justify them.

## Kubernetes

Not initially required.

Reason:

ProductIQ does not initially have enough distributed infrastructure to justify Kubernetes.

---

## Kafka

Not initially required.

Reason:

We do not yet have a high-throughput event-streaming requirement.

---

## Airflow

Not initially required.

Reason:

The initial offline pipeline can be executed through scripts/jobs without a workflow orchestrator.

Airflow can be introduced when pipeline scheduling and dependency management become complex enough to justify it.

---

## Elasticsearch / OpenSearch

Not initially required.

Reason:

BM25 + PostgreSQL/pgvector provides an appropriate initial retrieval architecture.

Elasticsearch/OpenSearch can be evaluated later if lexical search scale or operational requirements justify it.

---

## Dedicated Vector Database

Not initially required.

Reason:

pgvector provides a simpler unified architecture for the current scale.

---

## Microservices

Not initially required.

Reason:

A modular monolith is simpler for the MVP.

We can split services later based on measured requirements.

---

## Cloud-Native Infrastructure

Not initially required.

Reason:

The first objective is to validate the search system itself.

Cloud deployment should follow demonstrated requirements.

---

# 27. Architectural Philosophy

ProductIQ follows:

> **Start simple → measure → identify bottleneck → introduce complexity → measure again.**

Not:

> **Add every popular technology from the beginning.**

Therefore the architecture intentionally starts with:

```text
Python
+
PostgreSQL
+
pgvector
+
BM25
+
Sentence Transformers
+
FastAPI
+
Redis
+
Next.js
+
Docker
```

---

# 28. Technology Evolution Strategy

The stack may evolve through stages.

### Stage 1 — MVP

```text
PostgreSQL
pgvector
BM25
Sentence Transformers
FastAPI
Redis
Next.js
Docker
```

### Stage 2 — Search optimization

Potential additions:

```text
ANN optimization
Learning-to-rank
Cross-encoder reranking
FAISS benchmarking
Advanced indexing
```

### Stage 3 — Scale

Potential additions if justified:

```text
Dedicated search infrastructure
Dedicated vector database
Message queues
Workflow orchestration
Distributed services
Kubernetes
Cloud infrastructure
```

These are possibilities, not commitments.

---

# 29. Decision Criteria for Adding Technology

A new technology should be introduced only when at least one of the following is demonstrated:

1. Existing architecture cannot satisfy a requirement.
2. Measured performance is insufficient.
3. Reliability requirements demand it.
4. Operational complexity has exceeded what the current architecture can reasonably handle.
5. The technology provides a measurable benefit.

The decision should be documented in an Architecture Decision Record (ADR).

---

# 30. Technology Decision Summary

The initial ProductIQ architecture is intentionally centered around a small number of strongly integrated components.

```text
                    PRODUCTIQ
                        │
              ┌─────────┴─────────┐
              │                   │
          Backend              Frontend
              │                   │
           FastAPI              Next.js
              │
      ┌───────┼────────┐
      │       │        │
 PostgreSQL  Redis   ML/Search
      │                │
 pgvector         BM25 + Embeddings
                         │
                       Ranking
```

The architecture prioritizes:

- Simplicity
- Reproducibility
- ML experimentation
- Search quality
- Measurability
- Clear component ownership
- Future extensibility

---

# 31. Status

| Decision | Status |
|---|---|
| Python | ✅ Frozen |
| PyTorch | ✅ Selected |
| Transformers | ✅ Selected |
| Sentence Transformers | ✅ Selected |
| PostgreSQL | ✅ Frozen |
| pgvector | ✅ Frozen |
| BM25 | ✅ Frozen |
| FAISS | ✅ Experimental/offline |
| FastAPI | ✅ Frozen |
| Redis | ✅ Frozen |
| Next.js | ✅ Frozen |
| Docker | ✅ Frozen |
| Git/GitHub | ✅ Frozen |
| Kubernetes | ❌ Not initially |
| Kafka | ❌ Not initially |
| Airflow | ❌ Not initially |
| Elasticsearch/OpenSearch | ❌ Not initially |
| Dedicated vector DB | ❌ Not initially |
| Microservices | ❌ Not initially |

**Technology Decisions v1.0 is now frozen.**