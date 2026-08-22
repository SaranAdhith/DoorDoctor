"""In-memory sliding-window rate limiting.

State lives in this process, which is exactly right for the single-worker demo
deployment and exactly wrong for a horizontally scaled one. In production this
becomes a Redis sorted set per key; the call sites do not change, only the
storage behind `RateLimiter`.

Usage:

    limiter.check("forgot-password:email", email, limit=5, per_seconds=3600)

Every call both *records* the attempt and enforces the budget, so a caller
cannot accidentally consume budget without being limited by it.
"""

from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from .exceptions import TooManyRequestsError


class RateLimiter:
    """Fixed set of sliding windows, keyed by `scope` + `key`."""

    def __init__(self) -> None:
        self._hits: dict[tuple[str, str], deque[float]] = defaultdict(deque)
        # FastAPI serves sync endpoints on a thread pool, so two requests really
        # can land here at once.
        self._lock = threading.Lock()

    def check(self, scope: str, key: str, *, limit: int, per_seconds: int) -> None:
        """Record an attempt, raising `TooManyRequestsError` once the window is full."""
        retry_after = self._record(scope, key, limit=limit, per_seconds=per_seconds)
        if retry_after is not None:
            raise TooManyRequestsError(
                "Too many attempts. Please wait a few minutes and try again.",
                retry_after=retry_after,
            )

    def _record(self, scope: str, key: str, *, limit: int, per_seconds: int) -> int | None:
        """Return None when allowed, or the seconds until the oldest hit expires."""
        now = time.monotonic()
        cutoff = now - per_seconds
        bucket_key = (scope, key.strip().lower())

        with self._lock:
            bucket = self._hits[bucket_key]
            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= limit:
                return max(1, int(bucket[0] + per_seconds - now) + 1)

            bucket.append(now)
            if not bucket:  # pragma: no cover - defensive
                del self._hits[bucket_key]
            return None

    def reset(self) -> None:
        """Drop every window. Tests call this; nothing in the app does."""
        with self._lock:
            self._hits.clear()


limiter = RateLimiter()

# Budgets for the password-reset flow (§2.1).
FORGOT_PASSWORD_PER_EMAIL = (5, 3600)
FORGOT_PASSWORD_PER_IP = (20, 3600)

# Budget for the assistant (§2.3). An unmetered endpoint that reaches a paid LLM
# from behind a login is the obvious way to burn a free Groq tier, and the
# deterministic fallback is not free either — every question builds a context
# pack, which is a dozen queries.
ASSISTANT_PER_USER = (30, 3600)

# Budget for public lead capture (§2.6). `POST /leads` is the only endpoint in
# this codebase a stranger can write to, so it is budgeted twice: once per
# source address, and once per email so a botnet cannot spread one address's
# enquiries across many IPs. Deliberately generous enough that a family filling
# the form, mistyping a phone number and resubmitting is never refused.
LEADS_PER_IP = (10, 3600)
LEADS_PER_EMAIL = (3, 3600)
