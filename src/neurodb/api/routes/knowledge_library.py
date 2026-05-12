"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations

import logging
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_knowledge_store
from neurodb.api.schemas.knowledge_library import KnowledgeSourceItem
from neurodb.db import get_session
from neurodb.schema import KnowledgeSource

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("", response_model=list[KnowledgeSourceItem])
def get_knowledge_library(
    status: str = "all",
    engine: Engine = Depends(get_engine),
) -> list[KnowledgeSourceItem]:
    with get_session(engine) as session:
        query = session.query(KnowledgeSource)
        if status != "all":
            query = query.filter(KnowledgeSource.status == status)
        rows = query.order_by(KnowledgeSource.queued_at.desc()).all()
        return [KnowledgeSourceItem.model_validate(row) for row in rows]


@router.post("/{source_id}/approve", response_model=KnowledgeSourceItem)
def approve_source(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
) -> KnowledgeSourceItem:
    reviewed_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"KnowledgeSource {source_id} not found"
            )
        row.status = "approved"
        row.reviewed_at = reviewed_at
        session.flush()
        item = KnowledgeSourceItem.model_validate(row)
        # Capture scalar values before the session closes — ORM objects are detached after commit
        _id, _title, _doi, _topic, _summary = (
            row.id, row.title, row.doi, row.topic_context, row.summary
        )
    try:
        chroma_id = knowledge_store.add_summary(
            source_id=_id,
            title=_title,
            doi=_doi,
            topic_context=_topic,
            summary=_summary or "",
        )
        with get_session(engine) as session:
            row = session.get(KnowledgeSource, source_id)
            if row is not None:
                row.chroma_id = chroma_id
    except Exception as exc:
        logger.exception("ChromaDB indexing failed for source %d", source_id)
        warnings.append(f"ChromaDB indexing failed: {exc}")
    return item.model_copy(update={"warnings": warnings})


@router.post("/{source_id}/reject", response_model=KnowledgeSourceItem)
def reject_source(source_id: int, engine: Engine = Depends(get_engine)) -> KnowledgeSourceItem:
    return _set_status(source_id, "rejected", engine)


def _set_status(source_id: int, status: str, engine: Engine) -> KnowledgeSourceItem:
    reviewed_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(KnowledgeSource, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"KnowledgeSource {source_id} not found"
            )
        row.status = status
        row.reviewed_at = reviewed_at
        session.flush()
        return KnowledgeSourceItem.model_validate(row)
