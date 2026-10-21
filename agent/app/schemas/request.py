from typing import Any, List, Optional, Union

from pydantic import BaseModel, Field, field_validator


class WordInput(BaseModel):
    word: str
    confidence: Optional[float] = 1.0
    alternatives: List[str] = Field(default_factory=list)

    @field_validator("word")
    @classmethod
    def _strip(cls, v: str) -> str:
        return v.strip()


# alias names
SignWord = WordInput
WordItem = WordInput


class SentenceRequest(BaseModel):
    words: List[Union[str, WordInput, dict]] = Field(default_factory=list)
    language: Optional[str] = None

    @field_validator("words", mode="before")
    @classmethod
    def _normalize(cls, v: Any) -> List[Any]:
        if v is None:
            return []
        return list(v)

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