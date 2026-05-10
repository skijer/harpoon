"""Token-bucket rate limiter, keyed by (session_id, primitive).

Each rule has (count, window_seconds). A bucket starts full; each invocation
consumes one token; tokens regenerate proportionally to elapsed time. If the
bucket is empty, the call is denied.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class _Bucket:
    capacity: int
    window: float
    tokens: float = 0.0
    last_refill: float = field(default_factory=time.monotonic)

    def __post_init__(self) -> None:
        self.tokens = float(self.capacity)

    def try_consume(self, now: float) -> bool:
        elapsed = now - self.last_refill
        if elapsed > 0:
            refill = (elapsed / self.window) * self.capacity
            self.tokens = min(self.capacity, self.tokens + refill)
            self.last_refill = now
        if self.tokens >= 1.0:
            self.tokens -= 1.0
            return True
        return False


class RateLimiter:
    """Per-session, per-primitive token bucket."""

    def __init__(self) -> None:
        self._buckets: dict[tuple[int, str], _Bucket] = {}

    def check(self, session_id: int, primitive: str, count: int, window: float) -> bool:
        key = (session_id, primitive)
        bucket = self._buckets.get(key)
        if bucket is None or bucket.capacity != count or bucket.window != window:
            bucket = _Bucket(capacity=count, window=window)
            self._buckets[key] = bucket
        return bucket.try_consume(time.monotonic())

    def forget(self, session_id: int) -> None:
        """Remove all buckets for a session (call on disconnect)."""
        for key in [k for k in self._buckets if k[0] == session_id]:
            del self._buckets[key]
