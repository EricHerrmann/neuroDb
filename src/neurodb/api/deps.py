"""FastAPI dependency providers for the NeuroDb API."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import Engine


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_research_stores(request: Request) -> dict:
    return {
        "vector_store": request.app.state.vector_store,
        "knowledge_store": request.app.state.knowledge_store,
        "context_store": request.app.state.context_store,
    }
