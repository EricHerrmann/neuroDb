import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text

from neurodb.db import get_session
from neurodb.study import tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def _browse_section(engine: Engine) -> None:
    st.subheader("Your Study Tags")

    col1, col2 = st.columns(2)
    concept_filter = col1.text_input("Filter by concept", "")
    source_filter = col2.selectbox("Filter by source", ["All"] + SOURCES)

    conditions = []
    params: dict = {}
    if concept_filter:
        conditions.append("LOWER(sn.concept_tag) LIKE :concept")
        params["concept"] = f"%{concept_filter.lower()}%"
    if source_filter != "All":
        conditions.append("di.source = :source")
        params["source"] = source_filter

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"""
        SELECT
            sn.concept_tag,
            sn.section_ref,
            sn.note_text,
            sn.tagged_at,
            di.source,
            di.source_id
        FROM study_notes sn
        JOIN datasets_index di ON di.id = sn.index_id
        {where}
        ORDER BY sn.tagged_at DESC
    """)  # noqa: S608

    with engine.connect() as conn:
        result = conn.execute(sql, params)
        rows = result.fetchall()
        cols = list(result.keys())

    if not rows:
        st.info("No study tags yet. Tag a dataset from the Dataset Browser or use the form below.")
        return

    df = pd.DataFrame(rows, columns=cols)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(rows)} tag(s)")


def render(engine: Engine) -> None:
    st.header("Study Log")
    _browse_section(engine)
