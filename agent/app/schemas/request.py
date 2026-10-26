from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator

from app.config import settings


class WordInput(BaseModel):
    word: str
    confidence: Optional[float] = 1.0
    alternatives: List[str] = Field(default_factory=list)

    @field_validator("word")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()

    @field_validator("confidence")
    @classmethod
    def _clamp_conf(cls, v: Optional[float]) -> float:
        if v is None:
            return 1.0
        try:
            f = float(v)
        except (TypeError, ValueError):
            return 1.0
        return max(0.0, min(1.0, f))


# alias names
SignWord = WordInput
WordItem = WordInput


class SentenceRequest(BaseModel):
    words: List[Union[str, WordInput, dict]] = Field(default_factory=list)
    language: Optional[str] = None
    timeout: Optional[float] = None
    max_words: Optional[int] = None

    @field_validator("words", mode="before")
    @classmethod
    def _normalize(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        out = list(v)
        limit = getattr(settings, "max_words", None)
        # per-request max_words not available here; global check below
        return out

    @field_validator("words")
    @classmethod
    def _validate_word_count(cls, v: List[Any]) -> List[Any]:
        limit = getattr(settings, "max_words", 100)
        try:
            limit = int(limit)
        except (TypeError, ValueError):
            limit = 100
        if len(v) > limit:
            raise ValueError(f"Too many words: {len(v)} > {limit}")
        return v

    @field_validator("language")
    @classmethod
    def _validate_language(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError("language must be a string")
        v = v.strip()
        if not v:
            raise ValueError("language cannot be empty")
        if len(v) > 50:
            raise ValueError("language too long")
        supported_raw = getattr(settings, "supported_languages", "") or ""
        supported = [s.strip() for s in supported_raw.split(",") if s.strip()]
        if supported and v not in supported and v.lower() not in [s.lower() for s in supported]:
            raise ValueError(f"Unsupported language: {v}")
        return v

    @field_validator("timeout")
    @classmethod
    def _validate_timeout(cls, v: Optional[float]) -> Optional[float]:
        if v is None:
            return None
        try:
            f = float(v)
        except (TypeError, ValueError):
            raise ValueError("timeout must be a number")
        if f <= 0:
            raise ValueError("timeout must be positive")
        return f

    def normalized_words(self) -> List[str]:
        out = []
        for item in self.words:
            if isinstance(item, str):
                if item.strip():
                    out.append(item.strip())
            elif isinstance(item, WordInput):
                if item.word.strip():
                    out.append(item.word.strip())
            elif isinstance(item, dict):
                w = item.get("word") or item.get("text") or item.get("value")
                if w:
                    out.append(str(w).strip())
        return out

    def word_confidences(self) -> List[float]:
        out = []
        for item in self.words:
            if isinstance(item, WordInput):
                out.append(float(item.confidence if item.confidence is not None else 1.0))
            elif isinstance(item, dict):
                c = item.get("confidence", item.get("score", 1.0))
                try:
                    out.append(float(c))
                except (TypeError, ValueError):
                    out.append(1.0)
            else:
                out.append(1.0)
        return out

    def word_alternatives(self) -> List[List[str]]:
        out = []
        for item in self.words:
            if isinstance(item, WordInput):
                out.append(list(item.alternatives or []))
            elif isinstance(item, dict):
                out.append(list(item.get("alternatives") or []))
            else:
                out.append([])
        return out