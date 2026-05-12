from __future__ import annotations
from datetime import datetime

from pydantic import BaseModel


class ResearchQuestion(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    question: str
    status: str
    topic_context: str | None = None
    created_at: datetime | None = None


class Hypothesis(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    mechanism: str | None = None
    status: str
    created_at: datetime | None = None


class HypothesisReviewItem(BaseModel):
    id: int
    hypothesis_id: int
    model: str
    critique_text: str
    unsupported_claims: list[object]
    missing_confounds: list[object]
    suggested_revisions: str
    status: str
    created_at: datetime | None = None
