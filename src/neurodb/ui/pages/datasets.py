import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.query import search_datasets
from neurodb.study import tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def render(engine: Engine) -> None:
    st.header("Dataset Browser")

    col1, col2 = st.columns(2)
    keyword = col1.text_input("Search title/description", "")
    modality = col2.selectbox("Modality", ["Any", "MRI", "fMRI", "EEG", "MEG", "ISH"])

    with get_session(engine) as session:
        results = search_datasets(
            session,
            keyword=keyword or None,
            modality=None if modality == "Any" else modality,
        )

    if not results:
        st.info("No datasets found. Run an ingest first: `uv run scripts/ingest.py --source openneuro`")
        return

    data = [
        {
            "source": r["source"],
            "source_id": r["source_id"],
            "title": r["title"],
            "modality": r["modality"],
            "n_subjects": r["n_subjects"],
        }
        for r in results
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(results)} dataset(s) found")

    with st.expander("Tag a dataset from these results"):
        display_options = [f"{r['source']}:{r['source_id']}" for r in results]

        with st.form("inline_tag_form", clear_on_submit=True):
            selected = st.selectbox("Dataset", display_options)
            concept = st.text_input("Concept tag *", placeholder="e.g. retinotopic mapping")
            section = st.text_input("Section reference", placeholder="e.g. Augustine Ch13 p.312")
            note = st.text_area("Note", placeholder="What you observed or confirmed")
            submitted = st.form_submit_button("Save Tag")

        if submitted:
            if not concept.strip():
                st.error("Concept tag is required.")
            else:
                src, sid = selected.split(":", 1)
                try:
                    with get_session(engine) as session:
                        note_obj = tag_dataset(
                            session,
                            source=src,
                            source_id=sid,
                            concept_tag=concept.strip(),
                            section_ref=section.strip() or None,
                            note_text=note.strip() or None,
                        )
                    if note_obj is None:
                        st.error(f"Dataset not found in index: {selected}")
                    else:
                        st.success(f"Tagged {selected} → '{concept.strip()}'")
                except Exception as exc:
                    st.error(f"Error saving tag: {exc}")
