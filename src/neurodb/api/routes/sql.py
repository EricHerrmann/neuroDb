"""POST /api/sql/execute route."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, text

from neurodb.api.deps import get_engine
from neurodb.api.schemas.sql import SqlQuery, SqlResult

router = APIRouter()


@router.post("/execute", response_model=SqlResult)
def execute_sql(body: SqlQuery, engine: Engine = Depends(get_engine)) -> SqlResult:
    try:
        with engine.connect() as conn:
            result = conn.execute(text(body.sql))
            rows = result.fetchmany(500)
            columns = list(result.keys())
        return SqlResult(columns=columns, rows=[list(row) for row in rows], row_count=len(rows))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
