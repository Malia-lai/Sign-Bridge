"""Circuit breaker for LLM providers."""

import time
from enum import Enum
from typing import Callable


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitOpenError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
        enabled: bool = True,
        clock: Callable[[], float] = time.monotonic,
    ):
        self.failure_threshold = max(0, int(failure_threshold))
        self.recovery_timeout = float(recovery_timeout)
        self.half_open_max_calls = max(1, int(half_open_max_calls))
        self.enabled = bool(enabled)
        self.clock = clock
        self.state = CircuitState.CLOSED
        self.failures = 0
        self.opened_at = 0.0
        self.half_open_calls = 0
        # disabled when threshold == 0
        if self.failure_threshold == 0:
            self.enabled = False

    def allow(self) -> bool:
        if not self.enabled:
            return True
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if self.clock() - self.opened_at >= self.recovery_timeout:
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
                return True
            return False
        # half-open
        if self.half_open_calls < self.half_open_max_calls:
            self.half_open_calls += 1
            return True
        return False

    def record_success(self) -> None:
        if not self.enabled:
            return
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0

    def record_failure(self) -> None:
        if not self.enabled:
            return
        self.failures += 1
        if self.state == CircuitState.HALF_OPEN:
            self.state = CircuitState.OPEN
            self.opened_at = self.clock()
            return
        if self.failures >= self.failure_threshold:
            self.state = CircuitState.OPEN
            self.opened_at = self.clock()

    def reset(self) -> None:
        self.failures = 0
        self.state = CircuitState.CLOSED
        self.half_open_calls = 0
        self.opened_at = 0.0

    def stats(self) -> dict:
        return {
            "state": self.state.value,
            "failures": self.failures,
            "opened_at": self.opened_at,
        }

    # aliases
    def is_open(self) -> bool:
        return self.state == CircuitState.OPEN

    def call(self, func, *args, **kwargs):
        if not self.allow():
            raise CircuitOpenError("circuit breaker open")
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as exc:
            self.record_failure()
            raise exc
