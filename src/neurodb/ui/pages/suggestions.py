"""Suggestions tab: import queue and source suggestions from the discovery agent."""
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from neurodb.provenance import run_ingest
from neurodb.schema import ImportQueue, LearningSource, SourceSuggestion


def render(engine: Engine) -> None:
    st.header("Suggestions")
    st.subheader("Dataset Import Requests")
    _render_import_queue(engine)

    st.divider()
    st.subheader("Connector Requests")
    _render_source_suggestions(engine)


def _render_import_queue(engine: Engine) -> None:
    msg = st.session_state.pop("import_result", None)
    if msg:
        if msg["ok"]:
            st.success(msg["text"])
        else:
            st.error(msg["text"])

    with Session(engine) as session:
        rows = session.execute(
            select(ImportQueue)
            .where(ImportQueue.status == "pending")
            .order_by(ImportQueue.suggested_at.desc())
        ).scalars().all()

    if not rows:
        st.caption("No pending import suggestions.")
        return

    for row in rows:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                st.markdown(f"**{row.title or row.source_id}** — `{row.source}:{row.source_id}`")
                if row.chapter_ref:
                    st.caption(f"Suggested while reading: {row.chapter_ref}")
                if row.reason:
                    st.markdown(f"*{row.reason}*")
            with col_actions:
                if st.button("Import", key=f"import_{row.id}", width="stretch"):
                    _run_import(row, engine)
                if st.button("Dismiss", key=f"dismiss_import_{row.id}", width="stretch"):
                    _update_status(engine, ImportQueue, row.id, "dismissed")
                    st.rerun()


def _render_source_suggestions(engine: Engine) -> None:
    with Session(engine) as session:
        rows = session.execute(
            select(SourceSuggestion)
            .where(SourceSuggestion.status == "pending")
            .order_by(SourceSuggestion.suggested_at.desc())
        ).scalars().all()

    if not rows:
        st.caption("No pending source suggestions.")
        return

    for row in rows:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                label = row.display_name or row.reference or "—"
                st.markdown(f"**{label}** (`{row.suggestion_type}`)")
                if row.reference:
                    st.caption(row.reference)
                if row.reason:
                    st.markdown(f"*{row.reason}*")
            with col_actions:
                if row.suggestion_type == "learning_source":
                    if st.button("Promote", key=f"promote_{row.id}", width="stretch"):
                        _promote_to_learning_source(row, engine)
                if st.button("Dismiss", key=f"dismiss_src_{row.id}", width="stretch"):
                    _update_status(engine, SourceSuggestion, row.id, "dismissed")
                    st.rerun()


def _ingest_dataset(source: str, source_id: str, engine: Engine) -> None:
    """Import a single dataset in-process using the existing engine connection."""
    from neurodb.connectors.openneuro import OpenNeuroConnector
    from neurodb.connectors.dandi import DandiConnector
    from neurodb.connectors.neurovault import NeuroVaultConnector

    _connectors = {
        "openneuro": OpenNeuroConnector,
        "dandi": DandiConnector,
        "neurovault": NeuroVaultConnector,
    }
    if source not in _connectors:
        raise ValueError(f"No connector registered for source '{source}'")
    connector = _connectors[source]()
    run_ingest(engine=engine, connector=connector, dataset_ids=[source_id])


def _run_import(row: ImportQueue, engine: Engine) -> None:
    with st.spinner(f"Importing {row.source}:{row.source_id}…"):
        try:
            _ingest_dataset(row.source, row.source_id, engine)
            _update_status(engine, ImportQueue, row.id, "imported")
            st.session_state["import_result"] = {"ok": True, "text": f"Imported {row.source_id}"}
        except Exception as exc:
            st.session_state["import_result"] = {
                "ok": False,
                "text": f"Import failed for {row.source_id}: {str(exc)[:400]}",
            }
    st.rerun()


def _promote_to_learning_source(row: SourceSuggestion, engine: Engine) -> None:
    now = datetime.now(timezone.utc).isoformat()
    source_key = row.reference or row.display_name
    with Session(engine) as session:
        existing = session.execute(
            select(LearningSource).where(LearningSource.source_key == source_key)
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                LearningSource(
                    source_type="paper",
                    source_key=source_key,
                    display_name=row.display_name or row.reference or "Untitled source",
                    content_json=None,
                    metadata_json=row.metadata_json,
                    added_by="user",
                    added_at=now,
                )
            )
        row_obj = session.get(SourceSuggestion, row.id)
        if row_obj:
            row_obj.status = "accepted"
        session.commit()
    st.success(f"Promoted to Learning Registry: {row.display_name or row.reference}")
    st.rerun()


def _update_status(engine: Engine, model, row_id: int, status: str) -> None:
    resolved_at = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        row = session.get(model, row_id)
        if row:
            row.status = status
            if hasattr(row, "resolved_at"):
                row.resolved_at = resolved_at
            session.commit()
