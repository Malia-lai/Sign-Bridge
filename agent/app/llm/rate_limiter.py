import asyncio
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Callable, Deque

WINDOW_SECONDS = 60.0


def estimate_prompt_tokens(system_prompt: str, user_prompt: str) -> int:
    return math.ceil((len(system_prompt or "") + len(user_prompt or "")) / 4)


def estimate_call_tokens(system_prompt: str, user_prompt: str, max_output_tokens: int) -> int:
    return estimate_prompt_tokens(system_prompt, user_prompt) + max_output_tokens


@dataclass
class Reservation:
    timestamp: float
    tokens: int


class SlidingWindowRateLimiter:
    def __init__(
        self,
        requests_per_minute: int,
        tokens_per_minute: int,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], object] = asyncio.sleep,
        sync_sleep: Callable[[float], object] = time.sleep,
        window_seconds: float = WINDOW_SECONDS,
    ):
        if requests_per_minute <= 0 or tokens_per_minute <= 0:
            raise ValueError("Rate limits must be positive")
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute
        self.clock = clock
        self.sleep = sleep
        self.sync_sleep = sync_sleep
        self.window_seconds = window_seconds
        self._events: Deque[Reservation] = deque()
        self._lock = threading.Lock()

    def _try_acquire(self, estimated_tokens: int):
        if estimated_tokens < 0:
            raise ValueError("estimated_tokens cannot be negative")
        if estimated_tokens > self.tokens_per_minute:
            raise ValueError("A single call exceeds the tokens-per-minute budget")

        with self._lock:
            now = self.clock()
            while self._events and now - self._events[0].timestamp >= self.window_seconds:
                self._events.popleft()

            total_tokens = sum(event.tokens for event in self._events)
            if (
                len(self._events) < self.requests_per_minute
                and total_tokens + estimated_tokens <= self.tokens_per_minute
            ):
                reservation = Reservation(now, estimated_tokens)
                self._events.append(reservation)
                return reservation, 0.0

            wait_until = now
            if len(self._events) >= self.requests_per_minute:
                wait_until = max(wait_until, self._events[0].timestamp + self.window_seconds)
            token_deficit = total_tokens + estimated_tokens - self.tokens_per_minute
            if token_deficit > 0:
                released = 0
                for event in self._events:
                    released += event.tokens
                    if released >= token_deficit:
                        wait_until = max(wait_until, event.timestamp + self.window_seconds)
                        break
            return None, max(0.0, wait_until - now)

    async def acquire(self, estimated_tokens: int) -> Reservation:
        while True:
            reservation, wait_seconds = self._try_acquire(estimated_tokens)
            if reservation is not None:
                return reservation
            await self.sleep(wait_seconds)

    def acquire_sync(self, estimated_tokens: int) -> Reservation:
        while True:
            reservation, wait_seconds = self._try_acquire(estimated_tokens)
            if reservation is not None:
                return reservation
            self.sync_sleep(wait_seconds)

    def update(self, reservation: Reservation, actual_tokens: int) -> None:
        if actual_tokens < 0:
            raise ValueError("actual_tokens cannot be negative")
        with self._lock:
            reservation.tokens = actual_tokens

    def reset(self) -> None:
        with self._lock:
            self._events.clear()

    def stats(self) -> dict:
        with self._lock:
            now = self.clock()
            while self._events and now - self._events[0].timestamp >= self.window_seconds:
                self._events.popleft()
            total_tokens = sum(e.tokens for e in self._events)
            return {
                "requests": len(self._events),
                "tokens": total_tokens,
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "window_seconds": self.window_seconds,
            }

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "requests_per_minute": self.requests_per_minute,
                "tokens_per_minute": self.tokens_per_minute,
                "events": [(e.timestamp, e.tokens) for e in self._events],
            }

    def restore(self, snapshot: dict) -> None:
        with self._lock:
            self._events.clear()
            for ts, toks in (snapshot or {}).get("events", []):
                self._events.append(Reservation(timestamp=ts, tokens=toks))

    @staticmethod
    def safe_calls_per_minute(
        estimated_tokens: int, requests_per_minute: int, tokens_per_minute: int
    ) -> int:
        if estimated_tokens <= 0:
            return requests_per_minute
        return min(requests_per_minute, tokens_per_minute // estimated_tokens)


_shared_limiters: dict[tuple[int, int], SlidingWindowRateLimiter] = {}
_shared_lock = threading.Lock()


def get_shared_limiter(
    requests_per_minute: int, tokens_per_minute: int, key: Any = None
) -> SlidingWindowRateLimiter:
    base_key = (requests_per_minute, tokens_per_minute)
    if key is None:
        store_key = base_key
    else:
        store_key = (str(key),) + base_key
    with _shared_lock:
        limiter = _shared_limiters.get(store_key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(requests_per_minute, tokens_per_minute)
            _shared_limiters[store_key] = limiter
        return limiter


# per-user / per-api-key rate limiting
_per_key_limiters: dict = {}
_per_key_lock = threading.Lock()


def get_limiter_for_key(
    key: Any, requests_per_minute: int = 30, tokens_per_minute: int = 14000
) -> SlidingWindowRateLimiter:
    store_key = (str(key), requests_per_minute, tokens_per_minute)
    with _per_key_lock:
        limiter = _per_key_limiters.get(store_key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(requests_per_minute, tokens_per_minute)
            _per_key_limiters[store_key] = limiter
        return limiter


def get_user_limiter(
    user_id: Any, requests_per_minute: int = 30, tokens_per_minute: int = 14000
) -> SlidingWindowRateLimiter:
    return get_limiter_for_key(f"user:{user_id}", requests_per_minute, tokens_per_minute)


def get_api_key_limiter(
    api_key: Any, requests_per_minute: int = 30, tokens_per_minute: int = 14000
) -> SlidingWindowRateLimiter:
    return get_limiter_for_key(f"apikey:{api_key}", requests_per_minute, tokens_per_minute)


class PerKeyRateLimiter:
    def __init__(self, requests_per_minute: int = 30, tokens_per_minute: int = 14000):
        self.requests_per_minute = requests_per_minute
        self.tokens_per_minute = tokens_per_minute

    def for_key(self, key: Any) -> SlidingWindowRateLimiter:
        return get_limiter_for_key(key, self.requests_per_minute, self.tokens_per_minute)
