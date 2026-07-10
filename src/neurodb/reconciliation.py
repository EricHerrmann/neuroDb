"""FullTextAcquired reconciliation: keep derived stores consistent with `papers`.

papers is the source of truth; this handler pushes data_tier / authors / year /
currency_status into the summary index (knowledge_library) and the chunk index
(knowledge_chunks) with metadata-only updates. Idempotent: deterministic doc ids,
merge-updates only. Auditable: one event_log row per run.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.events import FULL_TEXT_ACQUIRED, subscribe
from neurodb.schema import EventLog, Paper

logger = logging.getLogger(__name__)

HANDLER_KEY = "reconcile_derived_stores"


def register_reconciliation(engine: Engine, knowledge_store, chunk_store) -> None:
    """Subscribe the reconciliation handler once (keyed: re-registration replaces)."""

    def _handler(source_id: int) -> None:
        reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                     source_id=source_id)

    subscribe(FULL_TEXT_ACQUIRED, _handler, key=HANDLER_KEY)


def reconcile_full_text_acquired(engine: Engine, knowledge_store, chunk_store, *,
                                 source_id: int) -> dict:
    """Re-sync derived stores for one paper. Raises on failure after audit row."""
    detail: dict = {"summary_updated": False, "chunks_updated": 0, "skipped": []}
    status = "ok"
    try:
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            if paper is None:
                raise ValueError(f"paper {source_id} not found")
            authors = ""
            if paper.authors_json:
                authors = "; ".join(json.loads(paper.authors_json))
            metadata = {
                "data_tier": paper.data_tier,
                "year": str(paper.year) if paper.year else "",
                "currency_status": paper.currency_status,
                "authors": authors,
            }
        if knowledge_store is None:
            detail["skipped"].append("knowledge_store unavailable")
        else:
            detail["summary_updated"] = knowledge_store.update_summary_metadata(
                source_id, metadata)
        if chunk_store is None:
            detail["skipped"].append("chunk_store unavailable")
        else:
            detail["chunks_updated"] = chunk_store.update_paper_metadata(
                source_id, metadata)
    except Exception as exc:
        status = "error"
        detail["error"] = str(exc)
        logger.exception("reconciliation failed for source %d", source_id)
    _log_event(engine, source_id=source_id, status=status, detail=detail)
    if status == "error":
        raise RuntimeError(
            f"reconciliation failed for source {source_id}: {detail['error']}")
    return detail


def _log_event(engine: Engine, *, source_id: int, status: str, detail: dict) -> None:
    try:
        with get_session(engine) as session:
            session.add(EventLog(
                event_name=FULL_TEXT_ACQUIRED,
                entity_id=str(source_id),
                handler=HANDLER_KEY,
                status=status,
                detail_json=json.dumps(detail),
                created_at=datetime.now(UTC).isoformat(),
            ))
    except Exception:
        logger.exception("event_log write failed for source %d", source_id)
