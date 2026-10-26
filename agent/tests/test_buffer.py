import os

os.environ.setdefault("MOCK_MODE", "true")

from app.core.buffer import SlidingWindowBuffer, dedupe_immediate_repeats


def test_buffer_basic(buffer):
    buffer.add("a")
    buffer.append("b")
    buffer.extend(["c", "c"])
    assert buffer.get() == ["a", "b", "c", "c"] or buffer.get() == ["a", "b", "c"]
    assert len(buffer) >= 3


def test_buffer_capacity():
    b = SlidingWindowBuffer(size=2)
    b.extend(["a", "b", "c"])
    assert b.get() == ["b", "c"]
    assert len(b) == 2


def test_buffer_clear_reset():
    b = SlidingWindowBuffer(size=3)
    b.extend(["a", "b"])
    b.clear()
    assert b.get() == []
    b.extend(["x"])
    b.reset()
    assert len(b) == 0


def test_dedupe_immediate():
    assert dedupe_immediate_repeats(["a", "a", "b", "b", "b", "c"]) == ["a", "b", "c"]
    assert SlidingWindowBuffer.dedupe_immediate([]) == []


def test_dedupe_with_window():
    b = SlidingWindowBuffer(size=3)
    b.extend(["a"])
    assert b.dedupe_with_window(["a", "b", "b"]) == ["b"]
    b2 = SlidingWindowBuffer(size=3)
    assert b2.dedupe_with_window(["x", "y"]) == ["x", "y"]


def test_buffer_aliases_and_props():
    from app.core.buffer import Buffer, WordBuffer, SlidingBuffer

    b = Buffer(size=4)
    b.push("z")
    assert b.recent_words == ["z"]
    assert b.words == ["z"]
    assert b.to_list() == ["z"]
    assert list(b) == ["z"]


def test_buffer_recent():
    b = SlidingWindowBuffer(size=10)
    b.extend(["a", "b", "c"])
    assert b.recent(2) == ["b", "c"]
    assert b.latest() == ["a", "b", "c"]
    assert b.window() == ["a", "b", "c"]
    assert b.values() == ["a", "b", "c"]
