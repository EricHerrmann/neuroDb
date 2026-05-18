"""GET and POST /api/study-log routes."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, select

from neurodb.api.deps import get_engine, get_vector_store
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.embed_hooks import embed_note, remove_note
from neurodb.schema import DatasetIndex, StudyNote
from neurodb.study import delete_tag, list_tags, tag_dataset

logger = logging.getLogger(__name__)

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


class DeleteStudyNoteResponse(BaseModel):
    deleted: bool
    warnings: list[str] = []


def _embed_note_with_warning(
    vector_store,
    note_id: int,
    source: str,
    source_id: str,
    concept_tag: str,
    section_ref: str | None,
    note_text: str | None,
) -> list[str]:
    try:
        embed_note(
            vector_store, note_id, source, source_id,
            concept_tag, section_ref, note_text,
        )
    except Exception as exc:
        logger.exception("embed_note failed for note %d", note_id)
        return [f"Vector embedding failed: {exc}"]
    return []


@router.post("/study-log", response_model=StudyNoteItem)
def create_study_note(
    body: CreateStudyNoteRequest,
    engine: Engine = Depends(get_engine),
    vector_store=Depends(get_vector_store),
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
        item = StudyNoteItem(
            id=note.id,
            source=body.source,
            source_id=body.source_id,
            concept_tag=note.concept_tag,
            section_ref=note.section_ref,
            note_text=note.note_text,
            tagged_at=note.tagged_at,
        )
        note_id = note.id  # capture before session closes — attributes expire on commit
    warnings = _embed_note_with_warning(
        vector_store,
        note_id,
        body.source,
        body.source_id,
        body.concept_tag,
        body.section_ref,
        body.note_text,
    )
    return item.model_copy(update={"warnings": warnings})


@router.patch("/study-log/{note_id}", response_model=StudyNoteItem)
def update_study_note(
    note_id: int,
    body: CreateStudyNoteRequest,
    engine: Engine = Depends(get_engine),
    vector_store=Depends(get_vector_store),
) -> StudyNoteItem:
    with get_session(engine) as session:
        note = session.get(StudyNote, note_id)
        if note is None:
            raise HTTPException(status_code=404, detail=f"StudyNote {note_id} not found")
        idx = session.execute(
            select(DatasetIndex).where(
                DatasetIndex.source == body.source,
                DatasetIndex.source_id == body.source_id,
            )
        ).scalar_one_or_none()
        if idx is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {body.source}:{body.source_id} not in index",
            )
        note.index_id = idx.id
        note.concept_tag = body.concept_tag
        note.section_ref = body.section_ref
        note.note_text = body.note_text
        session.flush()
        item = StudyNoteItem(
            id=note.id,
            source=idx.source,
            source_id=idx.source_id,
            concept_tag=note.concept_tag,
            section_ref=note.section_ref,
            note_text=note.note_text,
            tagged_at=note.tagged_at,
        )

    warnings = _embed_note_with_warning(
        vector_store,
        note_id,
        body.source,
        body.source_id,
        body.concept_tag,
        body.section_ref,
        body.note_text,
    )
    return item.model_copy(update={"warnings": warnings})


@router.delete("/study-log/{note_id}", response_model=DeleteStudyNoteResponse)
def delete_study_note(
    note_id: int,
    engine: Engine = Depends(get_engine),
    vector_store=Depends(get_vector_store),
) -> DeleteStudyNoteResponse:
    with get_session(engine) as session:
        deleted = delete_tag(session, note_id)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"StudyNote {note_id} not found")

    warnings: list[str] = []
    try:
        remove_note(vector_store, note_id)
    except Exception as exc:
        logger.exception("remove_note failed for note %d", note_id)
        warnings.append(f"Vector deindex failed: {exc}")
    return DeleteStudyNoteResponse(deleted=True, warnings=warnings)
