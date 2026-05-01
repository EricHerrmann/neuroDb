"""Learning Registry tab: view and manage learning sources."""
import json
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from neurodb.schema import LearningSource


def render(engine: Engine) -> None:
    st.header("Learning Registry")
    st.caption("All textbooks, papers, and datasets registered as learning sources.")

    with Session(engine) as session:
        rows = session.execute(
            select(LearningSource).order_by(LearningSource.source_type, LearningSource.display_name)
        ).scalars().all()

    books = [row for row in rows if row.source_type == "book"]
    papers = [row for row in rows if row.source_type == "paper"]
    datasets = [row for row in rows if row.source_type == "dataset"]
    other = [row for row in rows if row.source_type not in {"book", "paper", "dataset"}]

    _render_section("Books", books, engine, show_chapters=True)
    _render_section("Papers & Studies", papers, engine)
    _render_section("Datasets", datasets, engine)
    if other:
        _render_section("Other", other, engine)

    st.divider()
    _render_add_form(engine)


def _render_section(title: str, rows: list[LearningSource], engine: Engine, show_chapters: bool = False) -> None:
    st.markdown(f"**{title}** ({len(rows)})")
    if not rows:
        st.caption(f"No {title.lower()} in registry yet.")
        return

    for row in rows:
        with st.expander(row.display_name, expanded=False):
            st.caption(f"Type: {row.source_type} | Key: `{row.source_key}` | Added by: {row.added_by}")

            if show_chapters and row.content_json:
                _render_chapters(row.content_json)
            elif row.content_json:
                _render_topics(row.content_json)

            if st.button("Remove", key=f"remove_{row.id}"):
                _remove_entry(engine, row.id)
                st.rerun()


def _render_chapters(content_json: str) -> None:
    try:
        content = json.loads(content_json)
        chapters = content.get("chapters", {})
        if not chapters:
            return
        chapter_items = sorted(chapters.items(), key=lambda item: int(item[0]))
        for chapter_num, chapter_data in chapter_items:
            topics = ", ".join(chapter_data.get("topics", []))
            st.markdown(f"- **Ch{chapter_num}** — {chapter_data['title']}")
            if topics:
                st.caption(f"Topics: {topics}")
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        st.warning("Could not parse chapter data.")


def _render_topics(content_json: str) -> None:
    try:
        content = json.loads(content_json)
        topics = content.get("topics", [])
        if topics:
            st.caption(f"Topics: {', '.join(topics)}")
    except json.JSONDecodeError:
        return


def _remove_entry(engine: Engine, row_id: int) -> None:
    with Session(engine) as session:
        row = session.get(LearningSource, row_id)
        if row:
            session.delete(row)
            session.commit()


def _render_add_form(engine: Engine) -> None:
    st.markdown("**Add a learning source manually**")
    with st.form("add_learning_source_form", clear_on_submit=True):
        source_type = st.selectbox("Type", options=["paper", "dataset", "book"])
        source_key = st.text_input("Key (DOI, URL, or unique ID)", placeholder="10.1167/19.10.23")
        display_name = st.text_input(
            "Display name",
            placeholder="Benson et al. 2018 retinotopy",
        )
        topics_raw = st.text_input("Topics (comma-separated)", placeholder="retinotopy, V1, pRF")
        submitted = st.form_submit_button("Add")

    if submitted and source_key.strip() and display_name.strip():
        topics = [topic.strip() for topic in topics_raw.split(",") if topic.strip()]
        content = json.dumps({"topics": topics}) if topics else None
        now = datetime.now(timezone.utc).isoformat()
        with Session(engine) as session:
            existing = session.execute(
                select(LearningSource).where(LearningSource.source_key == source_key.strip())
            ).scalar_one_or_none()
            if existing:
                st.warning(f"Key '{source_key.strip()}' already in registry.")
            else:
                session.add(
                    LearningSource(
                        source_type=source_type,
                        source_key=source_key.strip(),
                        display_name=display_name.strip(),
                        content_json=content,
                        metadata_json=None,
                        added_by="user",
                        added_at=now,
                    )
                )
                session.commit()
                st.success(f"Added: {display_name.strip()}")
                st.rerun()
