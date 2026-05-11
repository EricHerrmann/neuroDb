"""Routes for polling background task state."""
from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException

from neurodb.api.deps import get_task_store
from neurodb.api.tasks import TaskRecord

router = APIRouter()


@router.get("/tasks/{task_id}")
def get_task(task_id: str, tasks: dict[str, TaskRecord] = Depends(get_task_store)) -> dict:
    record = tasks.get(task_id)
    if record is None:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")

    if record.status == "running":
        timeout_at = datetime.fromisoformat(record.timeout_at)
        if datetime.now(UTC) > timeout_at:
            return {
                "task_id": record.task_id,
                "status": "failed",
                "result": None,
                "error": "Timed out",
                "started_at": record.started_at,
                "timeout_at": record.timeout_at,
            }

    return {
        "task_id": record.task_id,
        "status": record.status,
        "result": record.result,
        "error": record.error,
        "started_at": record.started_at,
        "timeout_at": record.timeout_at,
    }
