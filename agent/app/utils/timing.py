"""Timing helpers: context managers and decorators for per-stage measurements."""

import asyncio
import functools
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional


@dataclass
class StageTiming:
    name: str
    start: float = 0.0
    end: float = 0.0
    elapsed: float = 0.0
    elapsed_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def finish(self) -> "StageTiming":
        self.end = time.perf_counter()
        self.elapsed = self.end - self.start
        self.elapsed_ms = self.elapsed * 1000.0
        return self


class TimingContext:
    """Context manager recording a single named stage.

    Usage:
        with TimingContext("llm") as t:
            ...
        print(t.elapsed, t.elapsed_ms)
    """

    def __init__(
        self,
        stage: Optional[str] = None,
        name: Optional[str] = None,
        timings: Optional[Dict[str, Any]] = None,
        store_ms: bool = False,
    ) -> None:
        self.stage = stage or name or "stage"
        self.name = self.stage
        self.timings = timings if timings is not None else {}
        self.store_ms = store_ms
        self.start = 0.0
        self.end = 0.0
        self.elapsed = 0.0
        self.elapsed_ms = 0.0
        self.duration = 0.0
        self.duration_ms = 0.0

    def __enter__(self) -> "TimingContext":
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        self.end = time.perf_counter()
        self.elapsed = self.end - self.start
        self.elapsed_ms = self.elapsed * 1000.0
        self.duration = self.elapsed
        self.duration_ms = self.elapsed_ms
        try:
            self.timings[self.stage] = self.elapsed_ms if self.store_ms else self.elapsed
        except Exception:
            pass
        return False

    # dict-like convenience
    def __getitem__(self, key):
        return self.timings[key]

    def __setitem__(self, key, value):
        self.timings[key] = value


class StageTimer(TimingContext):
    """Alias of TimingContext."""


class Timer:
    """Multi-stage timer aggregating timings into a dict."""

    def __init__(self, timings: Optional[Dict[str, Any]] = None) -> None:
        self.timings: Dict[str, Any] = timings if timings is not None else {}
        self._starts: Dict[str, float] = {}

    def start(self, stage: str) -> float:
        now = time.perf_counter()
        self._starts[stage] = now
        return now

    def stop(self, stage: str) -> float:
        start = self._starts.pop(stage, None)
        if start is None:
            start = time.perf_counter()
        elapsed = time.perf_counter() - start
        self.timings[stage] = elapsed
        return elapsed

    @contextmanager
    def time(self, stage: str):
        ctx = TimingContext(stage, timings=self.timings)
        with ctx:
            yield ctx
        # ensure recorded
        self.timings[stage] = ctx.elapsed

    @contextmanager
    def stage(self, stage: str):
        with self.time(stage) as ctx:
            yield ctx

    def context(self, stage: str, timings: Optional[Dict[str, Any]] = None):
        t = timings if timings is not None else self.timings
        return TimingContext(stage, timings=t)

    def as_dict(self) -> Dict[str, Any]:
        return dict(self.timings)

    def reset(self) -> None:
        self.timings.clear()
        self._starts.clear()


def timed(stage: Optional[str] = None, timer: Optional[Timer] = None):
    """Decorator recording execution time of a function (sync or async)."""

    def decorator(func: Callable) -> Callable:
        name = stage or getattr(func, "__name__", "function")

        if asyncio.iscoroutinefunction(func):

            @functools.wraps(func)
            async def wrapper(*args, **kwargs):
                with TimingContext(name):
                    return await func(*args, **kwargs)

            return wrapper
        else:

            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with TimingContext(name):
                    return func(*args, **kwargs)

            return wrapper

    return decorator


def time_stage(stage: str, timings: Optional[Dict[str, Any]] = None):
    return TimingContext(stage, timings=timings)


def stage_timer(stage: str, timings: Optional[Dict[str, Any]] = None):
    return TimingContext(stage, timings=timings)


def measure(stage: str, timings: Optional[Dict[str, Any]] = None):
    return TimingContext(stage, timings=timings)


@contextmanager
def timing(stage: str, timings: Optional[Dict[str, Any]] = None):
    ctx = TimingContext(stage, timings=timings)
    with ctx:
        yield ctx


def record_timing(timings: Dict[str, Any], stage: str, value: float) -> None:
    timings[stage] = value


# aliases
stage = stage_timer
measure_stage = measure
TimerContext = TimingContext
TimedContext = TimingContext
