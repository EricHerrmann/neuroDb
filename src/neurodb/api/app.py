"""FastAPI app factory."""
from __future__ import annotations

import os

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

    from neurodb.api.routes import status, preferences, research, chat

    app.include_router(status.router, prefix="/api")
    app.include_router(preferences.router, prefix="/api")
    app.include_router(research.router, prefix="/api/research")
    app.include_router(chat.router, prefix="/api")

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
