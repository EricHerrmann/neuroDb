"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
"""
import sys
import streamlit as st
from neurodb.db import get_engine, init_db
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset with Base.metadata

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")

# Accept --db flag from command line; default to neurodb.db
db_path = "neurodb.db"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

engine = get_engine(f"sqlite:///{db_path}")
init_db(engine)

st.session_state["engine"] = engine

st.title("NeuroDb Explorer")
st.caption(f"Connected to: `{db_path}`")

page = st.sidebar.radio("Navigate", ["Dataset Browser", "SQL Query"])

if page == "Dataset Browser":
    from neurodb.ui.pages.datasets import render
    render(engine)
elif page == "SQL Query":
    from neurodb.ui.pages.query import render
    render(engine)
