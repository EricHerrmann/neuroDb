import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.embed_hooks import embed_note, remove_note
from neurodb.study import delete_tag, list_tags, tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]
_DISPLAY_COLS = ["source", "source_id", "concept_tag", "section_ref", "tagged_at", "note_text"]


def _browse_section(engine: Engine) -> None:
    st.subheader("Your Study Tags")

    col1, col2, col3 = st.columns([3, 2, 1])
    concept_filter = col1.text_input("Filter by concept", "")
    source_filter = col2.selectbox("Filter by source", ["All"] + SOURCES)
    search_clicked = col3.button("Search", use_container_width=True)

    if "tag_search_active" not in st.session_state:
        st.session_state["tag_search_active"] = False
    if search_clicked:
        st.session_state["tag_search_active"] = True
        st.session_state["tag_concept_filter"] = concept_filter.strip() or None
        st.session_state["tag_source_filter"] = source_filter if source_filter != "All" else None

    active_concept = st.session_state.get("tag_concept_filter") if st.session_state["tag_search_active"] else None
    active_source = st.session_state.get("tag_source_filter") if st.session_state["tag_search_active"] else None

    with get_session(engine) as session:
        rows = list_tags(session, concept=active_concept, source=active_source)

    if not rows:
        st.info("No study tags yet. Tag a dataset from the Dataset Browser or use the form below.")
        return

    df = pd.DataFrame([{c: r[c] for c in _DISPLAY_COLS} for r in rows])
    df_height = min(46 + 50 * len(df), 600)
    event = st.dataframe(df, use_container_width=True, on_select="rerun", selection_mode="single-row", height=df_height)
    st.caption(f"{len(rows)} tag(s) — click a row to populate the form below")

    sel = event.selection.rows
    if sel:
        row = rows[sel[0]]
        if st.session_state.get("selected_tag_id") != row["id"]:
            st.session_state["selected_tag_id"] = row["id"]
            st.session_state["prefill"] = row
            st.session_state["prefill_pending"] = True
    else:
        st.session_state.pop("selected_tag_id", None)


def _tag_form_section(engine: Engine) -> None:
    st.subheader("Tag a Dataset by ID")
    st.caption("Use source IDs from the Dataset Browser or SQL Query results.")

    if st.session_state.pop("prefill_pending", False):
        p = st.session_state["prefill"]
        st.session_state["tf_source"] = p["source"]
        st.session_state["tf_source_id"] = p["source_id"]
        st.session_state["tf_concept"] = p["concept_tag"]
        st.session_state["tf_section"] = p["section_ref"] or ""
        st.session_state["tf_note"] = p["note_text"] or ""

    has_selection = "selected_tag_id" in st.session_state

    with st.form("tag_by_id_form", clear_on_submit=False):
        source = st.selectbox("Source", SOURCES, key="tf_source")
        source_id = st.text_input("Source ID", key="tf_source_id",
                                  placeholder="e.g. 000003 (DANDI) or ds003684 (OpenNeuro)")
        concept = st.text_input("Concept tag *", key="tf_concept",
                                placeholder="e.g. primary visual cortex")
        section = st.text_input("Section reference", key="tf_section",
                                placeholder="e.g. Augustine Ch13 p.312")
        note = st.text_area("Note", key="tf_note",
                            placeholder="What you observed, confirmed, or questioned")
        col_save, col_delete = st.columns(2)
        submitted = col_save.form_submit_button("Save Tag", use_container_width=True)
        delete_clicked = col_delete.form_submit_button(
            "Delete Tag", use_container_width=True,
            type="secondary", disabled=not has_selection,
        )

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
                    vs = st.session_state.get("vector_store")
                    if vs:
                        embed_note(vs, note_obj.id, source, source_id.strip(),
                                   concept.strip(), section.strip() or None, note.strip() or None)
                    st.success(f"Tagged `{source}:{source_id.strip()}` → '{concept.strip()}'")
                    st.rerun()
            except Exception as exc:
                st.error(f"Error saving tag: {exc}")

    if delete_clicked and has_selection:
        tag_id = st.session_state.pop("selected_tag_id")
        with get_session(engine) as session:
            delete_tag(session, tag_id)
        vs = st.session_state.get("vector_store")
        if vs:
            remove_note(vs, tag_id)
        for key in ("tf_source_id", "tf_concept", "tf_section", "tf_note", "prefill", "prefill_pending"):
            st.session_state.pop(key, None)
        st.rerun()


def render(engine: Engine) -> None:
    st.header("Study Log")
    _browse_section(engine)
    st.divider()
    _tag_form_section(engine)
