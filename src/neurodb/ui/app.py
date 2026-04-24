"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
"""
import sys

import streamlit as st

import neurodb.connectors.allen_brain  # noqa: F401 — registers AllenDataset
import neurodb.connectors.dandi  # noqa: F401 — registers DandiDataset
import neurodb.connectors.neurovault  # noqa: F401 — registers NeuroVaultDataset
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset
from neurodb.db import create_views, get_engine, init_db

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")

db_path = "neurodb.duckdb"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

engine = get_engine(f"duckdb:///{db_path}")
init_db(engine)
create_views(engine)

st.session_state["engine"] = engine

st.title("NeuroDb Explorer")
st.caption(f"Connected to: `{db_path}`")

page = st.sidebar.radio("Navigate", ["Dataset Browser", "SQL Query", "Study Log"])

if page == "Dataset Browser":
    from neurodb.ui.pages.datasets import render
    render(engine)
elif page == "SQL Query":
    from neurodb.ui.pages.query import render
    render(engine)
elif page == "Study Log":
    from neurodb.ui.pages.study_log import render
    render(engine)
