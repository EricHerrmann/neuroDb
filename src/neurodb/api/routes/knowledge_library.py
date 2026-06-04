"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations

import logging
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, text

from neurodb.api.deps import get_engine, get_knowledge_store, get_task_store
from neurodb.api.schemas.knowledge_library import PaperItem
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.schema import (
    Claim,
    DatasetPacketPaper,
    EvidenceLink,
    GroupingLink,
    Paper,
    StudyNote,
)

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
        if status == "all":
            query = query.filter(Paper.status != "removed")
        else:
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
    item = _update_paper_fields(
        source_id,
        engine,
        status="approved",
        reviewed_at=reviewed_at,
    )
    _id, _title, _doi, _topic, _summary = (
        item.id, item.title, item.doi, item.topic_context, item.summary
    )
    try:
        chroma_id = knowledge_store.add_summary(
            source_id=_id,
            title=_title,
            doi=_doi,
            topic_context=_topic,
            summary=_summary or "",
        )
        _update_paper_fields(source_id, engine, chroma_id=chroma_id)
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


@router.post("/{source_id}/remove", response_model=PaperItem)
def remove_source(
    source_id: int,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
) -> PaperItem:
    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        was_approved = row.status == "approved"
        chroma_id = row.chroma_id

    item = _update_paper_fields(source_id, engine, status="removed")

    if was_approved and chroma_id:
        try:
            knowledge_store.remove_summary(source_id)
        except Exception:
            logger.exception("ChromaDB removal failed for source %d", source_id)

    return item


def _set_status(source_id: int, status: str, engine: Engine) -> PaperItem:
    reviewed_at = datetime.now(UTC).isoformat()
    return _update_paper_fields(source_id, engine, status=status, reviewed_at=reviewed_at)


def _approve_with_summary(source_id: int, engine: Engine, knowledge_store) -> dict:
    reviewed_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise ValueError(f"Paper {source_id} not found")
        summary = _generate_summary(row, engine)
    item = _update_paper_fields(
        source_id,
        engine,
        status="approved",
        reviewed_at=reviewed_at,
        summary=summary,
    )
    values = {
        "id": item.id,
        "title": item.title,
        "doi": item.doi,
        "topic_context": item.topic_context,
        "summary": item.summary or "",
    }

    chroma_id = knowledge_store.add_summary(
        source_id=values["id"],
        title=values["title"],
        doi=values["doi"],
        topic_context=values["topic_context"],
        summary=values["summary"],
    )
    _update_paper_fields(source_id, engine, chroma_id=chroma_id)
    return {"approved": True, "source_id": source_id, "chroma_id": chroma_id}


def _update_paper_fields(source_id: int, engine: Engine, **fields) -> PaperItem:
    if not fields:
        with get_session(engine) as session:
            row = _get_paper_or_404(session, source_id)
            return PaperItem.model_validate(row)
    if engine.dialect.name == "duckdb":
        return _update_paper_fields_duckdb(source_id, engine, **fields)

    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        for field, value in fields.items():
            setattr(row, field, value)
        session.flush()
        return PaperItem.model_validate(row)


def _update_paper_fields_duckdb(source_id: int, engine: Engine, **fields) -> PaperItem:
    """Update Paper fields while preserving paper references.

    DuckDB currently rejects UPDATEs to a parent row when child rows reference it
    through a foreign key, even when the primary key is unchanged. Knowledge
    Library approval commonly touches papers that already have topic/concept or
    claim links, so preserve those rows around the UPDATE.
    """
    with get_session(engine) as session:
        _get_paper_or_404(session, source_id)
        preserved_links = _detach_paper_links(session, source_id)

    try:
        with get_session(engine) as session:
            row = _get_paper_or_404(session, source_id)
            for field, value in fields.items():
                setattr(row, field, value)
            session.flush()
            item = PaperItem.model_validate(row)
    finally:
        with get_session(engine) as session:
            _restore_paper_links(session, preserved_links)
    return item


def _get_paper_or_404(session, source_id: int) -> Paper:
    row = session.get(Paper, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {source_id} not found")
    return row


def _detach_paper_links(session, paper_id: int) -> dict[str, list[dict]]:
    has_claims = _table_has_columns(
        session,
        "claims",
        ["id", "paper_id", "text", "claim_type", "status", "created_at", "updated_at"],
    )
    has_study_notes = _table_has_columns(
        session,
        "study_notes",
        [
            "id",
            "index_id",
            "topic_id",
            "concept_id",
            "paper_id",
            "concept_tag",
            "section_ref",
            "note_text",
            "tagged_at",
        ],
    )
    has_evidence_links = _table_has_columns(
        session,
        "evidence_links",
        [
            "id",
            "hypothesis_id",
            "claim_id",
            "paper_id",
            "packet_id",
            "note_id",
            "link_type",
            "created_at",
        ],
    )
    has_grouping_links = _table_has_columns(
        session,
        "grouping_links",
        ["id", "grouping_id", "anchor_type", "anchor_id", "status", "created_at"],
    )
    claims = session.query(Claim).filter_by(paper_id=paper_id).all() if has_claims else []
    claim_ids = [claim.id for claim in claims]
    study_notes = (
        session.query(StudyNote).filter_by(paper_id=paper_id).all()
        if has_study_notes
        else []
    )
    study_note_ids = [note.id for note in study_notes]
    evidence_links = []
    if has_evidence_links:
        evidence_query = session.query(EvidenceLink).filter(EvidenceLink.paper_id == paper_id)
        if claim_ids:
            evidence_query = evidence_query.union(
                session.query(EvidenceLink).filter(EvidenceLink.claim_id.in_(claim_ids))
            )
        if study_note_ids:
            evidence_query = evidence_query.union(
                session.query(EvidenceLink).filter(EvidenceLink.note_id.in_(study_note_ids))
            )
        evidence_links = evidence_query.all()
    links: dict[str, list[dict]] = {
        "grouping_links": [
            {
                "id": link.id,
                "grouping_id": link.grouping_id,
                "anchor_type": link.anchor_type,
                "anchor_id": link.anchor_id,
                "status": link.status,
                "created_at": link.created_at,
            }
            for link in (
                session.query(GroupingLink)
                .filter_by(anchor_type="paper", anchor_id=paper_id)
                .all()
                if has_grouping_links
                else []
            )
        ],
        "dataset_packet_papers": [
            {"id": link.id, "packet_id": link.packet_id, "paper_id": link.paper_id}
            for link in session.query(DatasetPacketPaper).filter_by(paper_id=paper_id).all()
        ],
        "study_notes": [
            {
                "id": note.id,
                "index_id": note.index_id,
                "topic_id": note.topic_id,
                "concept_id": note.concept_id,
                "paper_id": note.paper_id,
                "concept_tag": note.concept_tag,
                "section_ref": note.section_ref,
                "note_text": note.note_text,
                "tagged_at": note.tagged_at,
            }
            for note in study_notes
        ],
        "claims": [
            {
                "id": claim.id,
                "paper_id": claim.paper_id,
                "text": claim.text,
                "claim_type": claim.claim_type,
                "status": claim.status,
                "created_at": claim.created_at,
                "updated_at": claim.updated_at,
            }
            for claim in claims
        ],
        "evidence_links": [
            {
                "id": link.id,
                "hypothesis_id": link.hypothesis_id,
                "claim_id": link.claim_id,
                "paper_id": link.paper_id,
                "packet_id": link.packet_id,
                "note_id": link.note_id,
                "link_type": link.link_type,
                "created_at": link.created_at,
            }
            for link in evidence_links
        ],
    }
    if has_grouping_links:
        for link in session.query(GroupingLink).filter_by(
            anchor_type="paper", anchor_id=paper_id
        ).all():
            session.delete(link)
    for link in evidence_links:
        session.delete(link)
    for model, enabled in [
        (DatasetPacketPaper, True),
        (StudyNote, has_study_notes),
        (Claim, has_claims),
    ]:
        if not enabled:
            continue
        for link in session.query(model).filter_by(paper_id=paper_id).all():
            session.delete(link)
    session.flush()
    return links


def _restore_paper_links(session, links: dict[str, list[dict]]) -> None:
    for values in links.get("grouping_links", []):
        session.add(GroupingLink(**values))
    for values in links["dataset_packet_papers"]:
        session.add(DatasetPacketPaper(**values))
    for values in links["claims"]:
        session.add(Claim(**values))
    for values in links["study_notes"]:
        session.add(StudyNote(**values))
    for values in links["evidence_links"]:
        session.add(EvidenceLink(**values))
    session.flush()


def _table_has_columns(session, table_name: str, column_names: list[str]) -> bool:
    rows = session.execute(
        text(
            "SELECT column_name FROM information_schema.columns "
            "WHERE table_name = :table_name"
        ),
        {"table_name": table_name},
    ).fetchall()
    actual = {row[0] for row in rows}
    return set(column_names).issubset(actual)


def _generate_summary(row: Paper, engine: Engine | None = None) -> str:
    try:
        from neurodb.config.provider_factory import build_provider_clients
        from neurodb.config.task_router import TaskRouter

        providers = build_provider_clients()
        if not providers:
            return _fallback_summary(row)
        route = TaskRouter(providers).route("summary.knowledge_source", engine=engine)
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
