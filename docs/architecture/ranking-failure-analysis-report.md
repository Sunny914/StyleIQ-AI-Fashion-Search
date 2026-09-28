# Ranking Failure Analysis Report (Phase 10.9)

**Artifact filename:** `resources/evaluation/ranking_failure_analysis_v10_9.json` (when written by tooling)  
**Analysis version:** 10.9.0  
**Benchmark:** `productiq_lexical_retrieval_v1` (10 queries, 44 judged relevant IDs)

This document describes the **report schema** and representative failure patterns. It does not claim LTR superiority or expanded labels.

## Record template

| Field | Meaning |
|-------|---------|
| **Failure category** | `RankingFailureCategory` enum value |
| **Observed behavior** | `observed_facts` (artifact-derived) |
| **Affected stage** | retrieval, filtering, baseline_ranking, evaluation_top_k, ltr_inference, … |
| **Evidence** | Structured key/value context (IDs, counts, metrics) |
| **Diagnosis / hypothesis** | `diagnosis_hypotheses` — interpretive, not proven causality |
| **Mitigation** | Suggested engineering follow-up (non-prescriptive) |
| **Remaining limitation** | Benchmark / pipeline constraints |

## Categories observed on the lexical benchmark (via 10.6 diagnostics)

### RELEVANT_NOT_IN_CANDIDATE_POOL

| | |
|--|--|
| **Observed** | Judged relevant product IDs absent from filtered candidate pool |
| **Affected stage** | retrieval / candidate_pool |
| **Evidence** | `relevant_missing_from_pool_product_ids`, `candidate_coverage` |
| **Hypothesis** | Product not retrieved or removed by hard filtering |
| **Mitigation** | Review retrieval depth, RRF pool, and catalog constraints |
| **Limitation** | Incomplete judged set; unjudged catalog items may also be relevant |

### RELEVANT_RETRIEVED_BUT_RANKED_LOW

| | |
|--|--|
| **Observed** | Relevant ID in pool but outside evaluated ranked top-k |
| **Affected stage** | baseline_ranking (10.4) |
| **Evidence** | `baseline_first_relevant_rank`, MRR |
| **Hypothesis** | Fixed baseline weights rank judged items below evaluation depth |
| **Mitigation** | Inspect normalized features and baseline score breakdown per query |
| **Limitation** | No weight tuning in Phase 10 |

### EMPTY_CANDIDATE_POOL

| | |
|--|--|
| **Observed** | Zero candidates enter ranking |
| **Affected stage** | retrieval / filtering |
| **Hypothesis** | Query intent unusable or filters remove all candidates |
| **Mitigation** | Validate query representation and constraint activity |

### EVALUATION_DEPTH_LIMITED

| | |
|--|--|
| **Observed** | Pool larger than metric truncation effects |
| **Affected stage** | evaluation_top_k |
| **Hypothesis** | Metrics computed on truncated ranked lists |
| **Limitation** | `evaluation_top_k` caps observable ranking depth |

### LTR_ARTIFACT_INCOMPATIBLE (offline)

| | |
|--|--|
| **Observed** | `RankingError` from compatibility validation |
| **Affected stage** | ltr_inference |
| **Hypothesis** | Artifact schema/order/policy mismatch |
| **Mitigation** | Reload compatible 10.7 artifact; production stays on 10.4 baseline |

## Production boundary

Ranking failure analysis informs offline review. **Production `retrieve_ranked()` continues to use the 10.4 baseline** regardless of LTR artifact presence.
