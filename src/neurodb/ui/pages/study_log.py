import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.study import list_tags, tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def _browse_section(engine: Engine) -> None:
    st.subheader("Your Study Tags")

    col1, col2 = st.columns(2)
    concept_filter = col1.text_input("Filter by concept", "")
    source_filter = col2.selectbox("Filter by source", ["All"] + SOURCES)

    with get_session(engine) as session:
        rows = list_tags(
            session,
            concept=concept_filter.strip() or None,
            source=source_filter if source_filter != "All" else None,
        )

    if not rows:
        st.info("No study tags yet. Tag a dataset from the Dataset Browser or use the form below.")
        return

    df = pd.DataFrame(rows, columns=["source", "source_id", "concept_tag", "section_ref", "tagged_at", "note_text"])
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(rows)} tag(s)")


def _tag_form_section(engine: Engine) -> None:
    st.subheader("Tag a Dataset by ID")
    st.caption("Use source IDs from the Dataset Browser or SQL Query results.")

    with st.form("tag_by_id_form", clear_on_submit=True):
        source = st.selectbox("Source", SOURCES)
        source_id = st.text_input("Source ID", placeholder="e.g. 000003 (DANDI) or ds003684 (OpenNeuro)")
        concept = st.text_input("Concept tag *", placeholder="e.g. primary visual cortex")
        section = st.text_input("Section reference", placeholder="e.g. Augustine Ch13 p.312")
        note = st.text_area("Note", placeholder="What you observed, confirmed, or questioned")
        submitted = st.form_submit_button("Save Tag")

    if submitted:
        if not source_id.strip():
            st.error("Source ID is required.")
        elif not concept.strip():
            st.error("Concept tag is required.")
        else:
            try:
                with get_session(engine) as session:
                    note_obj = tag_dataset(
                        session,
                        source=source,
                        source_id=source_id.strip(),
                        concept_tag=concept.strip(),
                        section_ref=section.strip() or None,
                        note_text=note.strip() or None,
                    )
                if note_obj is None:
                    st.error(f"Dataset not found: `{source}:{source_id.strip()}` — run ingest first.")
                else:
                    st.success(f"Tagged `{source}:{source_id.strip()}` → '{concept.strip()}'")
                    st.rerun()
            except Exception as exc:
                st.error(f"Error saving tag: {exc}")


def render(engine: Engine) -> None:
    st.header("Study Log")
    _browse_section(engine)
    st.divider()
    _tag_form_section(engine)
