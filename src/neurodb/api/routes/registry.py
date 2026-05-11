"""GET /api/registry route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.registry import LearningSourceItem
from neurodb.db import get_session
from neurodb.schema import LearningSource

router = APIRouter()


@router.get("", response_model=list[LearningSourceItem])
def get_registry(engine: Engine = Depends(get_engine)) -> list[LearningSourceItem]:
    with get_session(engine) as session:
        rows = (
            session.query(LearningSource)
            .order_by(LearningSource.source_type, LearningSource.display_name)
            .all()
        )
        return [LearningSourceItem.model_validate(row) for row in rows]
