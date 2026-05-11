"""GET /api/study-log route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.study_log import StudyNoteItem
from neurodb.db import get_session
from neurodb.study import list_tags

router = APIRouter()


@router.get("/study-log", response_model=list[StudyNoteItem])
def get_study_log(engine: Engine = Depends(get_engine)) -> list[StudyNoteItem]:
    with get_session(engine) as session:
        return [StudyNoteItem(**row) for row in list_tags(session)]
