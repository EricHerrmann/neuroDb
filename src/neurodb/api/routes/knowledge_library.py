"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_knowledge_store, get_task_store
from neurodb.api.schemas.knowledge_library import PaperItem
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.schema import Paper

logger = logging.getLogger(__name__)

router = APIRouter()


class DuplicateCandidate(BaseModel):
    id: str
    title: str
    doi: str | None = None
    distance: float | None = None


class DuplicateCheckResponse(BaseModel):
    candidates: list[DuplicateCandidate]


@router.get("", response_model=list[PaperItem])
def get_knowledge_library(
    status: str = "all",
    engine: Engine = Depends(get_engine),
) -> list[PaperItem]:
    with get_session(engine) as session:
        query = session.query(Paper)
        if status != "all":
            query = query.filter(Paper.status == status)
        rows = query.order_by(Paper.queued_at.desc()).all()
        return [PaperItem.model_validate(row) for row in rows]


@router.post("/{source_id}/approve", response_model=PaperItem)
def approve_source(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
) -> PaperItem:
    reviewed_at = datetime.now(UTC).isoformat()
    warnings: list[str] = []
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Paper {source_id} not found"
            )
        row.status = "approved"
        row.reviewed_at = reviewed_at
        session.flush()
        item = PaperItem.model_validate(row)
        # Capture scalar values before the session closes — ORM objects are detached after commit
        _id, _title, _doi, _topic, _summary = (
            row.id, row.title, row.doi, row.topic_context, row.summary
        )
    try:
        chroma_id = knowledge_store.add_summary(
            source_id=_id,
            title=_title,
            doi=_doi,
            topic_context=_topic,
            summary=_summary or "",
        )
        with get_session(engine) as session:
            row = session.get(Paper, source_id)
            if row is not None:
                row.chroma_id = chroma_id
    except Exception as exc:
        logger.exception("ChromaDB indexing failed for source %d", source_id)
        warnings.append(f"ChromaDB indexing failed: {exc}")
    return item.model_copy(update={"warnings": warnings})


@router.post("/{source_id}/approve-with-summary")
def approve_source_with_summary(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
    tasks: dict[str, TaskRecord] = Depends(get_task_store),
) -> dict[str, str]:
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Paper {source_id} not found"
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
            result = _approve_with_summary(source_id, engine, knowledge_store)
            tasks[task_id].status = "done"
            tasks[task_id].result = result
        except Exception as exc:
            logger.exception("Knowledge summary task failed for source %d", source_id)
            tasks[task_id].status = "failed"
            tasks[task_id].error = str(exc)[:400]

    threading.Thread(target=run, daemon=True).start()
    return {"task_id": task_id}


@router.get("/{source_id}/duplicates", response_model=DuplicateCheckResponse)
def get_duplicate_candidates(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
) -> DuplicateCheckResponse:
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Paper {source_id} not found"
            )
        query = f"{row.title}\n{row.topic_context}"

    try:
        results = knowledge_store.search(query, n=5)
    except Exception as exc:
        logger.exception("Duplicate check failed for source %d", source_id)
        raise HTTPException(status_code=503, detail=f"Duplicate check failed: {exc}") from exc

    threshold = _dedup_threshold()
    candidates = []
    for result in results:
        distance = result.get("distance")
        if distance is not None and distance > threshold:
            continue
        metadata = result.get("metadata") or {}
        if str(metadata.get("source_id") or "") == str(source_id):
            continue
        candidates.append(DuplicateCandidate(
            id=str(result.get("id") or ""),
            title=str(metadata.get("title") or result.get("id") or "unknown"),
            doi=str(metadata.get("doi") or "") or None,
            distance=distance,
        ))
    return DuplicateCheckResponse(candidates=candidates)


@router.post("/{source_id}/reject", response_model=PaperItem)
def reject_source(source_id: int, engine: Engine = Depends(get_engine)) -> PaperItem:
    return _set_status(source_id, "rejected", engine)


def _set_status(source_id: int, status: str, engine: Engine) -> PaperItem:
    reviewed_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise HTTPException(
                status_code=404, detail=f"Paper {source_id} not found"
            )
        row.status = status
        row.reviewed_at = reviewed_at
        session.flush()
        return PaperItem.model_validate(row)


def _approve_with_summary(source_id: int, engine: Engine, knowledge_store) -> dict:
    reviewed_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise ValueError(f"Paper {source_id} not found")
        summary = _generate_summary(row)
        row.status = "approved"
        row.reviewed_at = reviewed_at
        row.summary = summary
        session.flush()
        values = {
            "id": row.id,
            "title": row.title,
            "doi": row.doi,
            "topic_context": row.topic_context,
            "summary": row.summary or "",
        }

    chroma_id = knowledge_store.add_summary(
        source_id=values["id"],
        title=values["title"],
        doi=values["doi"],
        topic_context=values["topic_context"],
        summary=values["summary"],
    )
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is not None:
            row.chroma_id = chroma_id
    return {"approved": True, "source_id": source_id, "chroma_id": chroma_id}


def _generate_summary(row: Paper) -> str:
    try:
        from neurodb.config.provider_factory import build_provider_clients
        from neurodb.config.task_router import TaskRouter

        providers = build_provider_clients()
        if not providers:
            return _fallback_summary(row)
        route = TaskRouter(providers).route("summary.knowledge_source")
        response = route.model_client.create_message(
            model=route.model_id,
            max_tokens=route.max_tokens,
            system="",
            tools=[],
            messages=[{
                "role": "user",
                "content": (
                    "Create a concise structured neuroscience learning summary for this source.\n"
                    f"Title: {row.title}\n"
                    f"Source type: {row.source_type}\n"
                    f"DOI: {row.doi or 'unknown'}\n"
                    f"URL: {row.url or 'unknown'}\n"
                    f"Topic context: {row.topic_context}\n\n"
                    "Use sections: Key concepts, Relevance to neuroscience, Open questions."
                ),
            }],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
    except Exception as exc:
        logger.exception("Summary generation failed for source %d", row.id)
        return f"{_fallback_summary(row)}\n\nSummary generation note: {exc}"
    return _fallback_summary(row)


def _fallback_summary(row: Paper) -> str:
    return (
        f"Key concepts: {row.title} was queued as a {row.source_type} while discussing "
        f"{row.topic_context}.\n\n"
        "Relevance to neuroscience: This source was approved for future Neuro-Tutor retrieval.\n\n"
        "Open questions: Add a richer model-generated summary when provider access is available."
    )


def _dedup_threshold() -> float:
    raw = os.environ.get("NEURODB_DEDUP_THRESHOLD", "0.15")
    try:
        return float(raw)
    except ValueError:
        return 0.15
