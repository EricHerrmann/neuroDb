"""GET /api/knowledge-library and approve/reject routes."""
from __future__ import annotations

import json
import logging
import os
import threading
import uuid
from datetime import UTC, datetime, timedelta

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import Engine, text

from neurodb.api.deps import get_chunk_store, get_engine, get_knowledge_store, get_task_store
from neurodb.api.schemas.knowledge_library import PaperGroupingLink, PaperItem
from neurodb.api.tasks import TaskRecord
from neurodb.chunking import Section, chunk_sections
from neurodb.db import get_session
from neurodb.events import FULL_TEXT_ACQUIRED, emit
from neurodb.full_text_client import AcquireFailure, SuppliedInput, acquire, classify_for_phase2b
from neurodb.fulltext_staging import delete_staging, read_staging
from neurodb.fulltext_types import ParsedArtifact
from neurodb.knowledge_summary import fallback_summary as _fallback_summary
from neurodb.knowledge_summary import summary_prompt as _summary_prompt
from neurodb.metadata_backfill import BackfillResult, backfill_paper_metadata
from neurodb.metadata_lookup import MetadataLookupClient
from neurodb.phase2b import run_acquisition
from neurodb.schema import (
    Claim,
    DatasetPacketPaper,
    EventLog,
    EvidenceLink,
    Grouping,
    GroupingLink,
    Paper,
    PaperChunk,
    PaperFulltextStaging,
    PlanStep,
    StudyNote,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# Sentinel for _paper_item_from_row's `staged` parameter: distinguishes
# "caller wants auto-fetch" from "caller explicitly passed None".
_SENTINEL = object()


class DuplicateCandidate(BaseModel):
    id: str
    title: str
    doi: str | None = None
    distance: float | None = None


class DuplicateCheckResponse(BaseModel):
    candidates: list[DuplicateCandidate]


class AcquireFullTextRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    format: str | None = None
    source_url: str | None = None  # Phase 2b: user-supplied PDF/HTML link
    source_path: str | None = None  # Local library file name (relative to library root)


class FulltextReviewRequest(BaseModel):
    decision: str  # confirm | reject


class RemoveSourceRequest(BaseModel):
    action: str = "delete"  # delete | delete_with_references | replace_references
    replacement_source_id: int | None = None


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
        rows = query.order_by(Paper.normalized_title.asc()).all()
        items = [_paper_item_from_row(row, session, staged=None) for row in rows]
        review_ids = [row.id for row in rows if row.full_text_status == "needs_review"]

    # read_staging opens its own session; do this after the query session closes
    # to avoid nested DuckDB transactions.
    staging_by_id: dict[int, dict | None] = {
        sid: read_staging(engine, sid) for sid in review_ids
    }
    if staging_by_id:
        items = [
            item.model_copy(update={"fulltext_staging": staging_by_id[item.id]})
            if item.id in staging_by_id else item
            for item in items
        ]
    return items


@router.get("/library-files")
def library_files() -> list[dict]:
    from neurodb.library_store import list_library_files, list_library_projects
    return list_library_files() + list_library_projects()


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
            data_tier=item.data_tier,
            year=item.year,
            currency_status=item.currency_status,
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


@router.post("/{source_id}/remove")
def remove_source(
    source_id: int,
    body: RemoveSourceRequest | None = None,
    engine: Engine = Depends(get_engine),
    knowledge_store=Depends(get_knowledge_store),
    chunk_store=Depends(get_chunk_store),
) -> dict:
    body = body or RemoveSourceRequest()
    if body.action not in {"delete", "delete_with_references", "replace_references"}:
        raise HTTPException(status_code=422, detail=f"Unsupported remove action: {body.action}")

    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        title = row.title
        reference_counts = _paper_reference_counts(session, source_id)
        blocker_counts = _external_reference_counts(reference_counts)
        if body.action == "delete" and _reference_total(blocker_counts) > 0:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "paper_has_references",
                    "message": (
                        "This paper is referenced elsewhere in NeuroDb. "
                        "Choose how to handle those references before deleting it."
                    ),
                    "paper_id": source_id,
                    "title": title,
                    "references": reference_counts,
                    "blocking_references": blocker_counts,
                    "available_actions": [
                        "delete_with_references",
                        "replace_references",
                    ],
                },
            )
        if body.action == "replace_references":
            if body.replacement_source_id is None:
                raise HTTPException(
                    status_code=422,
                    detail="replacement_source_id is required for replace_references",
                )
            replacement = session.get(Paper, body.replacement_source_id)
            if replacement is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Replacement paper {body.replacement_source_id} not found",
                )
            if replacement.id == source_id:
                raise HTTPException(
                    status_code=422,
                    detail="replacement_source_id must point to a different paper",
                )
            _replace_paper_references(session, source_id, replacement.id)
        elif body.action == "delete_with_references":
            _delete_external_paper_references(session, source_id)

    # DuckDB can still see pre-update FK references inside the same transaction.
    # Commit reference handling first, then delete the paper in a fresh session.
    with get_session(engine) as session:
        _delete_paper_row(session, source_id)

    _remove_paper_indexes(source_id, knowledge_store, chunk_store)
    return {
        "status": "deleted",
        "id": source_id,
        "title": title,
        "references": reference_counts,
        "action": body.action,
        "replacement_source_id": body.replacement_source_id,
    }


@router.post("/{source_id}/restore", response_model=PaperItem)
def restore_source(source_id: int, engine: Engine = Depends(get_engine)) -> PaperItem:
    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        if row.status != "removed":
            raise HTTPException(
                status_code=409,
                detail=f"Paper {source_id} is not removed",
            )

    return _update_paper_fields(
        source_id,
        engine,
        status="pending",
        reviewed_at=None,
    )


@router.post("/{source_id}/acquire-full-text", response_model=PaperItem)
def acquire_full_text(
    source_id: int,
    background_tasks: BackgroundTasks,
    body: AcquireFullTextRequest | None = None,
    engine: Engine = Depends(get_engine),
    chunk_store=Depends(get_chunk_store),
) -> PaperItem:
    body = body or AcquireFullTextRequest()
    if body.source_path:
        from neurodb.library_store import (
            library_root,
            resolve_library_path,
            resolve_library_project,
        )
        project = resolve_library_project(body.source_path)
        if project is not None:
            supplied = SuppliedInput(path=str(project))
        else:
            resolved = resolve_library_path(body.source_path)
            if resolved is None:
                root = library_root()
                try:
                    inside = (root / body.source_path).resolve().is_relative_to(root)
                except Exception:
                    inside = False
                if not inside:
                    raise HTTPException(status_code=400, detail="Invalid file path")
                raise HTTPException(status_code=404,
                                    detail="File not found in library or unsupported type")
            ext = resolved.suffix.lower()
            if ext in (".txt", ".md"):
                supplied = SuppliedInput(text=resolved.read_text(errors="replace"),
                                         format="md" if ext == ".md" else "txt")
            else:  # .pdf/.html/.htm
                supplied = SuppliedInput(path=str(resolved))
    else:
        # source_url (phase 2b explicit link) takes precedence over url when no text is supplied
        effective_url = body.url or body.source_url
        supplied = SuppliedInput(url=effective_url, text=body.text, format=body.format)

    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if paper.status != "approved":
            raise HTTPException(status_code=400, detail="Approve the source first")
        # Snapshot fields needed after session closes (expire_on_commit=False keeps them)
        paper_title = paper.title
        paper_year = paper.year
        paper_currency = paper.currency_status

    if classify_for_phase2b(paper, supplied) == "phase2b":
        # Async path: mark pending, schedule background job, return immediately
        _update_paper_fields(source_id, engine, full_text_status="pending")
        background_tasks.add_task(_run_phase2b_job, source_id, engine, chunk_store, supplied)
        with get_session(engine) as session:
            row = session.get(Paper, source_id)
            return _paper_item_from_row(row, session)

    # Synchronous 2a path (unchanged)
    with httpx.Client(timeout=20.0, follow_redirects=True) as http:
        result = acquire(paper, http, supplied)

    warnings: list[str] = []
    if isinstance(result, AcquireFailure):
        _update_paper_fields(source_id, engine, full_text_status=result.status)
        warnings.append(result.message)
    else:
        _commit_chunks(source_id, engine, chunk_store, sections=result.sections,
                       text_source=result.text_source, title=paper_title, year=paper_year,
                       currency=paper_currency)
        _update_paper_fields(source_id, engine, full_text_status="verified",
                             text_source=result.text_source, data_tier="full_text")
        warnings.extend(run_post_acquisition(source_id, engine))

    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        item = _paper_item_from_row(row, session)
    return item.model_copy(update={"warnings": warnings})


@router.post("/{source_id}/fulltext-review", response_model=PaperItem)
def fulltext_review(
    source_id: int,
    body: FulltextReviewRequest,
    engine: Engine = Depends(get_engine),
    chunk_store=Depends(get_chunk_store),
) -> PaperItem:
    staged = read_staging(engine, source_id)
    if staged is None:
        raise HTTPException(status_code=404, detail="No parse awaiting review")

    post_warnings: list[str] = []
    if body.decision == "confirm":
        sections = [
            Section(
                label=s.get("label"),
                text=s["text"],
                char_start=s.get("char_start", 0),
                char_end=s.get("char_end", len(s["text"])),
                page=s.get("page"),
            )
            for s in staged["sections"]
        ]
        with get_session(engine) as session:
            row = session.get(Paper, source_id)
            if row is None:
                raise HTTPException(status_code=404, detail=f"Paper {source_id} not found")
            title, year, currency = row.title, row.year, row.currency_status

        _commit_chunks(source_id, engine, chunk_store,
                       sections=sections,
                       text_source=staged["text_source"],
                       title=title, year=year, currency=currency)
        _update_paper_fields(source_id, engine,
                             full_text_status="verified",
                             text_source=staged["text_source"],
                             data_tier="full_text",
                             parse_confidence=staged.get("parse_confidence"))
        post_warnings = run_post_acquisition(source_id, engine)
    else:
        _update_paper_fields(source_id, engine, full_text_status="unavailable")

    delete_staging(engine, source_id)

    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        # staging was just deleted; pass explicitly to avoid a sentinel auto-fetch
        # opening a nested session inside this DuckDB session.
        item = _paper_item_from_row(row, session, staged=None)
    return item.model_copy(update={"warnings": post_warnings})


def _load_paper(engine: Engine, source_id: int) -> Paper:
    """Load a Paper in its own session and return a detached instance."""
    with get_session(engine) as session:
        row = session.get(Paper, source_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Paper {source_id} not found")
        # Access all attributes we need before session closes
        session.expunge(row)
        return row


def _phase2b_parse(paper: Paper, supplied: SuppliedInput) -> ParsedArtifact | None:
    """Attempt OA PDF/HTML acquisition for a paper. Module-level for monkeypatching in tests."""
    from neurodb.html_extractor import extract_html
    from neurodb.oa_locator import find_pdf_url
    from neurodb.pdf_parser import parse_pdf

    if supplied and supplied.path:
        from pathlib import Path
        p = Path(supplied.path)
        try:
            if p.is_dir():
                from neurodb.tex_parser import parse_tex
                artifact = parse_tex(p)
            elif p.suffix.lower() == ".pdf":
                artifact = parse_pdf(p.read_bytes())
            else:  # .html/.htm
                artifact = extract_html(p.read_text(errors="replace"))
            artifact.fetched_url = p.name
            return artifact
        except Exception:
            logger.exception("Phase 2b local-file parse failed for %s", supplied.path)
            return None

    unpaywall_email = os.environ.get("UNPAYWALL_EMAIL")
    s2_pdf_url = getattr(paper, "open_access_pdf", None)

    # Prefer an explicitly-supplied URL over OA discovery
    source = supplied.url if supplied and supplied.url else None

    if source is None:
        with httpx.Client(timeout=30.0, follow_redirects=True) as http:
            source = find_pdf_url(paper, http, unpaywall_email=unpaywall_email,
                                  s2_pdf_url=s2_pdf_url)

    if source is None:
        return None

    try:
        with httpx.Client(timeout=60.0, follow_redirects=True) as http:
            resp = http.get(source)
            resp.raise_for_status()

        content_type = (resp.headers.get("Content-Type") or "").lower()
        is_pdf = "pdf" in content_type or source.lower().endswith(".pdf")

        if is_pdf:
            artifact = parse_pdf(resp.content)
        else:
            artifact = extract_html(resp.text)

        artifact.fetched_url = source
        return artifact
    except Exception:
        logger.exception("Phase 2b parse failed for url=%s", source)
        return None


def _run_phase2b_job(source_id: int, engine: Engine, chunk_store, supplied: SuppliedInput) -> None:
    """Background job: run the phase2b acquisition pipeline for one paper."""
    run_acquisition(
        source_id=source_id,
        engine=engine,
        parse=lambda: _phase2b_parse(_load_paper(engine, source_id), supplied),
        commit_chunks=lambda **kw: _commit_chunks(
            kw.pop("source_id", source_id), engine, chunk_store, **kw),
        set_fields=lambda **f: _update_paper_fields(source_id, engine, **f),
        on_verified=lambda: run_post_acquisition(source_id, engine),
    )


def _commit_chunks(source_id, engine, chunk_store, *, sections, text_source,
                   title, year, currency):
    chunks = chunk_sections(sections)
    if chunk_store is not None:
        chunk_store.delete_paper(source_id)
        chunk_store.add_chunks(paper_id=source_id, title=title, year=year,
                               currency_status=currency, text_source=text_source, chunks=chunks)
    created_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        session.query(PaperChunk).filter(PaperChunk.paper_id == source_id).delete()
        for c in chunks:
            session.add(PaperChunk(
                paper_id=source_id, chunk_index=c.chunk_index, text=c.text, section=c.section,
                char_start=c.char_start, char_end=c.char_end, page=c.page,
                text_source=text_source, chroma_id=f"chunk:{source_id}:{c.chunk_index}",
                created_at=created_at))


def _build_metadata_client() -> MetadataLookupClient:
    """Seam for tests: monkeypatch to avoid network in the backfill path."""
    return MetadataLookupClient()


def run_post_acquisition(source_id: int, engine: Engine) -> list[str]:
    """Single shared commit point for all acquisition paths (spec workstream 2+3).

    Backfills NULL bibliographic metadata (audited, source-labeled), then emits
    full_text_acquired so the reconciliation handler sees populated authorship.
    Never raises; every failure becomes a warning so acquisition is never blocked.
    """
    warnings: list[str] = []
    try:
        result = backfill_paper_metadata(
            engine, source_id,
            metadata_client=_build_metadata_client(),
            set_fields=lambda **fields: _update_paper_fields(source_id, engine, **fields),
        )
        warnings.extend(result.warnings)
    except Exception as exc:
        logger.exception("metadata backfill failed for source %d", source_id)
        warnings.append(f"metadata backfill failed: {exc}")
        result = BackfillResult(warnings=[str(exc)])
    _log_backfill(engine, source_id, result)
    outcomes = emit(FULL_TEXT_ACQUIRED, source_id=source_id)
    warnings.extend(
        f"reconciliation handler {o['handler']} failed: {o['error']}"
        for o in outcomes if o["status"] == "error"
    )
    return warnings


def _log_backfill(engine: Engine, source_id: int, result: BackfillResult) -> None:
    """Audit row labeling the source of every backfilled value (provenance rule)."""
    try:
        with get_session(engine) as session:
            session.add(EventLog(
                event_name="metadata_backfill",
                entity_id=str(source_id),
                handler="backfill_paper_metadata",
                status="ok" if not result.warnings else "warning",
                detail_json=json.dumps({
                    "filled": result.filled,
                    "values": {k: str(v) for k, v in result.values.items()},
                    "warnings": result.warnings,
                }),
                created_at=datetime.now(UTC).isoformat(),
            ))
    except Exception:
        logger.exception("backfill audit write failed for source %d", source_id)


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
        "data_tier": item.data_tier,
        "year": item.year,
        "currency_status": item.currency_status,
    }

    chroma_id = knowledge_store.add_summary(
        source_id=values["id"],
        title=values["title"],
        doi=values["doi"],
        topic_context=values["topic_context"],
        summary=values["summary"],
        data_tier=values["data_tier"],
        year=values["year"],
        currency_status=values["currency_status"],
    )
    _update_paper_fields(source_id, engine, chroma_id=chroma_id)
    return {"approved": True, "source_id": source_id, "chroma_id": chroma_id}


def _update_paper_fields(source_id: int, engine: Engine, **fields) -> PaperItem:
    if not fields:
        with get_session(engine) as session:
            row = _get_paper_or_404(session, source_id)
            return _paper_item_from_row(row, session)
    if engine.dialect.name == "duckdb":
        return _update_paper_fields_duckdb(source_id, engine, **fields)

    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        for field, value in fields.items():
            setattr(row, field, value)
        session.flush()
        return _paper_item_from_row(row, session)


def _update_paper_fields_duckdb(source_id: int, engine: Engine, **fields) -> PaperItem:
    """Update Paper fields while preserving paper references.

    DuckDB rejects UPDATEs to a parent row when child rows reference it through a
    foreign key, even when the primary key is unchanged. Only the tables that
    actually FK to papers are detached and restored around the UPDATE
    (claims, study_notes, evidence_links, dataset_packet_papers). grouping_links
    has no such FK, so it is left untouched — detaching it churned and corrupted
    its ART unique index on DuckDB.
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
    finally:
        with get_session(engine) as session:
            _restore_paper_links(session, preserved_links)
    # Pre-fetch staging before opening the final session.  read_staging opens its
    # own session, and DuckDB forbids nested transactions.
    with get_session(engine) as _peek:
        _row_peek = _get_paper_or_404(_peek, source_id)
        _needs_staging = _row_peek.full_text_status == "needs_review"
    staging = read_staging(engine, source_id) if _needs_staging else None

    with get_session(engine) as session:
        row = _get_paper_or_404(session, source_id)
        return _paper_item_from_row(row, session, staged=staging)


def _paper_item_from_row(row: Paper, session, *,
                         staged: dict | None = _SENTINEL) -> PaperItem:
    """Build a PaperItem from a Paper ORM row.

    `staged` is the fulltext_staging dict (or None) to include in the response.
    Pass the sentinel default to auto-fetch it from the engine when status is
    needs_review. Pass None explicitly to skip it (e.g. when the staging row
    was just deleted).

    Auto-fetch opens its own session, so do NOT call with the sentinel from
    inside a DuckDB transaction (which prohibits nested transactions). In that
    case, fetch staging first and pass it explicitly.
    """
    item = PaperItem.model_validate(row)
    links = (
        session.query(GroupingLink, Grouping)
        .join(Grouping, Grouping.id == GroupingLink.grouping_id)
        .filter(GroupingLink.anchor_type == "paper", GroupingLink.anchor_id == row.id)
        .order_by(Grouping.type.asc(), Grouping.name.asc())
        .all()
    )
    if staged is _SENTINEL:
        if row.full_text_status == "needs_review":
            engine = session.get_bind()
            staging = read_staging(engine, row.id)
        else:
            staging = None
    else:
        staging = staged
    return item.model_copy(update={
        "grouping_links": [
            PaperGroupingLink(
                grouping_id=link.grouping_id,
                grouping_type=grouping.type,
                grouping_name=grouping.name,
                status=link.status,
            )
            for link, grouping in links
        ],
        "fulltext_staging": staging,
    })


def _get_paper_or_404(session, source_id: int) -> Paper:
    row = session.get(Paper, source_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Paper {source_id} not found")
    return row


def _reference_total(counts: dict[str, int]) -> int:
    return sum(counts.values())


def _external_reference_counts(counts: dict[str, int]) -> dict[str, int]:
    artifact_keys = {"full_text_chunks", "fulltext_staging"}
    return {key: value for key, value in counts.items() if key not in artifact_keys}


def _paper_claim_ids(session, paper_id: int) -> list[int]:
    if not _table_has_columns(
        session,
        "claims",
        ["id", "paper_id", "text", "claim_type", "status", "created_at", "updated_at"],
    ):
        return []
    return [
        row[0]
        for row in session.query(Claim.id).filter(Claim.paper_id == paper_id).all()
    ]


def _paper_study_note_ids(session, paper_id: int) -> list[int]:
    if not _table_has_columns(
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
    ):
        return []
    return [
        row[0]
        for row in session.query(StudyNote.id).filter(StudyNote.paper_id == paper_id).all()
    ]


def _paper_evidence_link_ids(
    session,
    paper_id: int,
    claim_ids: list[int] | None = None,
    study_note_ids: list[int] | None = None,
) -> list[int]:
    if not _table_has_columns(
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
            "status",
            "created_at",
        ],
    ):
        return []
    ids = {
        row[0]
        for row in session.query(EvidenceLink.id)
        .filter(EvidenceLink.paper_id == paper_id)
        .all()
    }
    if claim_ids:
        ids.update(
            row[0]
            for row in session.query(EvidenceLink.id)
            .filter(EvidenceLink.claim_id.in_(claim_ids))
            .all()
        )
    if study_note_ids:
        ids.update(
            row[0]
            for row in session.query(EvidenceLink.id)
            .filter(EvidenceLink.note_id.in_(study_note_ids))
            .all()
        )
    return sorted(ids)


def _paper_reference_counts(session, paper_id: int) -> dict[str, int]:
    claim_ids = _paper_claim_ids(session, paper_id)
    study_note_ids = _paper_study_note_ids(session, paper_id)
    evidence_ids = _paper_evidence_link_ids(session, paper_id, claim_ids, study_note_ids)
    return {
        "claims": len(claim_ids),
        "study_notes": len(study_note_ids),
        "evidence_links": len(evidence_ids),
        "dataset_packet_papers": session.query(DatasetPacketPaper)
        .filter(DatasetPacketPaper.paper_id == paper_id)
        .count(),
        "grouping_links": session.query(GroupingLink)
        .filter(GroupingLink.anchor_type == "paper", GroupingLink.anchor_id == paper_id)
        .count(),
        "plan_steps": session.query(PlanStep).filter(PlanStep.paper_id == paper_id).count(),
        "full_text_chunks": session.query(PaperChunk)
        .filter(PaperChunk.paper_id == paper_id)
        .count(),
        "fulltext_staging": session.query(PaperFulltextStaging)
        .filter(PaperFulltextStaging.source_id == paper_id)
        .count(),
    }


def _delete_paper_artifacts(session, paper_id: int) -> None:
    for row in session.query(PaperChunk).filter(PaperChunk.paper_id == paper_id).all():
        session.delete(row)
    for row in (
        session.query(PaperFulltextStaging)
        .filter(PaperFulltextStaging.source_id == paper_id)
        .all()
    ):
        session.delete(row)


def _delete_external_paper_references(session, paper_id: int) -> None:
    claim_ids = _paper_claim_ids(session, paper_id)
    study_note_ids = _paper_study_note_ids(session, paper_id)
    evidence_ids = _paper_evidence_link_ids(session, paper_id, claim_ids, study_note_ids)
    for row in session.query(EvidenceLink).filter(EvidenceLink.id.in_(evidence_ids)).all():
        session.delete(row)
    for model, field in [
        (DatasetPacketPaper, DatasetPacketPaper.paper_id),
        (StudyNote, StudyNote.paper_id),
        (Claim, Claim.paper_id),
        (PlanStep, PlanStep.paper_id),
    ]:
        for row in session.query(model).filter(field == paper_id).all():
            session.delete(row)
    for row in (
        session.query(GroupingLink)
        .filter(GroupingLink.anchor_type == "paper", GroupingLink.anchor_id == paper_id)
        .all()
    ):
        session.delete(row)
    session.flush()


def _evidence_link_values(session, evidence_ids: list[int], old_id: int, new_id: int) -> list[dict]:
    values = []
    if not evidence_ids:
        return values
    for link in session.query(EvidenceLink).filter(EvidenceLink.id.in_(evidence_ids)).all():
        values.append({
            "id": link.id,
            "hypothesis_id": link.hypothesis_id,
            "claim_id": link.claim_id,
            "paper_id": new_id if link.paper_id == old_id else link.paper_id,
            "packet_id": link.packet_id,
            "note_id": link.note_id,
            "link_type": link.link_type,
            "status": link.status,
            "created_at": link.created_at,
        })
    return values


def _replace_dataset_packet_links(session, old_id: int, new_id: int) -> None:
    for link in session.query(DatasetPacketPaper).filter_by(paper_id=old_id).all():
        duplicate = (
            session.query(DatasetPacketPaper)
            .filter_by(packet_id=link.packet_id, paper_id=new_id)
            .one_or_none()
        )
        if duplicate is not None:
            session.delete(link)
        else:
            link.paper_id = new_id


def _replace_grouping_links(session, old_id: int, new_id: int) -> None:
    rows = (
        session.query(GroupingLink)
        .filter(GroupingLink.anchor_type == "paper", GroupingLink.anchor_id == old_id)
        .all()
    )
    for link in rows:
        duplicate = (
            session.query(GroupingLink)
            .filter_by(
                grouping_id=link.grouping_id,
                anchor_type="paper",
                anchor_id=new_id,
            )
            .one_or_none()
        )
        if duplicate is not None:
            session.delete(link)
        else:
            link.anchor_id = new_id


def _replace_paper_references(session, old_id: int, new_id: int) -> None:
    claim_ids = _paper_claim_ids(session, old_id)
    study_note_ids = _paper_study_note_ids(session, old_id)
    evidence_ids = _paper_evidence_link_ids(session, old_id, claim_ids, study_note_ids)
    evidence_values = _evidence_link_values(session, evidence_ids, old_id, new_id)
    for link in session.query(EvidenceLink).filter(EvidenceLink.id.in_(evidence_ids)).all():
        session.delete(link)
    session.flush()

    _replace_dataset_packet_links(session, old_id, new_id)
    _replace_grouping_links(session, old_id, new_id)
    for row in session.query(StudyNote).filter(StudyNote.paper_id == old_id).all():
        row.paper_id = new_id
    for row in session.query(Claim).filter(Claim.paper_id == old_id).all():
        row.paper_id = new_id
    for row in session.query(PlanStep).filter(PlanStep.paper_id == old_id).all():
        row.paper_id = new_id
        row.source_ref = None
    session.flush()
    for values in evidence_values:
        session.add(EvidenceLink(**values))
    session.flush()


def _delete_paper_row(session, paper_id: int) -> None:
    _delete_paper_artifacts(session, paper_id)
    row = _get_paper_or_404(session, paper_id)
    session.delete(row)
    session.flush()


def _remove_paper_indexes(source_id: int, knowledge_store, chunk_store) -> None:
    try:
        knowledge_store.remove_summary(source_id)
    except Exception:
        logger.exception("ChromaDB summary removal failed for source %d", source_id)
    if chunk_store is not None:
        try:
            chunk_store.delete_paper(source_id)
        except Exception:
            logger.exception("ChromaDB chunk removal failed for source %d", source_id)


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
        # grouping_links has no foreign key to papers, so the DuckDB FK-update
        # workaround does not need to detach it. Deleting + re-inserting these
        # rows (with explicit ids) on every approve/remove churned the ART unique
        # index and corrupted it, so we intentionally leave grouping_links in
        # place — the paper UPDATE is not blocked by them.
        "grouping_links": [],
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
    # grouping_links are intentionally not detached (see _detach_paper_links),
    # so there is nothing to restore for them.
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
    if session.get_bind().dialect.name == "sqlite":
        rows = session.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        actual = {row[1] for row in rows}
    else:
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
                "content": _summary_prompt(row),
            }],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
    except Exception as exc:
        logger.exception("Summary generation failed for source %d", row.id)
        return f"{_fallback_summary(row)}\n\nSummary generation note: {exc}"
    return _fallback_summary(row)


def _dedup_threshold() -> float:
    raw = os.environ.get("NEURODB_DEDUP_THRESHOLD", "0.15")
    try:
        return float(raw)
    except ValueError:
        return 0.15
