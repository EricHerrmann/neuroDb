import pandas as pd
import streamlit as st
from sqlalchemy import Engine
from neurodb.db import get_session
from neurodb.query import search_datasets


def render(engine: Engine):
    st.header("Dataset Browser")

    col1, col2 = st.columns(2)
    keyword = col1.text_input("Search title/description", "")
    modality = col2.selectbox("Modality", ["Any", "MRI", "fMRI", "EEG", "MEG"])

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
            "ID": ds.source_id,
            "Title": ds.title,
            "Modality": ds.modality,
            "Subjects": ds.n_subjects,
            "DOI": ds.doi or "",
        }
        for ds in results
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(results)} dataset(s) found")
