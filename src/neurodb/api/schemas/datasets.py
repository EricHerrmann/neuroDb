from __future__ import annotations

from pydantic import BaseModel


class DatasetItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source: str
    source_id: str
    title: str | None = None
    modality: str | None = None
    n_subjects: int | None = None
