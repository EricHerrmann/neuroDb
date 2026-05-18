from __future__ import annotations

from typing import Any

from pydantic import BaseModel


class LearningSourceItem(BaseModel):
    model_config = {"from_attributes": True}

    id: int
    source_type: str
    source_key: str
    display_name: str
    added_by: str
    added_at: str
    content_json: dict[str, Any] | None = None
