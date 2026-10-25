# Compose integration demo data (Phase 15B)

This directory documents **small, labeled demo catalog rows** used for Docker Compose smoke tests.

- Demo rows are inserted by `python -m productiq.database.load_runtime_catalog --mode fixture` (or bootstrap `--load-demo-fixture`).
- Product IDs use the `compose-demo-*` prefix and **must not** be reported as the 367,172-row AJIO catalog.
- Demo product IDs use the `compose-demo-*` prefix.
- This is **not** the 367,172-row AJIO reference catalog.

Full catalog loading remains an explicit operator step and is **not** implied by fixture success:

```bash
python -m productiq.database.load_runtime_catalog --mode full --enforce-official-checksums --json
```
