from __future__ import annotations

from pydantic import BaseModel


class ChatSessionItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    session_id: str
    inferred_topic: str
    agent_mode: str
    started_at: str
    message_count: int
    summary_preview: str | None = None
    topic_category: str | None = None
