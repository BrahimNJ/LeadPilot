"""A small in-memory rate limiter.

Counters live in the process, which is exact for a single instance (the public demo)
and a per-instance limit otherwise. See ADR 0003.
"""

WINDOW_SECONDS = 60
# A flood of different addresses must not grow the table without limit.
MAX_TRACKED_CLIENTS = 10_000
_OVERFLOW_KEY = "__overflow__"


class RateLimiter:
    """Allow `limit` requests per client in each one-minute window."""

    def __init__(self, limit: int) -> None:
        self.limit = limit
        self._window = -1
        self._counts: dict[str, int] = {}

    def check(self, client: str, now: float) -> int:
        """Count a request. Return 0 if allowed, else the seconds to wait."""
        window = int(now // WINDOW_SECONDS)
        if window != self._window:
            self._window = window
            self._counts.clear()

        if client not in self._counts and len(self._counts) >= MAX_TRACKED_CLIENTS:
            client = _OVERFLOW_KEY
        count = self._counts.get(client, 0) + 1
        self._counts[client] = count
        if count <= self.limit:
            return 0
        return max(1, WINDOW_SECONDS - int(now % WINDOW_SECONDS))
