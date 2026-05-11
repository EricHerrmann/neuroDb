from __future__ import annotations

from pydantic import BaseModel


class DatasetItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    source_id: str
