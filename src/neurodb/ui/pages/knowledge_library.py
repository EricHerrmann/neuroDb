"""Knowledge Library page for Neuro-Tutor curated sources."""
import os
from datetime import datetime, timezone
from time import perf_counter

import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.knowledge_summary import fallback_summary as _fallback_summary
from neurodb.knowledge_summary import summary_prompt
from neurodb.model_telemetry import add_model_call_log
from neurodb.schema import Paper


def render(engine: Engine) -> None:
    st.subheader("Knowledge Library")

    pending_tab, library_tab = st.tabs(["Pending", "Library"])
    with pending_tab:
        _render_pending(engine)
    with library_tab:
        _render_library(engine)


def _render_pending(engine: Engine) -> None:
    rows = _list_sources(engine, "pending")
    if not rows:
        st.info("No pending sources.")
        return

    for row in rows:
        with st.container(border=True):
            st.markdown(f"**{row.title}**")
            st.caption(f"Source type: {row.source_type}")
            st.caption(f"Topic context: {row.topic_context}")
            st.caption(f"Queued: {row.queued_at}")
            if row.doi:
                st.markdown(f"DOI: [{row.doi}](https://doi.org/{row.doi})")
            if row.url:
                st.markdown(f"URL: [{row.url}]({row.url})")
            duplicate = _find_near_duplicate(row)
            if duplicate:
                st.warning(
                    f"Similar to approved source: {duplicate['title']} - you can still approve."
                )
            approve_col, reject_col = st.columns(2)
            with approve_col:
                if st.button("Approve", key=f"approve_source_{row.id}", width="stretch"):
                    with st.spinner("Generating summary and indexing source..."):
                        _approve_source(engine, row.id)
                    st.rerun()
            with reject_col:
                if st.button("Reject", key=f"reject_source_{row.id}", width="stretch"):
                    _reject_source(engine, row.id)
                    st.rerun()


def _render_library(engine: Engine) -> None:
    rows = _list_sources(engine, "approved")
    if not rows:
        st.info("No approved sources yet.")
        return

    for row in rows:
        with st.container(border=True):
            st.markdown(f"**{row.title}**")
            st.caption(f"Source type: {row.source_type}")
            st.caption(f"Topic context: {row.topic_context}")
            st.caption(f"Reviewed: {row.reviewed_at or 'unknown'}")
            if row.doi:
                st.markdown(f"DOI: [{row.doi}](https://doi.org/{row.doi})")
            if row.url:
                st.markdown(f"URL: [{row.url}]({row.url})")
            if row.summary:
                with st.expander("Show summary"):
                    st.markdown(row.summary)
            else:
                st.caption("No summary available.")


def _list_sources(engine: Engine, status: str) -> list[Paper]:
    with get_session(engine) as session:
        return (
            session.query(Paper)
            .filter_by(status=status)
            .order_by(Paper.queued_at.desc())
            .all()
        )


def _approve_source(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        row = session.query(Paper).filter_by(id=source_id).one()
        summary, telemetry = _generate_summary(row, engine)
        row.summary = summary
        row.status = "approved"
        row.reviewed_at = datetime.now(timezone.utc).isoformat()
        if telemetry is not None:
            try:
                add_model_call_log(session, **telemetry)
            except Exception:
                pass

        knowledge_store = st.session_state.get("knowledge_store")
        if knowledge_store is not None:
            row.chroma_id = knowledge_store.add_summary(
                source_id=row.id,
                title=row.title,
                doi=row.doi,
                topic_context=row.topic_context,
                summary=summary,
                data_tier=row.data_tier,
                year=row.year,
                currency_status=row.currency_status,
            )


def _reject_source(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        row = session.query(Paper).filter_by(id=source_id).one()
        row.status = "rejected"
        row.reviewed_at = datetime.now(timezone.utc).isoformat()


def _find_near_duplicate(row: Paper) -> dict | None:
    knowledge_store = st.session_state.get("knowledge_store")
    if knowledge_store is None:
        return None
    query = f"{row.title}\n{row.topic_context}"
    results = knowledge_store.search(query, n=1)
    if not results:
        return None
    match = results[0]
    if match.get("distance", 1.0) > _dedup_threshold():
        return None
    metadata = match.get("metadata") or {}
    return {
        "title": metadata.get("title") or match.get("id") or "unknown",
        "distance": match.get("distance"),
    }


def _dedup_threshold() -> float:
    raw = os.environ.get("NEURODB_DEDUP_THRESHOLD", "0.15")
    try:
        return float(raw)
    except ValueError:
        return 0.15


def _generate_summary(row: Paper, engine: Engine | None = None) -> tuple[str, dict | None]:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    legacy_model = os.environ.get("NEURODB_KNOWLEDGE_SUMMARY_MODEL")
    if not api_key and legacy_model:
        return _fallback_summary(row), None

    try:
        model_client = None
        provider = "anthropic"
        max_tokens = 700
        if legacy_model:
            import anthropic

            client = anthropic.Anthropic(api_key=api_key)
            model = legacy_model
        else:
            from neurodb.config.provider_factory import build_provider_clients
            from neurodb.config.task_router import TaskRouter

            providers = build_provider_clients()
            if not providers:
                return _fallback_summary(row), None
            route = TaskRouter(providers).route("summary.knowledge_source", engine=engine)
            model_client = route.model_client
            provider = route.provider
            model = route.model_id
            max_tokens = route.max_tokens

        started = perf_counter()
        messages = [{
            "role": "user",
            "content": summary_prompt(row),
        }]
        if model_client is not None:
            response = model_client.create_message(
                model=model,
                max_tokens=max_tokens,
                system="",
                tools=[],
                messages=messages,
            )
        else:
            response = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=messages,
            )
        elapsed_ms = int((perf_counter() - started) * 1000)
        telemetry = {
            "task_type": "summary.knowledge_source",
            "provider": provider,
            "model": model,
            "mode": "summary",
            "response": response,
            "iteration": 1,
            "elapsed_ms": elapsed_ms,
        }
        for block in response.content:
            if block.type == "text":
                return block.text.strip(), telemetry
    except Exception as exc:
        return f"{_fallback_summary(row)}\n\nSummary generation note: {exc}", None

    return _fallback_summary(row), None


