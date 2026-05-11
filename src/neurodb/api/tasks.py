"""In-memory background task records for the API."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class TaskRecord:
    task_id: str
    status: Literal["running", "done", "failed"]
    result: dict | None
    error: str | None
    started_at: str
    timeout_at: str
