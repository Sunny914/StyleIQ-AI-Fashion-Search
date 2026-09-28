# ProductIQ — Phase 4.2 Search & Retrieval Contract

**Status:** Implemented (contract only)  
**Depends on:** Phase 3.8 `QueryRepresentation`  
**Does not implement:** BM25, vector search, hybrid fusion, ranking, filtering execution

---

## 1. Purpose

Phase 4.2 defines the engineering boundary between **query representation** (Phase 3) and **future retrieval engines** (later Phase 4 steps).

Retrieval answers:

> Given an already-understood `QueryRepresentation`, which `product_id` values are plausible candidates, and what score/provenance does each retrieval mechanism assign?

Retrieval does **not** parse natural language, generate embeddings, access PostgreSQL for search, rank final results, or fuse scores across methods.

---

## 2. Pipeline position

```text
Canonical catalog
        ↓
Product representations (Phase 3)
        ↓
QueryRepresentation (Phase 3.8)
        ↓
RetrievalRequest → Retriever → RetrievalResponse   ← Phase 4.2
        ↓
(filtering execution — timing TBD)
        ↓
Ranking (later)
        ↓
Serving (later)
```

Mental model: **UNDERSTAND → RETRIEVE → FILTER → RANK → SERVE**

Phase 4.2 covers **RETRIEVE** contracts only.

---

## 3. Retrieval boundary

| In scope | Out of scope |
|----------|----------------|
| Typed request/response | Raw query parsing |
| `product_id` candidates | URL/row/index identity |
| Per-method native scores | Score normalization / RRF |
| Provenance (`RetrievalMethod`) | Product attribute payloads |
| `top_k` candidate limit | Final UI result count |
| `Retriever` protocol | Registries, DI containers |

Query constraints remain on `QueryRepresentation`; Phase 4.2 does **not** duplicate filter models or decide pre/during/post retrieval filtering.

---

## 4. `RetrievalRequest`

| Field | Requirement |
|-------|-------------|
| `query` | Required `QueryRepresentation` (Phase 3) |
| `top_k` | Positive integer; number of **retrieval** candidates requested |

Example: `top_k=200` may shrink after hard filtering and again after ranking before serving ~20 products.

Validation is deterministic Pydantic validation; invalid `top_k` (0, negative) is rejected.

---

## 5. `RetrievalCandidate`

| Field | Requirement |
|-------|-------------|
| `product_id` | Required, non-empty; **canonical identity** |
| `score` | Finite float in the retrieval method’s native scale |
| `method` | `RetrievalMethod`: `bm25`, `vector`, or `hybrid` |
| `metadata` | Optional retrieval execution metadata only |

Examples:

```text
product_id=P123  score=14.82  method=bm25
product_id=P123  score=0.87   method=vector
```

**Score rule:** BM25 and vector scores are **not comparable**. Do not infer relevance ordering across methods in this layer. Fusion belongs to later hybrid work.

---

## 6. `RetrievalResponse`

| Field | Requirement |
|-------|-------------|
| `candidates` | Ordered tuple; order preserved as returned by the engine |
| `metadata` | Optional `RetrievalResponseMetadata` (e.g. `requested_top_k`) |
| `candidate_count` | Computed count of candidates |

Not a user-facing ranked result list. No automatic deduplication or reordering in the contract.

---

## 7. `Retriever` protocol

```python
def retrieve(self, request: RetrievalRequest) -> RetrievalResponse: ...
```

Future implementations: `BM25Retriever`, `VectorRetriever`, `HybridRetriever` (not in Phase 4.2).

---

## 8. Module layout

```text
src/productiq/retrieval/
├── __init__.py               # public exports
├── contracts.py              # Phase 4.2 models + Retriever protocol
├── query_for_retrieval.py    # Phase 4.3 retrieval query projection
├── lexical.py                # Phase 4.4 tokenization + inverted index
├── bm25.py                   # Phase 4.5 BM25 scoring
├── index_builder.py          # Phase 4.6 dataset → persisted index
├── index_schema.py           # Phase 4.6 artifact constants
├── bm25_retriever.py         # Phase 4.7 BM25 Retriever
├── evaluation/               # Phase 4.8 lexical retrieval evaluation
│   └── ...
├── semantic.py               # Phase 4.9 semantic retrieval foundations
└── exceptions.py             # RetrievalError alias
```

Serialization helpers: `retrieval_request_to_dict`, `retrieval_response_to_dict`.

---

## 9. Testing

`tests/retrieval/test_retrieval_contract.py` — validation, immutability, ordering, stub `Retriever`, and boundary checks (no engines, no fusion).

---

## 10. Future work (not Phase 4.2)

- BM25 index + `BM25Retriever`
- Embedding index + `VectorRetriever`
- Candidate union / hybrid orchestration
- Reciprocal rank fusion and score normalization
- Retrieval evaluation (Recall@K, etc.)
- Integration with materialized `product_representations.parquet`

---

## 11. Related documents

- Phase 3 query contract: `product-representation.md` (Part G)
- High-level candidate narrative: `interfaces.md` §13–16
- Phase 3 closure: `final-architecture-review.md` §53

---

# Phase 4.3 — Query Representation for Retrieval

**Status:** Implemented (semantics + projection; no new query model)  
**Reuses:** Phase 3.8 `QueryRepresentation` unchanged  
**Does not implement:** Query parsing, BM25, embeddings, vector search, filtering execution

## 12.1 Purpose

Phase 4.3 makes **retrieval-facing responsibilities** of the existing query contract explicit. Future retrievers consume understood queries through three parallel inputs:

| Query field | Retrieval role | Product-side alignment |
|-------------|----------------|----------------------|
| `lexical_intent.text` | Future lexical / BM25 input | `lexical_text` |
| `semantic_intent.text` | Future embedding / vector input | `semantic_text` |
| `constraints` | Structured hard-filter semantics | `FilteringRepresentation` facets |

Raw natural-language parsing belongs to **query understanding** (upstream). Retrievers must not re-parse user text.

## 12.2 Why separate lexical and semantic intent

Lexical retrieval rewards term overlap on plain search-oriented text. Semantic retrieval rewards meaning on labeled, embedding-friendly text. Merging them would blur indexing contracts and prevent independent iteration (same principle as product-side lexical vs semantic separation in Phase 3).

## 12.3 Why constraints stay separate

Price caps, brand, gender, and facet lists are **structured filters**, not BM25 terms or embedding prose. They align field-for-field with product `FilteringRepresentation` via Phase 3.8 `QueryFilterConstraints`. Phase 4.3 does **not** execute filters or choose pre/during/post retrieval timing.

## 12.4 `RetrievalQueryView`

`build_retrieval_query_view(query)` projects a frozen `RetrievalQueryView`:

- `lexical_retrieval_text` ← `query.lexical_intent.text`
- `semantic_retrieval_text` ← `query.semantic_intent.text`
- `constraints` ← `query.constraints` (unchanged reference equality)
- `query_text` ← normalized audit trail (not for retriever parsing)

No mutation of `QueryRepresentation`. Normalization rules remain those established in Phase 3.8 (`build_query_representation` / `normalize_query_text`).

## 12.5 Pipeline

```text
Raw user query
      ↓
Query understanding → QueryRepresentation (Phase 3.8)
      ↓
build_retrieval_query_view → RetrievalQueryView (Phase 4.3)
      ↓
┌──────────────┬──────────────┬──────────────┐
│ lexical text │ semantic text│ constraints  │
└──────┬───────┴──────┬───────┴──────┬───────┘
       ↓              ↓              ↓
   (future BM25) (future embed) (future filter)
       ↓              ↓              ↓
RetrievalRequest.query still carries full QueryRepresentation (Phase 4.2)
```

## 12.6 Testing

`tests/retrieval/test_query_for_retrieval.py` — alignment constants, normalization preservation, immutability, determinism, and boundary checks.

## 12.7 Not in scope

BM25, inverted indexes, embedding models, pgvector/FAISS, hybrid fusion, ranking, LLM parsing, spell correction, synonym expansion.

---

# Phase 4.4 — Lexical Retrieval Foundations

**Status:** Implemented (index mechanics only)  
**Depends on:** Phase 3 `lexical_text`, Phase 4.3 `lexical_retrieval_text`  
**Does not implement:** BM25, TF-IDF, IDF scoring, embeddings, vector search, ranking

## 13.1 What lexical retrieval is

Lexical retrieval matches **terms** from product `lexical_text` against terms from query `lexical_retrieval_text`. Phase 4.4 implements tokenization, inverted indexes, posting lists, and raw term statistics that Phase 4.5 BM25 will score.

## 13.2 Tokenization

`tokenize_lexical_text` collapses whitespace (Phase 3–consistent), lowercases with `casefold`, and extracts alphanumeric tokens. No stemming, synonyms, spell correction, or entity extraction.

## 13.3 Inverted index and posting lists

Each index term maps to sorted posting lists of `{product_id, term_frequency}`. Document identity is **`product_id` only**.

## 13.4 Statistics

| Statistic | Meaning |
|-----------|---------|
| TF(term, doc) | Count of term tokens in the document |
| DF(term) | Documents containing the term |
| document_length | Token count in the document |
| total_document_count | Indexed documents |

Statistics are exposed raw; no BM25/TF-IDF/IDF **scoring** in Phase 4.4.

## 13.5 Candidate retrieval vs scoring

`retrieve_lexical_candidates` unions product IDs from all query-term postings and sorts IDs ascending (deterministic, **not relevance ranking**).

```text
Product lexical_text
        ↓
Tokenization
        ↓
Inverted Index → Posting Lists → Candidate product_ids
                                        ↓
                                 Phase 4.5 BM25

Query lexical_retrieval_text
        ↓
Tokenization
        ↓
Index lookup → Candidate product_ids
```

## 13.6 Module

`src/productiq/retrieval/lexical.py` — `build_inverted_lexical_index`, `retrieve_lexical_candidates`, `retrieve_lexical_candidates_from_view`.

## 13.7 Testing

`tests/retrieval/test_lexical_foundations.py`

---

# Phase 4.5 — BM25 Scoring

**Status:** Implemented  
**Builds on:** Phase 4.4 `InvertedLexicalIndex`, Phase 4.3 `lexical_retrieval_text`  
**Does not implement:** TF-IDF ranking as product, embeddings, vector/hybrid retrieval, learning-to-rank

## 14.1 Why BM25

Phase 4.4 answers which documents **contain** query terms. BM25 answers how **relevant** each candidate document is using TF saturation, IDF, and length normalization.

## 14.2 Formula

For query terms \(q_i\), document \(D\), corpus size \(N\), document frequency `df`, term frequency `TF`, document length \(|D|\), average length `avgdl`, and parameters `k1`, `b`:

\[
\text{Score}(D,Q) = \sum_i \text{IDF}(q_i) \cdot \frac{TF(q_i,D)\,(k_1+1)}{TF(q_i,D) + k_1\left(1 - b + b\,\frac{|D|}{\text{avgdl}}\right)}
\]

\[
\text{IDF}(q_i) = \ln\left(1 + \frac{N - df(q_i) + 0.5}{df(q_i) + 0.5}\right)
\]

Default starting parameters: **k1 = 1.5**, **b = 0.75** (`BM25Config`).

## 14.3 Module API

`src/productiq/retrieval/bm25.py`:

- `BM25Scorer`, `BM25CorpusStatistics`, `BM25ScoredCandidate`
- `score_bm25_lexical_query`, `score_bm25_from_view`, `score_bm25_from_retrieval_request`
- Ranking: score descending, `product_id` ascending tie-break; optional `top_k`

Duplicate query tokens are deduplicated (first-seen order). Unknown terms use `df = 0` in IDF. Empty corpus yields zero scores without division by zero.

## 14.4 Testing

`tests/retrieval/test_bm25.py`

---

# Phase 4.6 — BM25 Lexical Index Construction

**Status:** Implemented  
**Source:** `resources/processed/product_representations.parquet` (`product_id`, `lexical_text` only)  
**Output:** `bm25_lexical_index.pkl` + `bm25_lexical_index.manifest.json`

## 15.1 Role

Phase 4.6 turns the approved Phase 3 representation artifact into a **persisted inverted lexical index** loadable by `BM25Scorer`. The Parquet dataset remains source of truth; the index is derived infrastructure.

## 15.2 Construction

- Batch-read representation Parquet (default batch size 10,000)
- Validate unique non-empty `product_id`, required columns
- Sort rows by `product_id` for deterministic `document_ids`
- Products with empty `lexical_text` are **retained** with `document_length = 0`
- No deduplication by identical lexical text
- `assemble_inverted_lexical_index` (Phase 4.4) builds postings

## 15.3 Artifact format

Pickle envelope (schema version **1.0.0**) containing JSON-serializable fields: `document_ids`, `document_lengths`, `postings_by_term` with integer TF. SHA-256 checksum in manifest (`checksum_algorithm` from Phase 2/3 export convention).

## 15.4 Manifest

Records source representation checksum/schema version, index statistics, tokenizer id (`tokenize_lexical_text/v1`), BM25 `k1`/`b`, build duration.

## 15.5 APIs

- `build_bm25_lexical_index_from_representation_dataset`
- `load_inverted_lexical_index` / `load_bm25_lexical_index_manifest`
- Atomic publish (temp files + replace, rollback on failure)

## 15.6 Testing

`tests/retrieval/test_index_builder.py`

---

# Phase 4.7 — BM25 Candidate Retrieval

**Status:** Implemented  
**Implements:** Phase 4.2 `Retriever` via `BM25Retriever`  
**Does not implement:** Filtering, vector/hybrid retrieval, reranking

## 16.1 Role

`BM25Retriever` connects `RetrievalRequest` → `RetrievalQueryView` → posting-list candidate union → `BM25Scorer` → `RetrievalCandidate` (`method=bm25`) → `RetrievalResponse` with `top_k` from the request.

## 16.2 Candidate generation vs scoring

Posting lists provide the **candidate product_id set** (union of query terms). BM25 scores only those IDs—no full-corpus scan of 367k documents per query.

## 16.3 Boundaries

- Uses **`lexical_retrieval_text` only** (not semantic intent).
- **No structured filter execution** inside the retriever (`QueryFilterConstraints` deferred to later stages).
- BM25 score is **lexical retrieval evidence**, not final ranked UI score.

## 16.4 APIs

- `BM25Retriever`, `create_bm25_retriever`, `create_bm25_retriever_from_index_path`
- Module: `src/productiq/retrieval/bm25_retriever.py`

## 16.5 Testing

`tests/retrieval/test_bm25_retriever.py` (in-memory indexes; optional persisted smoke via `PRODUCTIQ_BM25_RETRIEVER_SMOKE=1`)

---

# Phase 4.8 — Lexical Retrieval Evaluation

**Status:** Implemented  
**Implements:** Reusable retrieval **quality** evaluation (not software correctness alone)  
**Does not implement:** Vector/hybrid evaluation runners, LLM-as-judge, graded relevance (extensible later)

## 17.1 Why evaluation is separate from unit tests

Unit tests verify contracts, edge cases, and deterministic behavior of retrieval **code**. Phase 4.8 measures whether a `Retriever` returns **judged-relevant** products for realistic queries using manually curated ground truth.

## 17.2 Ground truth and limitations

Benchmark: `resources/evaluation/lexical_retrieval_benchmark_v1.json`

- **Binary relevance:** each query has a set of `relevant_product_ids` (not exhaustive over ~367k catalog rows).
- Judgments are **manual and inspectable**, not derived from BM25 output (no circular labels).
- **Incomplete judgments:** many other products may be relevant; recall is a lower bound, not oracle recall.

## 17.3 Metric contracts

Generic functions in `evaluation/metrics.py` (no BM25 imports):

| Metric | Definition |
|--------|------------|
| **Precision@K** | (# relevant in first K) / `min(K, len(retrieved))`; 0 if nothing retrieved |
| **Recall@K** | (# relevant in first K) / (# judged relevant); **`None`** if judged set empty |
| **MRR (per query)** | `1 / rank` of first relevant hit (1-based); **0** if none |
| **Aggregation** | **Macro** mean across benchmark queries; recall macro excludes queries with empty ground truth |

`K` values default to `(1, 5, 10, 20, 50)`. Evaluator `retrieval_top_k` controls how many IDs are fetched from the retriever (default 50). Per-query metrics at each configured `K` use `effective_k = min(K, retrieval_top_k)` because retrieval cannot rank beyond the fetched depth; with default settings all configured `K` values equal `retrieval_top_k` (50).

## 17.4 Evaluator

`LexicalRetrievalEvaluator` accepts any Phase 4.2 **`Retriever`** (BM25, future vector/hybrid) plus a `LexicalRetrievalBenchmark`. Outputs per-query metrics (failure analysis) and aggregate macro metrics.

## 17.5 APIs

- `load_lexical_retrieval_benchmark`, `LexicalRetrievalBenchmark`
- `precision_at_k`, `recall_at_k`, `reciprocal_rank`, `LexicalRetrievalEvaluator`

## 17.6 Testing

- `tests/retrieval/test_evaluation_metrics.py`
- `tests/retrieval/test_evaluation_evaluator.py`
- Optional BM25-on-benchmark smoke: `PRODUCTIQ_LEXICAL_EVAL_SMOKE=1`

## 17.7 Notebook

`notebooks/data_engineering/26_lexical_retrieval_evaluation.ipynb`

---

# Phase 4.9 — Semantic Retrieval Foundations

**Status:** Implemented (contracts and math only)  
**Does not implement:** Embedding models, embedding generation, vector indexes, similarity search execution, semantic retriever, hybrid fusion

## 18.1 Definition

Semantic retrieval finds candidate products using **vector similarity** over representations intended to capture meaning. Phase 4.9 establishes types and boundaries only; execution arrives in Phases 4.10–4.13.

## 18.2 Representation alignment

| Side | Field |
|------|--------|
| Product | `semantic_text` (`ProductRepresentationBundle.semantic`) |
| Query | `semantic_intent` (`QueryRepresentation.semantic_intent`) |

Phase 4.3 `RetrievalQueryView.semantic_retrieval_text` projects `semantic_intent.text`. Semantic retrieval must **not** rebuild text from raw catalog columns or parse NL in this layer.

## 18.3 Semantic vector and similarity

- `SemanticVector` — immutable finite numeric vector, `dimension = len(values)`.
- `cosine_similarity` — deterministic symmetric cosine; rejects empty vectors, dimension mismatch, non-finite values, and **zero-norm** vectors (`SemanticRetrievalError`).
- `SemanticRetrievalConfig` — `similarity_metric=cosine` only (no model or vector DB settings).

## 18.4 Candidates and retriever boundary

Reuse Phase 4.2 `RetrievalRequest`, `RetrievalCandidate` (`method=vector`), and `Retriever`. Semantic **similarity score** is not BM25 score and not final UI rank.

Future pipeline:

```text
semantic_intent → embedding model → query vector → VectorIndex.search → SemanticSearchHit → RetrievalResponse
```

`VectorIndex` protocol: `search(query_vector, top_k) -> SemanticSearchHit` (no storage in 4.9).

## 18.5 Separation

Semantic retrieval is independent of lexical BM25, structured filtering execution, final ranking, and recommendation.

## 18.6 Testing

`tests/retrieval/test_semantic_foundations.py`

## 18.7 Notebook

`notebooks/data_engineering/27_semantic_retrieval_foundations.ipynb`

---

# Phase 4.10 — Embedding Model Selection

**Status:** Decision frozen in artifact; **no** embedding generation or vector indexes  
**Artifact:** `resources/embedding/productiq_embedding_model_selection_v1.json`  
**Documentation:** `docs/architecture/embedding-model-selection.md`

**Primary model:** `BAAI/bge-small-en-v1.5` (384-d, cosine, L2-normalize, query instruction prefix)  
**Fallback:** `intfloat/e5-small-v2` (384-d, `query:` / `passage:` prefixes)

Loader: `load_productiq_embedding_model_selection()` in `embedding_selection.py`.

Phase 4.11 implements batch embedding over `semantic_text`; Phase 4.12+ pgvector and semantic retrieval.

---

# Phase 4.11 — Embedding Generation

**Status:** Product/document embedding pipeline over `product_representations.parquet`  
**Artifacts:** `resources/processed/product_embeddings.parquet`, `product_embeddings.manifest.json`  
**Implementation:** `embedding_encoder.py`, `embedding_builder.py`, `embedding_schema.py`

## 19.1 Input and encoding

| Role | Source | Rule |
|------|--------|------|
| **Document (product)** | `semantic_text` column | Raw Phase 3 text — **no** instruction prefix |
| **Query (later retrieval)** | `QueryRepresentation.semantic_intent` | Prefix: `Represent this sentence for searching relevant passages: ` |

**Model:** `BAAI/bge-small-en-v1.5` (local `sentence-transformers`, L2-normalized, **384** dimensions, cosine similarity per Phase 4.9/4.10).

## 19.2 Output schema

Parquet columns: `product_id`, `embedding` (fixed-size `float32` list length 384).

## 19.3 Reproducibility

Manifest records source representation checksum, row counts, model ID + pinned Hugging Face revision, batch size, device, duration, throughput, and embedding artifact checksum. Exact floats may vary by device/library; same pinned revision + environment should be semantically equivalent.

## 19.4 Scope boundary

Generates embeddings only. **No** pgvector tables, vector indexes, or semantic retriever in this phase (Phase 4.12+).

## 19.5 Operations

CLI: `scripts/run_product_embedding_generation.py`

| Workflow | Example |
|----------|---------|
| GPU smoke (small encode) | `python scripts/run_product_embedding_generation.py --gpu-smoke --device cuda --batch-size 32` |
| GPU 1k benchmark | `python scripts/run_product_embedding_generation.py --gpu-benchmark --device cuda --batch-size 32` |
| Validation (1k, checkpointed) | `python scripts/run_product_embedding_generation.py --max-products 1000 --device auto --fresh-run --publish` |
| Full catalog | `python scripts/run_product_embedding_generation.py --device cuda --batch-size 32 --pin-selection-revision` |
| Resume interrupted full run | `python scripts/run_product_embedding_generation.py --device cuda --batch-size 32 --resume` |

**Device:** `--device` accepts `cpu`, `cuda`, or `auto` (prefers CUDA). `--device cuda` fails if CUDA is unavailable unless `--allow-cpu-fallback` is set.

**Checkpoint/resume:** Full runs persist chunked progress under `resources/processed/.embedding_generation/` (`checkpoint.json` + `chunks/chunk_*.parquet`). Resume verifies source checksum, model revision, dimension, batch size, and device before continuing. `--fresh-run` discards checkpoint state.

**CPU reference (1,000 docs, post import-fix):** ~36.9 docs/sec, ~2.8 h estimated full catalog (approximate).

## 19.6 Testing

`tests/retrieval/test_embedding_generation.py`, `test_embedding_checkpoint.py`, `test_import_architecture.py` (optional model smoke: `PRODUCTIQ_EMBEDDING_SMOKE=1`).

## 19.7 Notebook

`notebooks/data_engineering/29_embedding_generation.ipynb`

---

# Phase 4.12 — Vector Index / Similarity Search Infrastructure

**Status:** PostgreSQL 18 + pgvector HNSW cosine index derived from the Phase 4.11 embedding artifact  
**Lineage artifact:** `resources/processed/product_vector_index.manifest.json`  
**Implementation:** `vector_index_loader.py`, `vector_index_builder.py`, `pgvector_search.py`, `database/vector_catalog.py`

## 20.1 Architecture

```
product_embeddings.parquet  →  offline batched load  →  products.embedding vector(384)
                                                      →  HNSW (vector_cosine_ops)
                                                      →  search_products_by_embedding()
```

PostgreSQL remains the system-of-record catalog. The Parquet embedding artifact remains the canonical offline source. Vectors are **updated** on existing `products.product_id` rows (no duplicate catalog). Index builds do **not** invoke the embedding model.

## 20.2 Schema and idempotency

| Item | Value |
|------|--------|
| Column | `products.embedding vector(384)` nullable until loaded |
| Catalog schema version | `1.1.0` (`PRODUCT_VECTOR_CATALOG_SCHEMA_VERSION`) |
| HNSW index | `ix_products_embedding_hnsw_cosine` |
| Distance | Cosine (`vector_cosine_ops`); pgvector distance `=<=>` where **similarity = 1 − distance** for unit-norm vectors |
| HNSW params (initial) | `m=16`, `ef_construction=64` (search-time `hnsw.ef_search` configurable later) |

The search primitive sets `hnsw.ef_search` to at least `top_k` so HNSW returns the requested number of neighbors (PostgreSQL session GUC; not bind-parameterized).

Re-running the loader **overwrites** embeddings by `product_id`. HNSW creation is idempotent (`CREATE INDEX IF NOT EXISTS`); use `--rebuild-hnsw` to drop and recreate.

## 20.3 Vector search primitive (not Phase 4.13 retriever)

`search_products_by_embedding(engine, query_vector, top_k=…)` accepts a **384-d query vector** and returns ordered hits (`product_id`, cosine distance, similarity). It does **not** parse natural language, encode text, apply filters, or fuse with BM25.

Phase 4.13 will map `semantic_intent → query embedding → this primitive → RetrievalResponse`.

## 20.4 Validation before load

Uses `validate_product_embeddings_parquet()` (manifest checksum, model, dimension, normalization, similarity, source representation checksum). Product IDs must exist in `products` before vectors are written.

## 20.5 Operations

CLI: `scripts/run_vector_index_build.py`

| Step | Command |
|------|---------|
| Validate artifact only | `python scripts/run_vector_index_build.py --validate-only` |
| Full index build | `python scripts/run_vector_index_build.py --benchmark-search` |
| Rebuild HNSW only | `python scripts/run_vector_index_build.py --skip-load --rebuild-hnsw` |

Requires PostgreSQL with `CREATE EXTENSION vector` (`ensure_pgvector_extension()`).

## 20.6 Testing

Unit: `tests/retrieval/test_vector_index_contract.py`, `test_vector_index_loader.py`  
Integration (PostgreSQL): set `PRODUCTIQ_RUN_INTEGRATION_TESTS=1`, run `tests/retrieval/test_vector_index_integration.py`

## 20.7 Scope boundary

**In scope:** artifact validation, batched load, HNSW index, primitive vector search, lineage manifest, baseline latency samples.  
**Out of scope:** semantic retriever, hybrid fusion, retrieval evaluation (Phases 4.13–4.14).

---

# Phase 4.13 — Semantic Candidate Retrieval

**Status:** Application-level `SemanticRetriever` implementing the Phase 4.2 `Retriever` protocol  
**Implementation:** `semantic_retriever.py`, `pgvector_vector_index.py` (adapter over Phase 4.12)

## 21.1 Semantic retrieval flow

```
QueryRepresentation.semantic_intent
        ↓
build_retrieval_query_view().semantic_retrieval_text
        ↓
DocumentEmbeddingEncoder.encode_query()  (BGE instruction prefix)
        ↓
384-d L2-normalized SemanticVector
        ↓
VectorIndex.search() → PgVectorProductVectorIndex → search_products_by_embedding()
        ↓
SemanticSearchHit (cosine similarity)
        ↓
RetrievalCandidate(method=VECTOR, score=similarity)
        ↓
RetrievalResponse
```

## 21.2 Score semantics

pgvector returns **cosine distance** (`<=>` with `vector_cosine_ops`). Phase 4.12 converts to **similarity = 1 − distance** before hits reach the retriever. `RetrievalCandidate.score` for `RetrievalMethod.VECTOR` is **cosine similarity** (not BM25, not hybrid, not final rank).

## 21.3 Model lifecycle

Construct `create_bge_small_en_v15_encoder(...)` once at application startup; inject into `create_semantic_retriever_from_engine(engine, encoder)`. The retriever does **not** load the model per request.

## 21.4 Empty semantic intent

Whitespace-only `semantic_intent` returns an empty `RetrievalResponse` with `requested_top_k` metadata (same pattern as empty lexical BM25 queries).

## 21.5 Operations

CLI smoke: `python scripts/run_semantic_retrieval_smoke.py "black running shoes" --top-k 10`

Integration pytest: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1` and `PRODUCTIQ_SEMANTIC_RETRIEVAL_SMOKE=1`

## 21.6 Scope boundary

**In scope:** `RetrievalRequest` → BGE query embedding → pgvector HNSW → `RetrievalResponse` with `method=vector`.

**Out of scope:** filtering, hybrid fusion, ranking, recommendation, semantic evaluation (Phases 4.14+).

---

# Phase 4.14 — Semantic Retrieval Evaluation

**Status:** Implemented  
**Implements:** Transparent semantic retrieval **quality** measurement on the ProductIQ catalog  
**Does not implement:** Hybrid retrieval, score fusion, reranking, LLM-as-judge, Phase 4.15+

## 22.1 Objective

Measure how well **`SemanticRetriever`** (BGE query encoder → pgvector HNSW → cosine similarity) retrieves products judged relevant for representative fashion search queries.

Evaluation uses the same retrieval path as production candidate retrieval (Phase 4.13). It does **not** query pgvector directly and does **not** regenerate product embeddings.

## 22.2 Ground truth

Benchmark: `resources/evaluation/semantic_retrieval_benchmark_v1.json`

- **Binary relevance:** `relevant_product_ids` per query (human-curated, inspectable catalog alignment).
- **Shared judgments with Phase 4.8:** the ten query strings and judged ID sets match `lexical_retrieval_benchmark_v1.json` so BM25 vs semantic aggregate metrics are **descriptively comparable** (not a combined score).
- **Not derived from:** embedding similarity, BM25 output, or LLM labels.

## 22.3 Limitations

**Incomplete judgments:** curated relevant sets are not exhaustive over ~367k products. Precision@K, Recall@K, and MRR are benchmark measurements under these labels only—not oracle metrics for the full catalog.

## 22.4 Metrics

Reuse Phase 4.8 definitions in `evaluation/metrics.py`:

| Metric | Notes |
|--------|--------|
| **Precision@K** | K ∈ {1, 5, 10, 20, 50}; macro mean across queries |
| **Recall@K** | Denominator = judged relevant count; `None` per query if empty ground truth; macro excludes empty-ground-truth queries |
| **MRR** | Mean reciprocal rank of first judged-relevant hit; 0 if none |

`RetrievalCandidate.score` remains **cosine similarity** (ranking signal). Evaluation metrics are separate from similarity scores.

## 22.5 Evaluator

`SemanticRetrievalEvaluator` accepts any Phase 4.2 **`Retriever`** (production: `SemanticRetriever`). It validates judged product IDs exist in `products`, runs `retrieval_top_k=50`, and emits per-query plus aggregate results. Analysis rows (`build_per_query_analysis_rows`) include retrieved IDs and similarity scores for failure analysis (Phase 4.17).

## 22.6 Artifacts

| File | Role |
|------|------|
| `semantic_retrieval_benchmark_v1.json` | Versioned benchmark + lineage (model, embedding checksum, representation checksum) |
| `semantic_retrieval_benchmark_v1_run.json` | Run metadata, aggregate + per-query metrics, optional BM25 comparison block |
| `semantic_retrieval_benchmark_v1_analysis.jsonl` | Per-query diagnosis (ranks, IDs, cosine scores) |

## 22.7 Operations

```bash
python scripts/run_semantic_retrieval_benchmark.py
```

Requires PostgreSQL vector index from Phase 4.12. Loads BGE once; does not rebuild the index or regenerate embeddings.

Integration pytest: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1` and `PRODUCTIQ_SEMANTIC_RETRIEVAL_SMOKE=1` → `tests/retrieval/test_semantic_retrieval_evaluation.py`

## 22.8 Notebook

`notebooks/data_engineering/31_semantic_retrieval_evaluation.ipynb`

## 22.9 Scope boundary

**In scope:** benchmark, catalog ID validation, semantic evaluator, run/analysis artifacts, descriptive BM25 comparison from existing lexical run JSON.

**Out of scope:** hybrid BM25+vector, RRF, reranking, filtering evaluation, recommendation metrics, Phase 4.15.

---

# Phase 4.15 — Hybrid Retrieval

**Status:** Implemented  
**Implements:** Candidate **union** of BM25 and semantic retrieval with deduplication and provenance  
**Does not implement:** Score fusion, RRF, reranking, filtering, Phase 4.16 candidate fusion

## 23.1 Hybrid retrieval flow

```text
QueryRepresentation
        ↓
   ┌────┴────┐
   ▼         ▼
 BM25    SemanticRetriever
   │         │
   ▼         ▼
 lexical   vector
 candidates candidates
   └────┬────┘
        ▼
 candidate union (by product_id)
        ▼
 deduplication + provenance
        ▼
 hybrid candidate pool (RetrievalMethod.HYBRID)
```

`HybridRetriever` composes injected `BM25Retriever` and `SemanticRetriever` instances. It does **not** load BGE, rebuild indexes, or query pgvector/BM25 directly.

## 23.2 Score semantics

| Source | Native field | Meaning |
|--------|----------------|---------|
| BM25 | `bm25_score` | Lexical BM25 score |
| Vector | `vector_score` | Cosine similarity |

BM25 scores and cosine similarity are **not** added, averaged, or normalized together in Phase 4.15. When both native scores exist for one product, `RetrievalCandidate.score` is **0.0** (sentinel: not a fused ranking score).

## 23.3 Provenance

Each hybrid candidate exposes `retrieval_methods`:

- **BM25-only** — lexical retrieval only  
- **VECTOR-only** — semantic retrieval only  
- **Both** — `(bm25, vector)` overlap

`RetrievalResponseMetadata` may include execution counts: `lexical_candidate_count`, `semantic_candidate_count`, `unique_candidate_count`, `overlap_count`.

## 23.4 Retrieval depth and ordering

Both underlying retrievers receive the same `RetrievalRequest.top_k`. The hybrid pool is **not** truncated back to `top_k`; up to **2×top_k** unique IDs before overlap. Candidate order is deterministic: BM25 retrieval order first (merged overlaps), then vector-only IDs in semantic order. This order is **not** final UI ranking.

## 23.5 Failure behavior

If either retriever raises, the hybrid call **propagates** the exception (no silent partial success).

## 23.6 Contract extensions (backward compatible)

`RetrievalCandidate` adds optional `retrieval_methods`, `bm25_score`, and `vector_score`. Single-method retrievers (`BM25Retriever`, `SemanticRetriever`) are unchanged.

## 23.7 Operations

CLI smoke: `python scripts/run_hybrid_retrieval_smoke.py "black Nike running shoes" --top-k 20`

Integration pytest: `PRODUCTIQ_RUN_INTEGRATION_TESTS=1` and `PRODUCTIQ_HYBRID_RETRIEVAL_SMOKE=1`

## 23.8 Notebook

`notebooks/data_engineering/32_hybrid_retrieval.ipynb`

## 23.9 Scope boundary

**In scope:** `HybridRetriever`, union/dedup, native score preservation, provenance metadata.

**Out of scope:** RRF, weighted fusion, reranking, filtering, quality evaluation, **Phase 4.16 candidate fusion**.

---

# Phase 4.16 — Candidate Fusion (RRF)

**Status:** Implemented  
**Implements:** Reciprocal Rank Fusion over BM25 + semantic ranked lists  
**Does not implement:** Raw score fusion, reranking, filtering, Phase 4.17+

## 24.1 Fusion flow

```text
BM25 ranked candidates (top_k)
        +
Semantic ranked candidates (top_k)
        ↓
   RRF by rank
        ↓
 sort fusion_score DESC, product_id ASC
        ↓
 return min(pool, top_k) fused candidates
```

`RRFHybridRetriever` composes injected `BM25Retriever` and `SemanticRetriever`. Phase 4.15 `HybridRetriever` (union without fusion) remains available.

## 24.2 Formula

```text
RRF(d) = Σ 1 / (k + rank_r(d))
```

- **rank:** 1-based position in each retriever’s response order (not re-sorted by native score)  
- **k:** configurable smoothing constant; default **60** (`RRFConfig.rank_constant`)

## 24.3 Score semantics

| Field | Meaning |
|-------|---------|
| `bm25_score` | Native BM25 score (diagnostic) |
| `vector_score` | Native cosine similarity (diagnostic) |
| `fusion_score` / `score` | RRF score only (when fusion applied) |

RRF uses **ranks only**; native score magnitudes do not enter the formula.

## 24.4 Output contract

Fused candidates use `RetrievalMethod.HYBRID` with `retrieval_methods` provenance, optional `bm25_rank` / `vector_rank`, and `fusion_score`. Dual-native union candidates from Phase 4.15 (score=0.0) are unchanged.

## 24.5 Evaluation

Shared 10-query benchmark (same judgments as lexical/semantic v1):

```bash
python scripts/run_rrf_retrieval_benchmark.py
```

Artifact: `resources/evaluation/hybrid_rrf_benchmark_v1_run.json` (BM25 vs semantic vs RRF metrics, per-query ranks).

## 24.6 Notebook

`notebooks/data_engineering/33_candidate_fusion.ipynb`

## 24.7 Scope boundary

**Out of scope:** cross-encoder reranking, LLM reranking, learning-to-rank, filtering, **Phase 4.17**.

---

# Phase 4.17 — Retrieval Failure Analysis

**Status:** Implemented  
**Implements:** Deterministic diagnostics over existing lexical, semantic, and RRF benchmark artifacts  
**Does not implement:** Retrieval optimization, reranking, filtering, **Phase 4.18+**

See **`docs/architecture/retrieval-failure-analysis.md`** for schema, artifacts, and limitations.

```bash
python scripts/run_retrieval_failure_analysis.py
```

**Out of scope:** re-embedding, index rebuilds, live full-catalog RRF re-evaluation, **Phase 4.18**.

---

# Phase 4.18 — Unified Retrieval Evaluation Framework

**Status:** Implemented  
**Implements:** Retriever-agnostic evaluation, artifact replay, category metrics, comparison, lineage  
**Does not implement:** Metric redefinition, retrieval changes, **Phase 4.19+**

See **`docs/architecture/retrieval-evaluation-framework.md`**.

```bash
python scripts/run_unified_retrieval_evaluation.py
```

**Out of scope:** optimization, re-embedding, index rebuilds, **Phase 4.19 / 4.20**.

---

# Phase 4.19 — Production Retrieval Pipeline

**Status:** Implemented  
**Implements:** `ProductionRetrievalPipeline` — RRF candidate pool, structured hard filtering, final top-k  
**Does not implement:** Final ranking, query parsing, **Phase 4.20+**

See **`docs/architecture/production-retrieval-pipeline.md`**.

**Entry point:** `ProductionRetrievalPipeline.retrieve(RetrievalRequest)` with injected RRF retriever and `CatalogCandidateFilter`.

**Out of scope:** cross-encoder reranking, API layer, evaluation rebuilds, **Phase 4.20**.

---

# Phase 4.20 — Retrieval Integration + System Testing

**Status:** Implemented (final retrieval subsystem phase)  
**Implements:** Opt-in integration tests for the full production retrieval path on live PostgreSQL, BM25, BGE, pgvector/HNSW, RRF, and `PostgresCatalogCandidateFilter`  
**Does not implement:** Algorithm changes, benchmark regeneration, ranking, Phase 5

See **`docs/architecture/retrieval-integration-testing.md`**.

```powershell
$env:PRODUCTIQ_RUN_INTEGRATION_TESTS = "1"
$env:PRODUCTIQ_PRODUCTION_RETRIEVAL_SMOKE = "1"
pytest tests/retrieval/integration/ -q
```

**Out of scope:** embedding/index rebuilds, evaluation artifact updates, **Phase 5+**.

