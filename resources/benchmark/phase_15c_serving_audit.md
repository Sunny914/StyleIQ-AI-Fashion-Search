# Phase 15C — Serving integration audit

- status: **BLOCKED**
- generated_at_utc: `2026-10-22T16:44:54.645446Z`
- catalog_mode: `fixture`

## Checks

| Check | Status |
|-------|--------|
| compose_config | PASS |
| api_image_build | PASS |
| fixture_load | PASS |
| pgvector_schema | PASS |
| http_search | PASS |
| http_product | PASS |
| http_recommendation | PASS |
| readiness | PASS |
| full_catalog_load | NOT_RUN |
| pytest_gate | FAIL |
| ruff | FAIL |
| mypy | PASS |

## Notes

- Live API on http://127.0.0.1:8010 after fixture load; catalog_mode=fixture (3 products, 3 embeddings); NOT the 367172-row catalog.
- HTTP search navy cotton shirt: compose-demo-003 rank 1 (lexical). HTTP search nike running shoes: compose-demo-001 rank 1 (semantic). Women filter excluded compose-demo-001.
- GET /api/v1/products/compose-demo-001 -> 200 Nike. Unknown id -> 404 Product not found.
- POST /api/v1/recommendations seed compose-demo-001 returned compose-demo-003 and compose-demo-002; seed excluded.
- PostgreSQL: 3 rows, embedding vector(384), HNSW ix_products_embedding_hnsw_cosine vector_cosine_ops, extension vector.
- Full non-integration pytest: 1710 passed, 2 failed, 49 skipped in 866s. Failures: (1) compose 127.0.0.1 healthcheck — removed; 21 compose contract tests then passed. (2) observability SLO test — passed on rerun.
- Phase 15C contract tests (compose + production_stack): 11 passed after connect_timeout fix.
- Ruff src/tests: 18 errors, all pre-existing outside 15C modules. 15C files ruff-clean.
- mypy on 15C modules: Success.
- full_catalog_load NOT_RUN: 367172-row load was not executed.
- BGE loads at API factory time into HF_HOME=/tmp/hf-cache (named volume avoided due to uid 1000 permissions).
- serving.performance.__init__ no longer eagerly imports TestClient/httpx.

## Catalog

- expected full count: `367172`
- observed full count: `None`
- full catalog verified: `False`
