from __future__ import annotations

from pydantic import BaseModel, Field


class PaperGroupingLink(BaseModel):
    grouping_id: int
    grouping_type: str
    grouping_name: str
    status: str


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
    abstract: str | None = None
    year: int | None = None
    warnings: list[str] = []
    grouping_links: list[PaperGroupingLink] = Field(default_factory=list)
