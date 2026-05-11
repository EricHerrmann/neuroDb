"""GET /api/suggestions and POST dismiss routes."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.suggestions import (
    ImportQueueItem,
    SourceSuggestionItem,
    SuggestionsResponse,
)
from neurodb.db import get_session
from neurodb.schema import ImportQueue, SourceSuggestion

router = APIRouter()


@router.get("", response_model=SuggestionsResponse)
def get_suggestions(engine: Engine = Depends(get_engine)) -> SuggestionsResponse:
    with get_session(engine) as session:
        import_items = (
            session.query(ImportQueue)
            .filter_by(status="pending")
            .order_by(ImportQueue.suggested_at.desc())
            .all()
        )
        source_items = (
            session.query(SourceSuggestion)
            .filter_by(status="pending")
            .order_by(SourceSuggestion.suggested_at.desc())
            .all()
        )
        return SuggestionsResponse(
            import_queue=[ImportQueueItem.model_validate(row) for row in import_items],
            source_suggestions=[SourceSuggestionItem.model_validate(row) for row in source_items],
        )


@router.post("/import-queue/{item_id}/dismiss", status_code=204)
def dismiss_import_item(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    resolved_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(ImportQueue, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"ImportQueue item {item_id} not found")
        row.status = "dismissed"
        row.resolved_at = resolved_at
