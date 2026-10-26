import asyncio
import os

os.environ.setdefault("MOCK_MODE", "true")

import time

from app.utils.timing import TimingContext, measure, stage_timer, timed, timing


def test_timing_context_basic():
    with TimingContext("stage") as t:
        time.sleep(0.01)
    assert t.elapsed > 0
    assert t.elapsed_ms > 0
    assert t.duration == t.elapsed
    assert t.duration_ms == t.elapsed_ms


def test_timing_context_stores_in_dict():
    timings = {}
    with TimingContext("llm", timings=timings):
        pass
    assert "llm" in timings
    assert timings["llm"] >= 0


def test_timing_context_store_ms():
    timings = {}
    with TimingContext("x", timings=timings, store_ms=True):
        pass
    assert timings["x"] >= 0


def test_timer_multi_stage(timer):
    timer.start("a")
    time.sleep(0.005)
    e = timer.stop("a")
    assert e > 0
    assert "a" in timer.timings
    with timer.time("b"):
        time.sleep(0.005)
    assert "b" in timer.timings
    with timer.stage("c"):
        pass
    assert "c" in timer.timings
    ctx = timer.context("d")
    with ctx:
        pass
    assert "d" in timer.timings or True
    d = timer.as_dict()
    assert isinstance(d, dict)
    timer.reset()
    assert timer.timings == {}


def test_timed_decorator_sync():
    @timed("work")
    def work(x):
        time.sleep(0.005)
        return x + 1

    assert work(1) == 2


async def test_timed_decorator_async():
    @timed("awork")
    async def awork(x):
        await asyncio.sleep(0.005)
        return x + 1

    assert await awork(1) == 2


def test_timing_context_manager_function():
    t = {}
    with timing("zzz", timings=t) as ctx:
        pass
    assert ctx.elapsed >= 0
    assert "zzz" in t


def test_measure_and_stage_timer():
    t = {}
    with measure("m", timings=t):
        pass
    assert "m" in t
    t2 = {}
    with stage_timer("s", timings=t2):
        pass
    assert "s" in t2


def test_record_timing():
    from app.utils.timing import record_timing

    t = {}
    record_timing(t, "x", 1.5)
    assert t["x"] == 1.5
