"""Vocabulary management service."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class VocabularyEntry(BaseModel):
    word: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# aliases
VocabularyWord = VocabularyEntry
VocabEntry = VocabularyEntry


def _normalize_vocab(vocabulary: Any) -> Any:
    if vocabulary is None:
        return {"words": []}
    return vocabulary


class VocabularyService:
    def __init__(
        self,
        agent: Any = None,
        vocabulary: Any = None,
        path: Optional[str] = None,
        storage_path: Optional[str] = None,
        **kwargs: Any,
    ) -> None:
        from app.config import settings

        self.agent = agent
        self.path = path or storage_path or getattr(settings, "vocabulary_path", "") or ""
        if not self.path:
            try:
                from app.core.agent import PROMPTS_DIR

                default_path = PROMPTS_DIR / "vocabulary.json"
                if default_path.exists():
                    self.path = str(default_path)
            except Exception:
                pass
        if vocabulary is not None:
            self.vocabulary = vocabulary
        elif agent is not None and getattr(agent, "vocabulary", None) is not None:
            self.vocabulary = agent.vocabulary
        else:
            self.vocabulary = {"words": []}
        if (
            self.path
            and (vocabulary is None)
            and (agent is None or getattr(agent, "vocabulary", None) is None)
        ):
            try:
                self.load(self.path)
            except Exception:
                pass
        self._lock = threading.RLock()
        if self.path:
            try:
                self.load(self.path)
            except Exception:
                pass

    # ------------------------------------------------------------------ #
    # Read
    # ------------------------------------------------------------------ #
    def get_vocabulary(self) -> Any:
        return self.vocabulary

    def list(self) -> List[str]:
        return self.words()

    def words(self) -> List[str]:
        try:
            from app.core.confidence import vocabulary_words as _vw

            return _vw(self.vocabulary)
        except Exception:
            pass
        if isinstance(self.vocabulary, dict):
            if "words" in self.vocabulary and isinstance(self.vocabulary["words"], list):
                out = []
                for item in self.vocabulary["words"]:
                    if isinstance(item, str):
                        out.append(item)
                    elif isinstance(item, dict):
                        w = item.get("word") or item.get("text")
                        if w:
                            out.append(str(w))
                return out
            return [str(k) for k in self.vocabulary.keys()]
        if isinstance(self.vocabulary, (list, tuple, set)):
            return [str(x) for x in self.vocabulary]
        return []

    def contains(self, word: str) -> bool:
        return str(word).strip().lower() in {w.lower() for w in self.words()}

    def get(self, word: str) -> Optional[VocabularyEntry]:
        for w in self._entries():
            if str(w.get("word", "")).lower() == str(word).strip().lower():
                return VocabularyEntry(
                    **{k: v for k, v in w.items() if k in {"word", "tags", "metadata"}}
                )
        return None

    def _entries(self) -> List[Dict[str, Any]]:
        if isinstance(self.vocabulary, dict) and isinstance(self.vocabulary.get("words"), list):
            out = []
            for item in self.vocabulary["words"]:
                if isinstance(item, str):
                    out.append({"word": item, "tags": [], "metadata": {}})
                elif isinstance(item, dict):
                    out.append(dict(item))
            return out
        return [{"word": w, "tags": [], "metadata": {}} for w in self.words()]

    # ------------------------------------------------------------------ #
    # Write
    # ------------------------------------------------------------------ #
    def add(
        self,
        word: Any = None,
        tags: Any = None,
        metadata: Any = None,
        words: Any = None,
        **kwargs: Any,
    ) -> Any:
        # support add(word=...) or add({"word":...}) or add([...])
        targets = []
        if words is not None:
            targets.extend(list(words) if not isinstance(words, str) else [words])
        if word is not None:
            if isinstance(word, (list, tuple, set)):
                targets.extend(list(word))
            else:
                targets.append(word)
        if not targets and kwargs:
            # maybe a dict passed as first positional
            pass
        # handle dict payloads
        dicts = []
        plain = []
        for t in targets:
            if isinstance(t, dict):
                dicts.append(t)
            else:
                plain.append(t)
        added = []
        with self._lock:
            entries = self._entries()
            existing = {e.get("word", "").lower(): e for e in entries}
            for d in dicts:
                w = d.get("word") or d.get("text") or d.get("value")
                if not w:
                    continue
                tgs = d.get("tags", tags if tags is not None else [])
                meta = d.get("metadata", metadata if metadata is not None else {})
                if str(w).lower() in existing:
                    existing[str(w).lower()]["tags"] = tgs
                    existing[str(w).lower()]["metadata"] = meta
                else:
                    entries.append(
                        {
                            "word": str(w).strip(),
                            "tags": list(tgs or []),
                            "metadata": dict(meta or {}),
                        }
                    )
                    existing[str(w).lower()] = entries[-1]
                added.append(str(w).strip())
            for w in plain:
                s = str(w).strip()
                if not s:
                    continue
                if s.lower() in existing:
                    if tags is not None:
                        existing[s.lower()]["tags"] = list(tags or [])
                    if metadata is not None:
                        existing[s.lower()]["metadata"] = dict(metadata or {})
                else:
                    entries.append(
                        {"word": s, "tags": list(tags or []), "metadata": dict(metadata or {})}
                    )
                    existing[s.lower()] = entries[-1]
                added.append(s)
            # write back
            if isinstance(self.vocabulary, dict) and "words" in self.vocabulary:
                self.vocabulary["words"] = entries
            else:
                self.vocabulary = {"words": entries}
            self._sync_agent()
        return added if len(added) != 1 else added[0]

    def remove(self, word: Any = None, words: Any = None, **kwargs: Any) -> bool:
        targets = []
        if words is not None:
            targets.extend(list(words) if not isinstance(words, str) else [words])
        if word is not None:
            if isinstance(word, (list, tuple, set)):
                targets.extend(list(word))
            else:
                targets.append(word)
        if not targets and kwargs.get("word") is not None:
            targets.append(kwargs.get("word"))
        removed_any = False
        with self._lock:
            if isinstance(self.vocabulary, dict) and isinstance(self.vocabulary.get("words"), list):
                before = len(self.vocabulary["words"])
                target_set = {str(w).strip().lower() for w in targets}
                self.vocabulary["words"] = [
                    item
                    for item in self.vocabulary["words"]
                    if (item if isinstance(item, str) else item.get("word", "")).lower()
                    not in target_set
                ]
                removed_any = len(self.vocabulary["words"]) < before
            self._sync_agent()
        return removed_any

    def delete(self, *args, **kwargs):
        return self.remove(*args, **kwargs)

    def update(self, word: str, tags: Any = None, metadata: Any = None, **kwargs: Any) -> bool:
        return self.add(word=word, tags=tags, metadata=metadata, **kwargs) is not None

    def import_vocabulary(
        self, data: Any = None, path: Optional[str] = None, replace: bool = False, **kwargs: Any
    ) -> int:
        if path:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        if data is None:
            data = kwargs.get("vocabulary", kwargs.get("data"))
        if replace:
            if isinstance(data, dict):
                self.vocabulary = {"words": list(data.get("words", []))}
            elif isinstance(data, list):
                self.vocabulary = {"words": list(data)}
            self._sync_agent()
            return len(self.words())
        # merge
        before = len(self.words())
        if isinstance(data, dict):
            self.add(words=data.get("words", []))
        elif isinstance(data, list):
            self.add(words=data)
        else:
            self.add(words=[data])
        return len(self.words()) - before

    def import_(self, *args, **kwargs):
        return self.import_vocabulary(*args, **kwargs)

    def export(self, format: str = "json") -> Any:
        if format in {"json", "dict"}:
            return {"words": self._entries()}
        if format in {"list", "words"}:
            return self.words()
        return self.vocabulary

    def reload(self, path: Optional[str] = None) -> None:
        p = path or self.path
        if p:
            self.load(p)

    def load(self, path: str) -> None:
        p = Path(path)
        data = json.loads(p.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            self.vocabulary = data
        elif isinstance(data, list):
            self.vocabulary = {"words": data}
        self._sync_agent()

    def save(self, path: Optional[str] = None) -> None:
        p = Path(path or self.path)
        if not p:
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(self.vocabulary, indent=2, ensure_ascii=False), encoding="utf-8")

    def reset(self) -> None:
        self.vocabulary = {"words": []}
        self._sync_agent()

    def clear(self) -> None:
        self.reset()

    def stats(self) -> Dict[str, Any]:
        return {"total": len(self.words()), "words": self.words()}

    def _sync_agent(self) -> None:
        if self.agent is not None:
            try:
                self.agent.vocabulary = self.vocabulary
            except Exception:
                pass


_DEFAULT_VOCABULARY_SERVICE: Optional[VocabularyService] = None


def get_vocabulary_service() -> VocabularyService:
    global _DEFAULT_VOCABULARY_SERVICE
    if _DEFAULT_VOCABULARY_SERVICE is None:
        _DEFAULT_VOCABULARY_SERVICE = VocabularyService()
    return _DEFAULT_VOCABULARY_SERVICE


def reset_vocabulary_store() -> None:
    get_vocabulary_service().reset()


VocabularyStore = VocabularyService
VocabService = VocabularyService

# extra aliases
VocabularyService.get_all = VocabularyService.words
VocabularyService.list_words = VocabularyService.words
VocabularyService.get_words = VocabularyService.words
VocabularyService.add_word = VocabularyService.add
VocabularyService.remove_word = VocabularyService.remove
VocabularyService.delete_word = VocabularyService.remove
VocabularyService.has = VocabularyService.contains
