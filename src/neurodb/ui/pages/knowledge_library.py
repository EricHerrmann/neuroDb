"""Knowledge Library page for Neuro-Tutor curated sources."""
import os
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.schema import KnowledgeSource


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
            st.caption(
                f"{row.source_type} | queued {row.queued_at} | topic: {row.topic_context}"
            )
            if row.doi:
                st.caption(f"DOI: `{row.doi}`")
            if row.url:
                st.caption(f"URL: {row.url}")
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
            st.caption(
                f"{row.source_type} | reviewed {row.reviewed_at or 'unknown'} | topic: {row.topic_context}"
            )
            preview = (row.summary or "").strip()
            if len(preview) > 220:
                preview = f"{preview[:217]}..."
            st.write(preview or "No summary available.")
            if row.summary:
                with st.expander("Full summary"):
                    st.markdown(row.summary)


def _list_sources(engine: Engine, status: str) -> list[KnowledgeSource]:
    with get_session(engine) as session:
        return (
            session.query(KnowledgeSource)
            .filter_by(status=status)
            .order_by(KnowledgeSource.queued_at.desc())
            .all()
        )


def _approve_source(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        row = session.query(KnowledgeSource).filter_by(id=source_id).one()
        summary = _generate_summary(row)
        row.summary = summary
        row.status = "approved"
        row.reviewed_at = datetime.now(timezone.utc).isoformat()

        knowledge_store = st.session_state.get("knowledge_store")
        if knowledge_store is not None:
            row.chroma_id = knowledge_store.add_summary(
                source_id=row.id,
                title=row.title,
                doi=row.doi,
                topic_context=row.topic_context,
                summary=summary,
            )


def _reject_source(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        row = session.query(KnowledgeSource).filter_by(id=source_id).one()
        row.status = "rejected"
        row.reviewed_at = datetime.now(timezone.utc).isoformat()


def _generate_summary(row: KnowledgeSource) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return _fallback_summary(row)

    try:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=os.environ.get("NEURODB_MODEL", "claude-opus-4-7"),
            max_tokens=700,
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
        return f"{_fallback_summary(row)}\n\nSummary generation note: {exc}"

    return _fallback_summary(row)


def _fallback_summary(row: KnowledgeSource) -> str:
    return (
        f"Key concepts: {row.title} was queued as a {row.source_type} while discussing "
        f"{row.topic_context}.\n\n"
        "Relevance to neuroscience: This source was approved for future Neuro-Tutor retrieval.\n\n"
        "Open questions: Add a richer Claude-generated summary when API access is available."
    )

