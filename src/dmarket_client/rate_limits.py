"""A shareable process-local limiter; implement Limiter for distributed coordination."""

import math
import threading
import time
from collections.abc import Callable, Mapping
from email.utils import parsedate_to_datetime
from typing import Protocol

from .exceptions import ConfigurationError


class Limiter(Protocol):
    """reserve grants a token at 0, or returns a delay before trying again."""

    def reserve(self, group: str) -> float: ...
    def observe(self, group: str, headers: Mapping[str, str]) -> None: ...


def retry_after(headers: Mapping[str, str], *, wall_time: float | None = None) -> float | None:
    value = headers.get("retry-after")
    if not value:
        return None
    try:
        seconds = float(value)
    except ValueError:
        try:
            seconds = parsedate_to_datetime(value).timestamp() - (
                wall_time if wall_time is not None else time.time()
            )
        except ValueError, TypeError, OverflowError:
            return None
    return max(0.0, seconds) if math.isfinite(seconds) else None


class RateLimiter:
    """Conservative global 5 RPS. Shared by sync/async clients when explicitly injected.

    All routes share the global budget, avoiding unverified category mappings.
    Server headers can lower the rate or postpone requests, never raise this ceiling.
    """

    def __init__(
        self, requests_per_second: float = 5.0, *, clock: Callable[[], float] = time.monotonic
    ) -> None:
        if not math.isfinite(requests_per_second) or requests_per_second <= 0:
            raise ConfigurationError("requests_per_second must be positive and finite")
        self._rate = requests_per_second
        self._clock = clock
        self._lock = threading.Lock()
        self._next = 0.0

    def reserve(self, group: str) -> float:
        with self._lock:
            now = self._clock()
            if now < self._next:
                return self._next - now
            self._next = now + 1 / self._rate
            return 0.0

    def observe(self, group: str, headers: Mapping[str, str]) -> None:
        with self._lock:
            limit = headers.get("x-ratelimit-limit-second")
            if limit:
                try:
                    value = float(limit)
                    if math.isfinite(value) and value > 0:
                        self._rate = min(self._rate, value)
                except ValueError:
                    pass
            delay = retry_after(headers) or 0.0
            remaining = headers.get(
                "x-ratelimit-remaining-second", headers.get("ratelimit-remaining")
            )
            if remaining == "0":
                # DMarket documents reset=1. Only consume plausible relative seconds.
                try:
                    reset = float(headers.get("ratelimit-reset", "1"))
                    if math.isfinite(reset) and 0 <= reset <= 60:
                        delay = max(delay, reset)
                    else:
                        delay = max(delay, 1.0)
                except ValueError:
                    delay = max(delay, 1.0)
            self._next = max(self._next, self._clock() + delay)
