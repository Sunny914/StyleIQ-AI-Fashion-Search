"""Build resilience primitives from serving configuration (Phase 13.10-B)."""

from __future__ import annotations

from dataclasses import dataclass

from productiq.serving.config import ServingConfig
from productiq.serving.resilience.concurrency import ConcurrencyGate, NullConcurrencyGate
from productiq.serving.resilience.rate_limit import (
    FixedWindowRateLimiter,
    NullRateLimiter,
    RateLimiter,
)


@dataclass(frozen=True)
class ApplicationResilience:
    rate_limiter: RateLimiter
    search_concurrency: ConcurrencyGate | NullConcurrencyGate
    recommendation_concurrency: ConcurrencyGate | NullConcurrencyGate


def build_application_resilience(config: ServingConfig) -> ApplicationResilience:
    if config.rate_limit_enabled:
        rate_limiter: RateLimiter = FixedWindowRateLimiter(
            requests_per_window=config.rate_limit_requests_per_window,
            window_seconds=config.rate_limit_window_seconds,
            max_keys=config.rate_limit_max_keys,
        )
    else:
        rate_limiter = NullRateLimiter()

    search_concurrency: ConcurrencyGate | NullConcurrencyGate
    if config.search_concurrency_limit > 0:
        search_concurrency = ConcurrencyGate(limit=config.search_concurrency_limit)
    else:
        search_concurrency = NullConcurrencyGate()

    recommendation_concurrency: ConcurrencyGate | NullConcurrencyGate
    if config.recommendation_concurrency_limit > 0:
        recommendation_concurrency = ConcurrencyGate(limit=config.recommendation_concurrency_limit)
    else:
        recommendation_concurrency = NullConcurrencyGate()

    return ApplicationResilience(
        rate_limiter=rate_limiter,
        search_concurrency=search_concurrency,
        recommendation_concurrency=recommendation_concurrency,
    )


__all__ = ["ApplicationResilience", "build_application_resilience"]
