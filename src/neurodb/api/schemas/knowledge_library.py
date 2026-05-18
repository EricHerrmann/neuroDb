from __future__ import annotations

from pydantic import BaseModel


class PaperItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    title: str
    doi: str | None = None
    url: str | None = None
    source_type: str
    topic_context: str
    status: str
    queued_at: str
    reviewed_at: str | None = None
    summary: str | None = None
    warnings: list[str] = []
