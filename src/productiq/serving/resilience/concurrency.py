"""Concurrency gates for expensive serving operations (Phase 13.10-B)."""

from __future__ import annotations

import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field


@dataclass
class ConcurrencyGate:
    """Bounded in-flight counter for one operation class."""

    limit: int
    _in_flight: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    def __post_init__(self) -> None:
        if self.limit < 1:
            msg = "limit must be >= 1"
            raise ValueError(msg)

    @contextmanager
    def acquire(self) -> Iterator[None]:
        if not self._try_acquire():
            msg = "concurrency limit exceeded"
            raise ConcurrencyLimitExceeded(msg)
        try:
            yield
        finally:
            self._release()

    def try_acquire(self) -> bool:
        return self._try_acquire()

    def _try_acquire(self) -> bool:
        with self._lock:
            if self._in_flight >= self.limit:
                return False
            self._in_flight += 1
            return True

    def _release(self) -> None:
        with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

    def release(self) -> None:
        """Release a slot acquired via ``try_acquire``."""
        self._release()


class ConcurrencyLimitExceeded(Exception):
    """Raised when an operation concurrency gate is full."""


class NullConcurrencyGate:
    @contextmanager
    def acquire(self) -> Iterator[None]:
        yield

    def try_acquire(self) -> bool:
        return True


__all__ = [
    "ConcurrencyGate",
    "ConcurrencyLimitExceeded",
    "NullConcurrencyGate",
]
