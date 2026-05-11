from __future__ import annotations

from pydantic import BaseModel


class LearningSourceItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source_type: str
    source_key: str
    display_name: str
    added_by: str
    added_at: str
