from __future__ import annotations
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class MetricsResponse(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    snapshot_at: datetime | None = None
    approved_sources_count: int | None = None
    research_questions_count: int | None = None
    research_hypotheses_count: int | None = None
    chat_sessions_count: int | None = None
    snapshot_id: int | None = None


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
