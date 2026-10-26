"""Sliding window buffer of recent words for the agent."""

from collections import deque
from typing import Any, Deque, Iterable, List, Optional


class SlidingWindowBuffer:
    """Keep the most recent N words; drop older ones."""

    def __init__(
        self, size: int = 10, capacity: Optional[int] = None, window_size: Optional[int] = None
    ):
        if window_size is not None:
            size = window_size
        if capacity is not None:
            size = capacity
        self.size = max(1, int(size))
        self.capacity = self.size
        self.window_size = self.size
        self.maxlen = self.size
        self.max_size = self.size
        self._items: Deque[str] = deque(maxlen=self.size)

    # core ops
    def add(self, word: Any) -> None:
        if word is None:
            return
        w = str(word).strip()
        if w:
            self._items.append(w)

    def append(self, word: Any) -> None:
        self.add(word)

    def extend(self, words: Iterable[Any]) -> None:
        for w in words or []:
            self.add(w)

    def push(self, word: Any) -> None:
        self.add(word)

    def record(self, words: Iterable[Any]) -> None:
        self.extend(words)

    def update(self, words: Iterable[Any]) -> None:
        self.extend(words)

    def get(self) -> List[str]:
        return list(self._items)

    def recent(self, n: Optional[int] = None) -> List[str]:
        items = list(self._items)
        if n is None:
            return items
        return items[-int(n) :]

    def window(self) -> List[str]:
        return self.get()

    def to_list(self) -> List[str]:
        return self.get()

    def values(self) -> List[str]:
        return self.get()

    def __len__(self) -> int:
        return len(self._items)

    def __iter__(self):
        return iter(self._items)

    def clear(self) -> None:
        self._items.clear()

    def reset(self) -> None:
        self.clear()

    # dedup helpers
    @staticmethod
    def dedupe_immediate(words: Iterable[Any]) -> List[str]:
        out: List[str] = []
        prev = None
        for w in words or []:
            s = str(w).strip() if not isinstance(w, str) else w.strip()
            if not s:
                continue
            if s == prev:
                continue
            out.append(s)
            prev = s
        return out

    def dedupe_with_window(self, words: Iterable[Any]) -> List[str]:
        """Drop leading word if it repeats the last buffered word."""
        words = [str(w).strip() for w in (words or []) if str(w).strip()]
        if not words:
            return words
        if self._items and words[0] == self._items[-1]:
            words = words[1:]
        # also collapse immediate repeats within the new list
        return self.dedupe_immediate(words)

    def process_words(self, words: Iterable[Any]) -> List[str]:
        return self.dedupe_with_window(words)

    def get_recent(self, n: Optional[int] = None) -> List[str]:
        return self.recent(n)

    def latest(self, n: Optional[int] = None) -> List[str]:
        return self.recent(n)

    def add_word(self, word: Any) -> None:
        self.add(word)

    def push_word(self, word: Any) -> None:
        self.add(word)

    @property
    def recent_words(self) -> List[str]:
        return self.get()

    @property
    def words(self) -> List[str]:
        return self.get()


# aliases
WordBuffer = SlidingWindowBuffer
Buffer = SlidingWindowBuffer
SlidingBuffer = SlidingWindowBuffer
RecentWordsBuffer = SlidingWindowBuffer
WordWindow = SlidingWindowBuffer


def dedupe_immediate_repeats(words: Iterable[Any]) -> List[str]:
    return SlidingWindowBuffer.dedupe_immediate(words)


def dedupe_repeats(words: Iterable[Any]) -> List[str]:
    return SlidingWindowBuffer.dedupe_immediate(words)


def sliding_window(words: Iterable[Any], size: int = 10) -> List[str]:
    buf = SlidingWindowBuffer(size=size)
    buf.extend(words)
    return buf.get()
