from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator

Intent = Literal["request", "question", "greeting", "statement", "emergency"]


class LLMOutput(BaseModel):
    sentence: str
    intent: Intent
    confidence: float
    alternatives: List[str] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


class SentenceResponse(BaseModel):
    sentence: str
    intent: Intent = "statement"
    confidence: float = 0.0
    alternatives: List[str] = Field(default_factory=list)
    fallback: bool = False
    fallback_reason: Optional[str] = None
    fallback_reasons: List[str] = Field(default_factory=list)
    emergency: bool = False
    emergency_fallback: bool = False
    is_emergency: bool = False
    emergency_flag: bool = False
    intent_overridden: bool = False
    overridden: bool = False
    intent_was_overridden: bool = False
    emergency_override: bool = False
    unknown_words: List[str] = Field(default_factory=list)
    raw_words: List[str] = Field(default_factory=list)
    suggestions: List[str] = Field(default_factory=list)
    did_you_mean: List[str] = Field(default_factory=list)
    cached: bool = False
    request_id: Optional[str] = None
    timings: Dict[str, Any] = Field(default_factory=dict)
    stage_timings: Dict[str, Any] = Field(default_factory=dict)
    timing: Dict[str, Any] = Field(default_factory=dict)
    durations: Dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: Optional[float] = None
    duration_ms: Optional[float] = None

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        return max(0.0, min(1.0, float(v)))


# aliases
SentenceResult = SentenceResponse
AgentResponse = SentenceResponse
LLMResult = LLMOutput