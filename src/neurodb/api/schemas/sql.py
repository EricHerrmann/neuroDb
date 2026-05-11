from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class SqlQuery(BaseModel):
    sql: str


class SqlResult(BaseModel):
    columns: list[str]
    rows: list[list[Any]]
    row_count: int
