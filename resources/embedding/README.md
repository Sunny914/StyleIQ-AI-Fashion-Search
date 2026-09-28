# ProductIQ embedding model selection (Phase 4.10)

Frozen decision artifact for semantic embedding generation (Phase 4.11+).

- **Artifact:** `productiq_embedding_model_selection_v1.json`
- **Primary model:** `BAAI/bge-small-en-v1.5` (384-d, cosine, L2-normalize)
- **Fallback:** `intfloat/e5-small-v2` (384-d, `query:` / `passage:` prefixes)

Full research, candidate comparison, storage/inference analysis, and evaluation strategy:
`docs/architecture/embedding-model-selection.md`

Load in code:

```python
from productiq.retrieval.embedding_selection import load_productiq_embedding_model_selection

selection = load_productiq_embedding_model_selection()
print(selection.primary_model.huggingface_model_id)
```

**Not in this phase:** embedding generation, pgvector tables, vector indexes, or semantic retrieval execution.
