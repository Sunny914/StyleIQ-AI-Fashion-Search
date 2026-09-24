# ProductIQ — Evaluation Strategy

**Project:** ProductIQ  
**Phase:** Phase 0 — Evaluation Strategy  
**Version:** v1.0  
**Status:** FROZEN

---

# 1. Purpose

This document defines how ProductIQ will measure the quality of its search and recommendation systems.

The evaluation framework must allow us to:

1. Measure retrieval quality.
2. Measure ranking quality.
3. Compare different search approaches.
4. Detect regressions.
5. Identify failure patterns.
6. Guide model and architecture decisions.
7. Demonstrate measurable improvement.

The central principle is:

> **Every major search improvement must be measurable.**

---

# 2. What Are We Evaluating?

ProductIQ has several stages that must be evaluated separately.

```text id="5mnjv7"
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
Final Results
```

Therefore evaluation should not treat the system as one black box only.

We evaluate:

```text id="9g7v7x"
1. Query Understanding
2. Retrieval
3. Filtering
4. Ranking
5. End-to-End Search
6. Recommendation
```

---

# 3. Evaluation Philosophy

We will use a layered evaluation strategy.

### Level 1 — Component Evaluation

Evaluate individual components.

Example:

```text
BM25
Vector Search
Query Parser
Ranker
```

### Level 2 — Pipeline Evaluation

Evaluate combinations.

```text
BM25
Vector
Hybrid
Hybrid + Filtering
Hybrid + Ranking
```

### Level 3 — End-to-End Evaluation

Evaluate:

```text
User Query
    ↓
Entire ProductIQ Pipeline
    ↓
Final Top-K Results
```

This allows us to understand **where improvements actually come from**.

---

# 4. Evaluation Dataset

ProductIQ requires a fixed evaluation dataset.

The core dataset will contain:

```text id="bx8lzr"
Query
Product
Relevance
```

Conceptually:

```text id="t7fn0y"
query_id
query
product_id
relevance
```

Example:

```text id="q2vph5"
Query:
"black Nike running shoes under 5000"

Product:
P10234

Relevance:
3
```

---

# 5. Relevance Labels

We will use graded relevance rather than only binary relevance.

Initial scale:

```text id="l7f36c"
0 → Not relevant
1 → Slightly relevant
2 → Relevant
3 → Highly relevant
```

### Example

Query:

> "black Nike running shoes under ₹5,000"

| Product | Relevance |
|---|---:|
| Black Nike running shoe, ₹4,299 | 3 |
| Black Nike running shoe, ₹4,899 | 3 |
| Nike running shoe, blue, ₹4,000 | 1 |
| Black Adidas running shoe, ₹4,500 | 1 |
| Black Nike casual sneaker, ₹4,000 | 0 |

The exact labels must be based on the defined relevance guidelines rather than arbitrary intuition.

---

# 6. Relevance Guidelines

Annotators should consider:

### Hard requirements

Examples:

```text
brand
category
price ceiling
availability
```

Violation of an explicit hard requirement can make a product non-relevant.

### Soft relevance

Examples:

```text
semantic similarity
style similarity
attribute compatibility
use-case similarity
```

These determine the degree of relevance when hard requirements are satisfied.

---

# 7. Evaluation Query Categories

The evaluation set should not consist only of simple queries.

We will create categories such as:

### Category A — Exact queries

```text
"Nike Pegasus 41"
```

Tests lexical retrieval.

---

### Category B — Semantic queries

```text
"comfortable shoes for daily jogging"
```

Tests semantic retrieval.

---

### Category C — Attribute queries

```text
"black running shoes"
```

Tests attribute understanding.

---

### Category D — Multi-constraint queries

```text
"black Nike running shoes under 5000"
```

Tests the complete query pipeline.

---

### Category E — Paraphrased queries

```text
"athletic footwear for jogging"
```

Tests semantic robustness.

---

### Category F — Brand queries

```text
"Nike running shoes"
```

Tests brand handling.

---

### Category G — Price queries

```text
"running shoes below 3000"
```

Tests numeric constraint extraction.

---

### Category H — Ambiguous queries

```text
"black sneakers"
```

Tests behavior when the query contains fewer constraints.

---

### Category I — Difficult queries

Examples:

```text
misspellings
mixed terminology
long queries
multiple constraints
unusual wording
```

---

# 8. Train / Validation / Test Separation

As the system becomes more sophisticated, evaluation data should be separated where appropriate.

Conceptually:

```text id="r46r4a"
Dataset
   │
   ├── Development
   ├── Validation
   └── Test
```

The test set should remain stable and should not be repeatedly tuned against.

This prevents overfitting to the evaluation benchmark.

---

# 9. Baseline Systems

Before introducing sophisticated ranking, ProductIQ must establish baselines.

We will compare:

```text id="f3j0yw"
Baseline 1
BM25 only

Baseline 2
Vector Search only

Baseline 3
Hybrid Retrieval

Baseline 4
Hybrid + Hard Filters

Baseline 5
Hybrid + Ranking
```

This allows us to answer:

> Which architectural component actually improves search quality?

---

# 10. Retrieval Evaluation

Retrieval asks:

> **Did we retrieve the relevant products at all?**

This is different from asking whether they were ranked first.

The primary retrieval metric will be:

> **Recall@K**

---

# 11. Recall@K

Recall@K measures how many relevant products were retrieved within the first K retrieved candidates.

Conceptually:

```text id="1crf0v"
Recall@K =
Relevant products retrieved in top K
-----------------------------------
Total relevant products
```

Example:

Suppose:

```text
10 relevant products exist
```

and:

```text
8 appear in the top 100 retrieved candidates
```

Then:

```text
Recall@100 = 0.8
```

or:

```text
80%
```

---

# 12. Why Retrieval Recall Matters

Suppose the correct product never enters the candidate pool.

The ranking model cannot recover it.

Therefore:

```text id="x5v19k"
Not retrieved
     ↓
Cannot be ranked
     ↓
Cannot appear in final results
```

This gives us a fundamental rule:

> **Ranking cannot fix retrieval failure.**

---

# 13. Precision@K

Precision@K measures the proportion of returned results that are relevant.

Conceptually:

```text id="atv4fb"
Precision@K =
Relevant results in top K
-------------------------
K
```

Example:

If 8 of the top 10 results are relevant:

```text
Precision@10 = 0.8
```

---

# 14. Recall vs Precision

They answer different questions.

### Recall

> Did we find the relevant products?

### Precision

> Are the products we returned actually relevant?

For ProductIQ:

```text id="z0x5x7"
Retrieval → prioritize high recall

Final ranking → prioritize high precision/relevance
```

---

# 15. Mean Reciprocal Rank — MRR

MRR measures how early the first relevant result appears.

For one query:

```text id="t2k9w4"
First relevant result at rank 1

RR = 1/1 = 1
```

If the first relevant result is at rank 5:

```text
RR = 1/5 = 0.2
```

MRR is the mean reciprocal rank across queries.

This is useful for search because users care about how quickly they encounter a relevant product.

---

# 16. NDCG

NDCG is particularly useful for ProductIQ because we use graded relevance.

Remember:

```text
0 → not relevant
1 → slightly relevant
2 → relevant
3 → highly relevant
```

NDCG evaluates whether highly relevant products appear higher in the ranking.

Conceptually:

```text id="m7tw8k"
Highly relevant product at rank 1
        ↓
Good ranking

Highly relevant product at rank 20
        ↓
Poorer ranking
```

NDCG therefore captures ranking quality better than simple binary relevance metrics.

---

# 17. Metric Responsibilities

| Metric | Primary Purpose |
|---|---|
| Recall@K | Retrieval coverage |
| Precision@K | Result relevance |
| MRR | Position of first relevant result |
| NDCG@K | Quality of ranked ordering |

We should report multiple metrics rather than relying on one number.

---

# 18. Retrieval Experiment

First we compare:

```text id="4b3xg5"
BM25
vs
Vector Search
```

Questions:

- Which retrieves more relevant products?
- Which handles exact terms better?
- Which handles paraphrases better?
- Where does each fail?

---

# 19. Hybrid Experiment

Next:

```text id="1ozz3b"
BM25
+
Vector
=
Hybrid Retrieval
```

We compare hybrid retrieval against the individual baselines.

The goal is not to assume hybrid is better.

The goal is to **measure whether combining them improves retrieval coverage**.

---

# 20. Filtering Experiment

Next:

```text id="p9lqkr"
Hybrid Retrieval
        ↓
Hard Filters
```

We evaluate whether explicit constraints are correctly enforced.

Example:

```text id="m19x4d"
Query:
Nike running shoes under ₹5000
```

The evaluation checks whether returned results violate:

```text price <= 5000
brand = Nike
category = running shoes
```

---

# 21. Ranking Experiment

After candidate generation:

```text id="prk0cu"
Candidate Pool
      ↓
Baseline Ordering
      ↓
Ranking Model
```

Compare:

```text id="byczd3"
Baseline ranking
vs
Weighted ranking
vs
Learning-to-rank
```

Only introduce more sophisticated ranking if evaluation demonstrates improvement.

---

# 22. Ablation Testing

ProductIQ should use ablation experiments to understand component contribution.

Example:

```text id="t9svb0"
Full system
    ↓
Remove BM25
    ↓
Measure performance
```

Then:

```text id="n0b1gz"
Full system
    ↓
Remove vector retrieval
    ↓
Measure performance
```

Then:

```text id="z8onm4"
Full system
    ↓
Remove ranking
    ↓
Measure performance
```

This answers:

> What does each component actually contribute?

---

# 23. Query-Type Analysis

Aggregate metrics are not enough.

We should break performance down by query type.

Example:

| Query Type | Recall@100 | NDCG@20 |
|---|---:|---:|
| Exact | — | — |
| Semantic | — | — |
| Brand | — | — |
| Price | — | — |
| Multi-constraint | — | — |
| Ambiguous | — | — |
| Difficult | — | — |

The values will be populated after implementation and evaluation.

---

# 24. Error Analysis

Metrics tell us **that** something is wrong.

Error analysis helps us understand **why**.

Each failed query should be classified.

Possible categories:

```text id="uwm4g5"
Query Understanding Failure
Retrieval Failure
Filtering Failure
Ranking Failure
Data Quality Failure
Embedding Failure
Lexical Matching Failure
Semantic Matching Failure
```

---

# 25. Example Error Analysis

Query:

> "black Nike running shoes under 5000"

Returned:

> Nike black casual sneaker ₹3,999

Potential classification:

```text id="0eowdc"
Category mismatch
```

If the query parser failed to extract:

```text
category = running shoes
```

then:

```text
Query Understanding Failure
```

If the query was understood correctly but retrieval missed the relevant running products:

```text
Retrieval Failure
```

If the correct products were retrieved but ranked below irrelevant products:

```text
Ranking Failure
```

This distinction is essential.

---

# 26. Search Quality Regression

Whenever the search system changes, the evaluation suite should be rerun.

Example:

```text id="z7o6v1"
Version 1
NDCG@20 = X

Version 2
NDCG@20 = Y
```

We then determine whether the change improved or degraded performance.

No model change should be considered successful merely because it works on a few manually inspected examples.

---

# 27. Evaluation Experiment Record

Each experiment should record:

```text id="f2xj7p"
Experiment ID
Date
Dataset version
Model version
Embedding model
Retrieval configuration
Ranking configuration
Metrics
Results
Observations
Decision
```

Example:

```text id="8t9zpq"
Experiment:
EXP-007

Change:
Added hybrid retrieval

Baseline:
Vector-only

Metrics:
Recall@100
NDCG@20

Result:
...

Decision:
...
```

---

# 28. Evaluation Dataset Versioning

The evaluation dataset must be versioned.

Example:

```text id="xq7p5s"
evaluation_v1
evaluation_v2
evaluation_v3
```

A metric without knowing the dataset version is difficult to interpret.

---

# 29. Recommendation Evaluation

Recommendation will initially be evaluated separately from search.

For similar-product recommendations we can eventually evaluate:

- Precision@K
- Recall@K
- NDCG@K

For personalized recommendation, future evaluation may also include behavioral metrics.

The recommendation benchmark should not be mixed blindly with the search benchmark.

---

# 30. Offline vs Online Evaluation

## Offline evaluation

Used during development.

Examples:

```text id="1whw5v"
Recall@K
Precision@K
MRR
NDCG
Latency
```

Advantages:

- Reproducible
- Fast
- Controlled
- Suitable for experimentation

---

## Online evaluation

Future production evaluation may use:

```text id="d2h1wr"
Click-through rate
Add-to-cart rate
Conversion rate
Search abandonment
Zero-result rate
```

These are behavioral signals rather than pure relevance judgments.

Online metrics will be introduced only after the system has real users/traffic.

---

# 31. Grounding Evaluation

Because ProductIQ is designed around catalog-grounded search, we should also verify:

```text id="h5q7uj"
Returned product
      ↓
Exists in catalog?
      ↓
Yes / No
```

Every returned product should resolve to a canonical product record.

We should also verify that displayed:

- Price
- Brand
- Category
- Availability

match the canonical catalog record.

---

# 32. Evaluation Pipeline

The evaluation system will eventually look like:

```text id="87c9sm"
Evaluation Queries
       │
       ▼
ProductIQ Search
       │
       ▼
Retrieved Results
       │
       ▼
Ground-Truth Relevance
       │
       ▼
Metric Calculation
       │
       ├── Recall@K
       ├── Precision@K
       ├── MRR
       └── NDCG@K
              │
              ▼
         Error Analysis
              │
              ▼
       Engineering Decision
```

---

# 33. Initial Evaluation Milestone

Before implementing an advanced ranking model, ProductIQ should be able to compare:

```text id="4r4vpb"
BM25
Vector
Hybrid
Hybrid + Hard Filters
```

and report:

```text
Recall@K
Precision@K
MRR
NDCG@K
```

This becomes the first major search-quality milestone.

---

# 34. Evaluation Principles

### Principle 1

Never optimize against one metric blindly.

### Principle 2

Retrieval should prioritize candidate coverage.

### Principle 3

Ranking should prioritize ordering quality.

### Principle 4

Hard constraints should be evaluated explicitly.

### Principle 5

Metrics should be segmented by query type.

### Principle 6

Every major model/search change should be benchmarked.

### Principle 7

Error analysis should accompany aggregate metrics.

### Principle 8

The test set should remain protected from excessive tuning.

### Principle 9

Evaluation datasets must be versioned.

### Principle 10

Search quality and system latency should be evaluated together.

---

# 35. Initial Evaluation Targets

We will **not invent arbitrary performance targets before seeing the dataset and baseline**.

Instead:

1. Build the dataset.
2. Establish baselines.
3. Measure performance.
4. Identify weaknesses.
5. Set improvement targets.
6. Iterate.

This prevents meaningless targets such as:

> "NDCG must be 0.95"

without understanding the difficulty of the benchmark.

---

# 36. Definition of Evaluation Success

A search-system change is considered successful when:

1. It improves one or more relevant metrics.
2. It does not create unacceptable regressions elsewhere.
3. The improvement is reproducible.
4. Error analysis provides a plausible explanation.
5. The added complexity is justified by the measured benefit.

---

# 37. Status

| Evaluation Component | Status |
|---|---|
| Evaluation philosophy | ✅ Frozen |
| Evaluation dataset structure | ✅ Frozen |
| Relevance labels | ✅ Frozen |
| Query categories | ✅ Frozen |
| Baselines | ✅ Frozen |
| Recall@K | ✅ Frozen |
| Precision@K | ✅ Frozen |
| MRR | ✅ Frozen |
| NDCG | ✅ Frozen |
| Ablation testing | ✅ Frozen |
| Error analysis | ✅ Frozen |
| Dataset versioning | ✅ Frozen |
| Regression testing | ✅ Frozen |
| Grounding evaluation | ✅ Frozen |
| Online evaluation | 🟡 Future |
| Exact performance targets | 🔬 Deferred until baseline |

**Evaluation Strategy v1.0 is now frozen.**