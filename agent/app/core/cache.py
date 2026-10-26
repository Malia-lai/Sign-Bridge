"""Simple LRU cache for sentence results."""

from collections import OrderedDict
from typing import Any, Callable, Dict, Optional


class LRUCache:
    def __init__(self, capacity: int = 128):
        self.capacity = max(1, int(capacity))
        self._store: OrderedDict = OrderedDict()
        self.hits = 0
        self.misses = 0
        self.evictions = 0

    def get(self, key: Any) -> Optional[Any]:
        if key in self._store:
            self.hits += 1
            self._store.move_to_end(key)
            return self._store[key]
        self.misses += 1
        return None

    def set(self, key: Any, value: Any) -> None:
        if key in self._store:
            self._store.move_to_end(key)
        self._store[key] = value
        while len(self._store) > self.capacity:
            self._store.popitem(last=False)
            self.evictions += 1

    def __contains__(self, key: Any) -> bool:
        return key in self._store

    def __len__(self) -> int:
        return len(self._store)

    def clear(self) -> None:
        self._store.clear()

    def stats(self) -> Dict[str, Any]:
        return {
            "size": len(self._store),
            "capacity": self.capacity,
            "maxsize": self.capacity,
            "currsize": len(self._store),
            "hits": self.hits,
            "misses": self.misses,
            "evictions": self.evictions,
        }

    def cache_info(self):
        # mimic functools.lru_cache cache_info namedtuple-ish
        class Info:
            pass
        info = Info()
        info.hits = self.hits
        info.misses = self.misses
        info.maxsize = self.capacity
        info.currsize = len(self._store)
        return info

    # aliases
    def info(self):
        return self.stats()

    def cache_info(self):
        return self.stats()


class SentenceCache(LRUCache):
    def make_key(self, words: Any, language: Any = None, **kwargs: Any) -> tuple:
        try:
            w = tuple(str(x).strip() for x in (words or []))
        except TypeError:
            w = (str(words),)
        return (w, language)


# aliases
SentenceLRUCache = SentenceCache
LRUSentenceCache = SentenceCache