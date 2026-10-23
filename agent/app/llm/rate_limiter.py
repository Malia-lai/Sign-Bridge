import asyncio
import math
import threading
import time
from collections import deque
from dataclasses import dataclass
from typing import Callable, Deque


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

    @staticmethod
    def safe_calls_per_minute(
        estimated_tokens: int, requests_per_minute: int, tokens_per_minute: int
    ) -> int:
        if estimated_tokens <= 0:
            return requests_per_minute
        return min(requests_per_minute, tokens_per_minute // estimated_tokens)


_shared_limiters: dict[tuple[int, int], SlidingWindowRateLimiter] = {}
_shared_lock = threading.Lock()


def get_shared_limiter(requests_per_minute: int, tokens_per_minute: int) -> SlidingWindowRateLimiter:
    key = (requests_per_minute, tokens_per_minute)
    with _shared_lock:
        limiter = _shared_limiters.get(key)
        if limiter is None:
            limiter = SlidingWindowRateLimiter(*key)
            _shared_limiters[key] = limiter
        return limiter
