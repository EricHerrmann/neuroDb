from __future__ import annotations
from pydantic import BaseModel


class StudyNoteItem(BaseModel):
    id: int
    source: str
    source_id: str
    concept_tag: str
    section_ref: str | None = None
    note_text: str | None = None
    tagged_at: str
    warnings: list[str] = []
