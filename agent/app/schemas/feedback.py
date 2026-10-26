from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FeedbackCreate(BaseModel):
    request_id: Optional[str] = None
    words: List[str] = Field(default_factory=list)
    original_sentence: Optional[str] = None
    corrected_sentence: Optional[str] = None
    rating: Optional[Any] = None
    comment: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class FeedbackRecord(BaseModel):
    id: int
    request_id: Optional[str] = None
    words: List[str] = Field(default_factory=list)
    original_sentence: Optional[str] = None
    corrected_sentence: Optional[str] = None
    rating: Optional[Any] = None
    comment: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: str


class FeedbackResponse(BaseModel):
    status: str = "ok"
    id: int
    created_at: str


class FeedbackStats(BaseModel):
    total: int = 0
    average_rating: Optional[float] = None
    ratings: Dict[str, int] = Field(default_factory=dict)
    with_correction: int = 0