"""GET /api/status route."""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import Engine, inspect

from neurodb.api.deps import get_engine

router = APIRouter()


@router.get("/status")
def get_status(engine: Engine = Depends(get_engine)) -> dict:
    inspector = inspect(engine)
    return {"status": "ok", "db_tables": inspector.get_table_names()}
