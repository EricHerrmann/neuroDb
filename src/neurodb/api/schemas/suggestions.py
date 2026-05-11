from __future__ import annotations

from pydantic import BaseModel


class ImportQueueItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    source_id: str
    title: str | None = None
    reason: str | None = None
    chapter_ref: str | None = None
    status: str
    suggested_at: str


class SourceSuggestionItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    suggestion_type: str
    reference: str | None = None
    display_name: str | None = None
    reason: str | None = None
    status: str
    suggested_at: str


class SuggestionsResponse(BaseModel):
    import_queue: list[ImportQueueItem]
    source_suggestions: list[SourceSuggestionItem]
