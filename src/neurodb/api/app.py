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


def app_factory() -> FastAPI:
    """Zero-arg factory for uvicorn --factory.

    Usage: uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
    DB path read from NEURODB_DB_PATH env var, defaulting to neurodb.duckdb.
    """
    from dotenv import load_dotenv

    from neurodb.db import create_views, get_engine, init_db

    load_dotenv()
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    engine = get_engine(f"duckdb:///{db_path}")
    init_db(engine)
    create_views(engine)
    return create_app(engine)
