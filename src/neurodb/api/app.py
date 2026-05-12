"""FastAPI app factory."""
from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI
from sqlalchemy import Engine


def create_app(
    engine: Engine,
    *,
    vector_store=None,
    knowledge_store=None,
    context_store=None,
    session_manager=None,
) -> FastAPI:
    """Create and configure FastAPI app with stores and routes."""
    app = FastAPI(title="NeuroDb API")
    app.state.engine = engine
    app.state.vector_store = vector_store
    app.state.knowledge_store = knowledge_store
    app.state.context_store = context_store
    app.state.session_manager = session_manager
    app.state.tasks = {}

    from neurodb.api.routes import (
        chat,
        datasets,
        knowledge_library,
        preferences,
        registry,
        research,
        sessions,
        sql,
        status,
        study_log,
        suggestions,
        tasks,
    )

    app.include_router(status.router, prefix="/api")
    app.include_router(tasks.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(research.router, prefix="/api/research")
    app.include_router(chat.router, prefix="/api")
    app.include_router(study_log.router, prefix="/api")
    app.include_router(sessions.router, prefix="/api")
    app.include_router(suggestions.router, prefix="/api/suggestions")
    app.include_router(datasets.router, prefix="/api/datasets")
    app.include_router(registry.router, prefix="/api/registry")
    app.include_router(knowledge_library.router, prefix="/api/knowledge-library")
    app.include_router(sql.router, prefix="/api/sql")

    dist_dir = Path("frontend/dist")
    if dist_dir.exists():
        from fastapi.staticfiles import StaticFiles

        app.mount("/", StaticFiles(directory=dist_dir, html=True), name="static")

    return app


def _chroma_path_for_db(db_path: str) -> str:
    if db_path.endswith(".duckdb"):
        return db_path.replace(".duckdb", "_chroma")
    return f"{db_path}_chroma"


def _build_runtime_stores(db_path: str, engine: Engine) -> dict:
    """Build the same Chroma-backed runtime stores used by the Streamlit app."""
    from neurodb.config.provider_factory import build_provider_clients
    from neurodb.config.task_router import TaskRouter
    from neurodb.embedder import Embedder
    from neurodb.knowledge_store import KnowledgeLibraryStore
    from neurodb.session_manager import AgentContextStore, SessionManager
    from neurodb.vector_store import VectorStore

    chroma_path = _chroma_path_for_db(db_path)
    embedder = Embedder()
    vector_store = VectorStore(path=chroma_path, embedder=embedder)
    knowledge_store = KnowledgeLibraryStore(path=chroma_path, embedder=embedder)
    context_store = AgentContextStore(path=chroma_path)

    route = None
    providers = build_provider_clients()
    if providers:
        try:
            route = TaskRouter(providers).route("summary.session")
        except KeyError:
            route = None

    session_kwargs = {"engine": engine}
    if route is not None:
        session_kwargs.update({
            "model_client": route.model_client,
            "summary_model": route.model_id,
            "summary_provider": route.provider,
            "summary_max_tokens": route.max_tokens,
        })

    return {
        "vector_store": vector_store,
        "knowledge_store": knowledge_store,
        "context_store": context_store,
        "session_manager": SessionManager(context_store, **session_kwargs),
    }


def app_factory() -> FastAPI:
    """Zero-arg factory for uvicorn --factory.

    Usage: uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
    DB path read from NEURODB_DB_PATH env var, defaulting to neurodb.duckdb.
    """
    from dotenv import load_dotenv

    import neurodb.connectors  # noqa: F401 — registers connector ORM models
    from neurodb.db import create_views, get_engine, init_db

    load_dotenv()
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    engine = get_engine(f"duckdb:///{db_path}")
    init_db(engine)
    create_views(engine)
    stores = _build_runtime_stores(db_path, engine)
    return create_app(engine, **stores)
