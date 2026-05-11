"""GET /api/datasets route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine

from neurodb.api.deps import get_engine
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.db import get_session
from neurodb.schema import DatasetIndex

router = APIRouter()


@router.get("", response_model=list[DatasetItem])
def get_datasets(
    keyword: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DatasetItem]:
    with get_session(engine) as session:
        query = session.query(DatasetIndex)
        if keyword:
            query = query.filter(DatasetIndex.source_id.ilike(f"%{keyword}%"))
        rows = query.order_by(DatasetIndex.source, DatasetIndex.source_id).limit(200).all()
        return [DatasetItem.model_validate(row) for row in rows]
