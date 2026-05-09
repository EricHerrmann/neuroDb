"""FastAPI app factory."""
from __future__ import annotations

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
