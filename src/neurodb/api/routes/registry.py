"""GET, POST, and DELETE /api/registry routes."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError

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


@router.delete("/{item_id}", status_code=204)
def delete_registry_entry(item_id: int, engine: Engine = Depends(get_engine)) -> None:
    with get_session(engine) as session:
        row = session.get(LearningSource, item_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"LearningSource {item_id} not found")
        session.delete(row)


class CreateRegistryRequest(BaseModel):
    source_type: str
    source_key: str
    display_name: str
    topics: list[str] | None = None


@router.post("", response_model=LearningSourceItem)
def create_registry_entry(
    body: CreateRegistryRequest,
    engine: Engine = Depends(get_engine),
) -> LearningSourceItem:
    content_json = json.dumps({"topics": body.topics}) if body.topics else None
    with get_session(engine) as session:
        source = LearningSource(
            source_type=body.source_type,
            source_key=body.source_key,
            display_name=body.display_name,
            content_json=content_json,
            added_by="user",
            added_at=datetime.now(UTC).isoformat(),
        )
        session.add(source)
        try:
            session.flush()
        except IntegrityError as exc:
            raise HTTPException(status_code=409, detail="source_key already exists") from exc
        return LearningSourceItem.model_validate(source)
