"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
"""
import sys

from dotenv import load_dotenv
load_dotenv()

import streamlit as st

import neurodb.connectors  # noqa: F401 — registers all connector ORM models with Base.metadata
from neurodb.db import create_views, get_engine, init_db
from neurodb.embedder import Embedder
from neurodb.vector_store import VectorStore

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")


def _inject_ui_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
          --ndb-ink: #f8fafc;
          --ndb-charcoal: #0f172a;
          --ndb-charcoal-2: #1e293b;
          --ndb-active: #1e3a8a;
          --ndb-active-2: #1d4ed8;
          --ndb-border: #cbd5e1;
          --ndb-muted: #475569;
          --ndb-surface: #ffffff;
        }

        .stApp {
          background: linear-gradient(180deg, #f8fafc 0%, #eef2f7 100%);
        }

        button[kind="primary"],
        button[kind="primaryFormSubmit"] {
          background: var(--ndb-charcoal) !important;
          color: var(--ndb-ink) !important;
          border: 1px solid var(--ndb-charcoal) !important;
          font-weight: 700 !important;
          box-shadow: 0 1px 2px rgba(15, 23, 42, 0.16) !important;
        }

        button[kind="primary"]:hover,
        button[kind="primaryFormSubmit"]:hover {
          background: var(--ndb-charcoal-2) !important;
          color: var(--ndb-ink) !important;
        }

        button[kind="secondary"],
        button[kind="secondaryFormSubmit"] {
          background: var(--ndb-surface) !important;
          color: var(--ndb-charcoal) !important;
          border: 1px solid var(--ndb-border) !important;
        }

        button[kind="secondary"]:hover,
        button[kind="secondaryFormSubmit"]:hover {
          background: #e2e8f0 !important;
          color: var(--ndb-charcoal) !important;
        }

        div[role="tablist"] button[aria-selected="true"] {
          background: var(--ndb-active) !important;
          color: var(--ndb-ink) !important;
          border-radius: 0.6rem !important;
          border: 1px solid var(--ndb-active) !important;
          font-weight: 700 !important;
          box-shadow: 0 2px 6px rgba(30, 58, 138, 0.22) !important;
        }

        div[role="tablist"] button[aria-selected="false"] {
          background: rgba(255, 255, 255, 0.78) !important;
          color: var(--ndb-muted) !important;
          border: 1px solid var(--ndb-border) !important;
          border-radius: 0.6rem !important;
        }

        div[role="radiogroup"] label[data-baseweb="radio"] > div:first-child {
          border-color: var(--ndb-border) !important;
        }

        div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) {
          background: var(--ndb-active) !important;
          color: var(--ndb-ink) !important;
          border: 1px solid var(--ndb-active) !important;
          border-radius: 999px !important;
          padding: 0.2rem 0.7rem !important;
        }

        div[role="radiogroup"] label[data-baseweb="radio"]:has(input:checked) * {
          color: var(--ndb-ink) !important;
        }

        </style>
        """,
        unsafe_allow_html=True,
    )

db_path = "neurodb.duckdb"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

st.session_state["db_path"] = db_path

engine = get_engine(f"duckdb:///{db_path}")
init_db(engine)
create_views(engine)
_inject_ui_styles()

st.session_state["engine"] = engine

if "vector_store" not in st.session_state:
    chroma_path = db_path.replace(".duckdb", "_chroma")
    st.session_state["vector_store"] = VectorStore(path=chroma_path, embedder=Embedder())

if "session_manager" not in st.session_state:
    import os
    import anthropic
    from neurodb.session_manager import AgentContextStore, SessionManager
    chroma_path = db_path.replace(".duckdb", "_chroma")
    context_store = AgentContextStore(path=chroma_path)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    client = anthropic.Anthropic(api_key=api_key) if api_key else None
    st.session_state["session_manager"] = SessionManager(context_store, client=client)

if "active_prior_context" not in st.session_state:
    manager = st.session_state.get("session_manager")
    st.session_state["active_prior_context"] = (
        manager.get_most_recent_context(engine) if manager is not None else ""
    )

if "knowledge_store" not in st.session_state:
    from neurodb.knowledge_store import KnowledgeLibraryStore
    chroma_path = db_path.replace(".duckdb", "_chroma")
    st.session_state["knowledge_store"] = KnowledgeLibraryStore(
        path=chroma_path,
        embedder=Embedder(),
    )

from neurodb.ui.sidebar import render_sidebar

render_sidebar(engine)

col_chat, col_workspace = st.columns([1.7, 1.1], gap="large")

with col_chat:
    from neurodb.ui.pages.chat import render_panel
    render_panel(engine, transcript_height=480)

with col_workspace:
    tab_suggestions, tab_study, tab_datasets, tab_registry, tab_knowledge, tab_sql = st.tabs([
        "Suggestions",
        "Study Log",
        "Datasets",
        "Registry",
        "Knowledge Library",
        "SQL",
    ])

    with tab_suggestions:
        from neurodb.ui.pages.suggestions import render
        render(engine)

    with tab_study:
        from neurodb.ui.pages.study_log import render
        render(engine)

    with tab_datasets:
        from neurodb.ui.pages.datasets import render
        render(engine)

    with tab_registry:
        from neurodb.ui.pages.learning_registry import render
        render(engine)

    with tab_knowledge:
        from neurodb.ui.pages.knowledge_library import render
        render(engine)

    with tab_sql:
        from neurodb.ui.pages.query import render
        render(engine)
