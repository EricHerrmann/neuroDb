"""GET and POST /api/study-log routes."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.study import list_tags, tag_dataset

router = APIRouter()


@router.get("/study-log", response_model=list[StudyNoteItem])
def get_study_log(engine: Engine = Depends(get_engine)) -> list[StudyNoteItem]:
    with get_session(engine) as session:
        return [StudyNoteItem(**row) for row in list_tags(session)]


class CreateStudyNoteRequest(BaseModel):
    source: str
    source_id: str
    concept_tag: str
    section_ref: str | None = None
    note_text: str | None = None


@router.post("/study-log", response_model=StudyNoteItem)
def create_study_note(
    body: CreateStudyNoteRequest,
    engine: Engine = Depends(get_engine),
) -> StudyNoteItem:
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source=body.source,
            source_id=body.source_id,
            concept_tag=body.concept_tag,
            section_ref=body.section_ref,
            note_text=body.note_text,
        )
        if note is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {body.source}:{body.source_id} not in index",
            )
        return StudyNoteItem(
            id=note.id,
            source=body.source,
            source_id=body.source_id,
            concept_tag=note.concept_tag,
            section_ref=note.section_ref,
            note_text=note.note_text,
            tagged_at=note.tagged_at,
        )
