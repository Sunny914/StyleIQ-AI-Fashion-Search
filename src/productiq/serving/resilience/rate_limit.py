"""Rate limiting primitives (Phase 13.10-B)."""

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class RateLimitDecision:
    """Outcome of a rate-limit check."""

    allowed: bool
    retry_after_seconds: int | None = None


class RateLimiter(Protocol):
    """Vendor-neutral rate limiter (in-memory or distributed backend)."""

    def allow(self, key: str) -> RateLimitDecision: ...


@dataclass
class FixedWindowRateLimiter:
    """Thread-safe fixed-window counter with bounded key storage."""

    requests_per_window: int
    window_seconds: int
    max_keys: int = 10_000

    def __post_init__(self) -> None:
        if self.requests_per_window < 1:
            msg = "requests_per_window must be >= 1"
            raise ValueError(msg)
        if self.window_seconds < 1:
            msg = "window_seconds must be >= 1"
            raise ValueError(msg)
        if self.max_keys < 1:
            msg = "max_keys must be >= 1"
            raise ValueError(msg)
        self._lock = threading.Lock()
        self._windows: OrderedDict[str, tuple[int, int]] = OrderedDict()

    def allow(self, key: str) -> RateLimitDecision:
        now = int(time.time())
        window_id = now // self.window_seconds
        with self._lock:
            self._evict_expired(now=now)
            count, stored_window = self._windows.get(key, (0, window_id))
            if stored_window != window_id:
                count = 0
            if count >= self.requests_per_window:
                window_end = (window_id + 1) * self.window_seconds
                retry_after = max(1, window_end - now)
                return RateLimitDecision(allowed=False, retry_after_seconds=retry_after)
            self._windows[key] = (count + 1, window_id)
            self._windows.move_to_end(key)
            self._enforce_max_keys()
        return RateLimitDecision(allowed=True)

    def _evict_expired(self, *, now: int) -> None:
        current_window = now // self.window_seconds
        stale = [key for key, (_, window_id) in self._windows.items() if window_id < current_window]
        for key in stale:
            del self._windows[key]

    def _enforce_max_keys(self) -> None:
        while len(self._windows) > self.max_keys:
            self._windows.popitem(last=False)


class NullRateLimiter:
    """Always allow (disabled rate limiting)."""

    def allow(self, key: str) -> RateLimitDecision:
        _ = key
        return RateLimitDecision(allowed=True)


__all__ = [
    "FixedWindowRateLimiter",
    "NullRateLimiter",
    "RateLimitDecision",
    "RateLimiter",
]
