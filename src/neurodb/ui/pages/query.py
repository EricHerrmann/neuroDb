import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text


def render(engine: Engine):
    st.header("SQL Query")
    st.caption("Run raw SQL against the local NeuroDb. Tables: `openneuro_datasets`, `datasets_index`, `subjects`, `ingest_runs`.")

    default_query = "SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;"
    sql = st.text_area("SQL", value=default_query, height=120)

    if st.button("Run Query"):
        try:
            with engine.connect() as conn:
                result = conn.execute(text(sql))
                rows = result.fetchall()
                cols = list(result.keys())
            df = pd.DataFrame(rows, columns=cols)
            st.dataframe(df, width="stretch")
            st.caption(f"{len(df)} row(s)")
        except Exception as e:
            st.error(f"Query error: {e}")
