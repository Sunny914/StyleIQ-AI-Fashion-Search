# Phase 4.10 — Embedding Model Selection

**Status:** Decision frozen (artifact + contract). **Not implemented:** embedding generation, pgvector indexes, vector search, semantic retriever.

## 1. Requirements (ProductIQ)

| Input | Source |
|--------|--------|
| Product semantic document | Phase 3 `semantic_text` (labeled brand, category, type, color, material, fit, features, style, description) |
| Query semantic intent | Phase 3.8 `QueryRepresentation.semantic_intent` |
| Similarity | Phase 4.9 **cosine** on **L2-normalized** vectors |
| Scale | **367,172** products; pgvector alongside PostgreSQL |
| Runtime | Python **3.13**; local/portfolio inference (CPU acceptable with batching; GPU optional) |
| Constraints | No API-only embeddings; reproducible Hugging Face model IDs; permissive license |

**Measured catalog context (ProductIQ representations parquet):** `semantic_text` length median **132** characters, p95 **171**, max **241** — well within **512-token** limits of short-text embedding models.

## 2. Candidates considered

Sources: official [Hugging Face model cards](https://huggingface.co/), BGE documentation ([bge-model.com](https://bge-model.com)), E5/unilm evaluation notes, MTEB leaderboard entries **as reported on model cards** (not re-run by ProductIQ in 4.10).

| Model | Params (approx) | Dim | Max tokens | Retrieval-oriented evidence (published) | License | ProductIQ notes |
|--------|-----------------|-----|------------|----------------------------------------|---------|-----------------|
| **BAAI/bge-small-en-v1.5** | 33.4M | 384 | 512 | MTEB Retrieval **51.68** (model card table) | MIT | **Selected primary** — English, short-query instruction, retrieval-tuned BGE v1.5 |
| **intfloat/e5-small-v2** | 33M | 384 | 512 | BEIR aggregate ~**49%** (third-party MTEB summary; verify in 4.11) | MIT | **Fallback** — `query:`/`passage:` prefixes |
| sentence-transformers/all-MiniLM-L6-v2 | ~22M | 384 | 512 | MTEB Retrieval **42.92** (community benchmark table) | Apache-2.0 | Fast baseline; weaker retrieval vs BGE/E5 small |
| BAAI/bge-base-en-v1.5 | 109M | 768 | 512 | MTEB Retrieval **53.25** (model card) | MIT | Better quality; **2×** raw vector storage vs 384-d |
| BAAI/bge-large-en-v1.5 | 335M | 1024 | 512 | MTEB Retrieval **54.29** (model card) | MIT | Highest English BGE v1.5 retrieval; heavy inference + **~1.4 GiB** raw vectors |
| BAAI/bge-m3 | ~568M (multi) | 1024 | 8192 | Strong multilingual MIRACL/MTEB (paper/card) | MIT | Overkill for English-only AJIO slice; large RAM; dense 1024-d storage |

**Engineering judgment (not measured on full ProductIQ in 4.10):** For a portfolio/production path with **367k** SKUs, **384-dimensional** English retrieval models balance pgvector footprint and retrieval quality. **bge-small-en-v1.5** beats MiniLM-class retrieval scores on published MTEB tables while matching e5-small storage.

## 3. Decision

### Primary: `BAAI/bge-small-en-v1.5`

**Why (explicit criteria):**

1. **Retrieval fit:** BGE family trained for dense retrieval; v1.5 improves similarity calibration vs v1.0 (model card).
2. **Product–query alignment:** Short queries vs labeled `semantic_text` passages → use query instruction; documents embed raw `semantic_text` (model card guidance).
3. **Dimension / storage:** **384** floats → **563.8 MB** raw float32 for 367,172 products (see §4).
4. **Local inference:** ~133 MB weights — feasible batched CPU/GPU batch job in Phase 4.11 (exact throughput **unknown** until benchmarked locally).
5. **Input length:** Catalog semantic text ≪ 512 tokens.
6. **License:** MIT.
7. **Phase 4.9 alignment:** L2-normalize embeddings; cosine similarity in application layer.

**Encoding contract (frozen in JSON artifact):**

- **Query (`semantic_intent`):** prefix `Represent this sentence for searching relevant passages: ` (query only).
- **Document (`semantic_text`):** no prefix.
- **Normalize:** L2 before storage/search (cosine ≡ dot product).

### Fallback: `intfloat/e5-small-v2`

Same **384-d** storage. Use if Phase 4.11 pilot shows better ranking with E5 `query:` / `passage:` prefixes or tooling constraints. English-only; MIT.

## 4. Storage analysis (367,172 products)

Raw float32 payload (no PostgreSQL overhead):

```text
bytes = 367,172 × dimension × 4
```

| Dimension | MB (10⁶ bytes) | GiB (1024³) |
|-----------|----------------|-------------|
| **384** (primary) | **563.8** | **0.525** |
| 768 | 1127.6 | 1.05 |
| 1024 | 1503.4 | 1.40 |

**pgvector note:** Table columns, TOAST, HNSW/IVFFlat indexes, and metadata FKs add substantial disk beyond raw vector bytes. Phase 4.12 will size indexes separately.

## 5. Inference analysis (367,172 products)

| Topic | Assessment |
|--------|------------|
| **Primary model size** | ~33M parameters (~133 MB FP32 weights per BGE docs) |
| **CPU** | Feasible with batch encoding in Phase 4.11; expect hours-scale without GPU (**throughput not measured** in 4.10) |
| **GPU** | Recommended for one-off full-catalog encoding; batch size tunable |
| **Batching** | Standard sentence-transformers / FlagEmbedding batch APIs (Phase 4.11) |
| **Exact docs/sec** | **Unknown** — benchmark on target hardware in Phase 4.11 |

Do **not** regenerate 367k embeddings in Phase 4.10.

## 6. Evaluation strategy (Phase 4.8 benchmark)

**Reusable for Phase 4.14 semantic retrieval evaluation?** **Yes**, with caveats:

- Same 10 queries and 35 judged relevant IDs can score vector retrieval (Precision/Recall/MRR) via existing Phase 4.8 framework + `Retriever` with `method=vector`.
- **Insufficient alone for model selection:** tiny, incomplete judgments; English fashion slice; not designed to compare embedding architectures.
- **Model selection (4.10)** uses published retrieval benchmarks + ProductIQ engineering constraints, **not** tuning on benchmark labels (no circular labels).

**Small local pilot (4.10):** Not run — downloading multiple transformer checkpoints is out of scope for this phase. Phase 4.11 should run a **controlled sample** (e.g. benchmark-related product IDs + stratified slice) to validate encoding prefixes and throughput before full catalog encoding.

## 7. Reproducibility artifact

Machine-readable freeze:

`resources/embedding/productiq_embedding_model_selection_v1.json`

Code loader:

`productiq.retrieval.embedding_selection.load_productiq_embedding_model_selection`

Pin `model_revision` to a Hugging Face commit in Phase 4.11 when generation is implemented.

## 8. What remains (Phase 4.11+)

| Phase | Work |
|-------|------|
| **4.11** | Embedding generation pipeline, dependency pins, batch job over `semantic_text` / query views |
| **4.12** | pgvector storage + index |
| **4.13** | Semantic candidate retrieval (`Retriever`, `method=vector`) |
| **4.14** | Semantic evaluation on Phase 4.8 benchmark (optional extensions) |

## 9. Limitations

- English-only models; catalog is mostly English with brand-specific tokens.
- Selection relies on **published** MTEB/BEIR figures and catalog statistics, not a full embedding pilot.
- Fallback model not automatically inferior — validate on ProductIQ sample in 4.11.
- Hybrid, reranking, and model fine-tuning are out of scope.
