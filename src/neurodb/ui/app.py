"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
"""
import sys

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

import neurodb.connectors.allen_brain  # noqa: F401 — registers AllenDataset
import neurodb.connectors.dandi  # noqa: F401 — registers DandiDataset
import neurodb.connectors.neurovault  # noqa: F401 — registers NeuroVaultDataset
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset
from neurodb.db import create_views, get_engine, init_db
from neurodb.embedder import Embedder
from neurodb.vector_store import VectorStore

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")

db_path = "neurodb.duckdb"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

engine = get_engine(f"duckdb:///{db_path}")
init_db(engine)
create_views(engine)

st.session_state["engine"] = engine

if "vector_store" not in st.session_state:
    chroma_path = db_path.replace(".duckdb", "_chroma")
    st.session_state["vector_store"] = VectorStore(path=chroma_path, embedder=Embedder())

# --- Sidebar: Research Assistant (natively resizable + collapsible) ---
with st.sidebar:
    st.caption(f"DB: `{db_path}`")
    if st.button("Clear Chat History", use_container_width=True):
        st.session_state["chat_history"] = []
        st.rerun()
    st.divider()
    from neurodb.ui.pages.chat import render_panel
    render_panel(engine)

# --- Main area: data tabs at full width ---
st.title("NeuroDb Explorer")
tab_datasets, tab_sql, tab_study = st.tabs(["Dataset Browser", "SQL Query", "Study Log"])

with tab_datasets:
    from neurodb.ui.pages.datasets import render
    render(engine)

with tab_sql:
    from neurodb.ui.pages.query import render
    render(engine)

with tab_study:
    from neurodb.ui.pages.study_log import render
    render(engine)
