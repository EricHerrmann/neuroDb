"""GET /api/datasets and dataset import routes."""
from __future__ import annotations

import json as _json
import logging
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import Engine, select

from neurodb.api.deps import get_engine, get_task_store
from neurodb.api.schemas.datasets import DatasetItem
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.query import search_datasets
from neurodb.schema import DatasetIndex, DatasetResearchPacket, ImportQueue

logger = logging.getLogger(__name__)

router = APIRouter()


def _packet_fields(session, dataset_id: int) -> tuple[str | None, str | None]:
    """Return (usefulness_state, missing_context) for a dataset, or (None, None) if no packet."""
    packet = session.execute(
        select(DatasetResearchPacket).where(
            DatasetResearchPacket.index_id == dataset_id
        )
    ).scalar_one_or_none()
    if packet is None:
        return None, None
    missing_list: list[str] = []
    try:
        missing_list = _json.loads(packet.missing_context_json or "[]")
    except Exception:
        pass
    return packet.usefulness_state, ", ".join(missing_list)


@router.get("", response_model=list[DatasetItem])
def get_datasets(
    keyword: str | None = None,
    modality: str | None = None,
    engine: Engine = Depends(get_engine),
) -> list[DatasetItem]:
    with get_session(engine) as session:
        try:
            rows = search_datasets(
                session,
                keyword=keyword,
                modality=None if modality in {None, "", "all"} else modality,
            )
            items = []
            for row in rows:
                usefulness_state, missing_context = _packet_fields(session, row["id"])
                items.append(
                    DatasetItem(
                        **dict(row),
                        usefulness_state=usefulness_state,
                        missing_context=missing_context,
                    )
                )
            return items
        except Exception:
            query = session.query(DatasetIndex)
            if keyword:
                query = query.filter(DatasetIndex.source_id.ilike(f"%{keyword}%"))
            rows = query.order_by(DatasetIndex.source, DatasetIndex.source_id).limit(200).all()
            if modality not in {None, "", "all"}:
                return []
            items = []
            for row in rows:
                usefulness_state, missing_context = _packet_fields(session, row.id)
                item = DatasetItem.model_validate(row)
                item.usefulness_state = usefulness_state
                item.missing_context = missing_context
                items.append(item)
            return items


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
            return
        # Best-effort: mark the import queue row resolved.
        # Failure here must not override the successful task status.
        try:
            resolved_at = datetime.now(UTC).isoformat()
            with get_session(engine) as session:
                queue_row = session.execute(
                    select(ImportQueue).where(
                        ImportQueue.source == source,
                        ImportQueue.source_id == source_id,
                        ImportQueue.status == "pending",
                    )
                ).scalars().first()
                if queue_row is not None:
                    queue_row.status = "imported"
                    queue_row.resolved_at = resolved_at
        except Exception:
            logger.exception(
                "Failed to update ImportQueue status for %s:%s", source, source_id
            )

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
