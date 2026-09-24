# ProductIQ

Product intelligence platform for analyzing product data with AI/ML.

## Project structure

- `docs/` — architecture, product specs, and ADRs
- `src/productiq/` — application source code
- `tests/` — test suite

## Getting started

1. Create a virtual environment and install dependencies: `pip install -e ".[dev]"`
2. Copy `.env.example` to `.env` and adjust values for your local machine
3. Run tests: `pytest`

## Testing

The test suite lives under `tests/` and discovers modules matching `test_*.py`.
Pytest is configured in `pyproject.toml` with `pythonpath = ["src"]` so the
src-layout package imports correctly without manual `sys.path` changes.

Run the full suite:

```bash
pytest
```

Run with coverage:

```bash
pytest --cov=productiq --cov-report=term-missing
```

Shared test isolation fixtures are defined in `tests/conftest.py`.

## Configuration

ProductIQ reads configuration from environment variables through a typed
`Settings` object in `src/productiq/config/settings.py`. Application code
should access configuration through `get_settings()` rather than calling
`os.getenv()` directly.

For local development, create a `.env` file in the project root. That file
is ignored by Git and must not contain committed secrets. `.env.example` is
the committed template showing supported variables and safe example values.

## Documentation

- [System architecture](docs/architecture/system.md)
- [Data flow](docs/architecture/data-flow.md)
- [Requirements](docs/product/requirements.md)
- [Scope](docs/product/scope.md)
- [ADR-001](docs/decisions/ADR-001-architecture.md)
