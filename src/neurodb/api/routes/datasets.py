"""GET /api/datasets and dataset import routes."""
from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, select

from neurodb.api.deps import get_engine, get_task_store
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.api.tasks import TaskRecord
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


@router.post("/{source}/{source_id}/import")
def import_dataset(
    source: str,
    source_id: str,
    engine: Engine = Depends(get_engine),
    tasks: dict[str, TaskRecord] = Depends(get_task_store),
) -> dict[str, str]:
    with get_session(engine) as session:
        row = session.execute(
            select(DatasetIndex).where(
                DatasetIndex.source == source,
                DatasetIndex.source_id == source_id,
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"Dataset {source}:{source_id} not in index",
            )

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    tasks[task_id] = TaskRecord(
        task_id=task_id,
        status="running",
        result=None,
        error=None,
        started_at=now.isoformat(),
        timeout_at=(now + timedelta(seconds=180)).isoformat(),
    )

    def run() -> None:
        try:
            _ingest_dataset(source, source_id, engine)
            tasks[task_id].status = "done"
            tasks[task_id].result = {"imported": True}
        except Exception as exc:
            tasks[task_id].status = "failed"
            tasks[task_id].error = str(exc)[:400]

    threading.Thread(target=run, daemon=True).start()
    return {"task_id": task_id}


def _ingest_dataset(source: str, source_id: str, engine: Engine) -> None:
    from neurodb.connectors.dandi import DandiConnector
    from neurodb.connectors.neurovault import NeuroVaultConnector
    from neurodb.connectors.openneuro import OpenNeuroConnector
    from neurodb.provenance import run_ingest

    connector_map = {
        "openneuro": OpenNeuroConnector,
        "dandi": DandiConnector,
        "neurovault": NeuroVaultConnector,
    }
    connector_cls = connector_map.get(source)
    if connector_cls is None:
        raise ValueError(f"Unknown source: {source}")
    run_ingest(engine=engine, connector=connector_cls(), dataset_ids=[source_id])
