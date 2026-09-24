# ADR-001: Initial Architecture

## Status

Accepted

## Context

ProductIQ needs a clear structure for a portfolio-grade ML/engineering project.

## Decision

- Use a `src/` layout with package name `productiq`
- Separate `docs/` for architecture, product, and ADRs
- Configuration via `.env` (see `.env.example`)
- Tests in top-level `tests/`

## Consequences

**Positive:** Standard Python layout, easy to extend, good for reviewers.

**Negative:** More folders upfront before code exists; acceptable for clarity.
