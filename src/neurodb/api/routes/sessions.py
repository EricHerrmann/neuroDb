"""GET /api/sessions route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.sessions import ChatSessionItem
from neurodb.db import get_session
from neurodb.schema import ChatSession

router = APIRouter()


@router.get("/sessions", response_model=list[ChatSessionItem])
def get_sessions(engine: Engine = Depends(get_engine)) -> list[ChatSessionItem]:
    with get_session(engine) as session:
        rows = (
            session.query(ChatSession)
            .order_by(ChatSession.started_at.desc())
            .all()
        )
        return [ChatSessionItem.model_validate(r) for r in rows]
