"""FastAPI dependency providers for the NeuroDb API."""
from __future__ import annotations

from fastapi import Request
from sqlalchemy import Engine

VALID_AGENT_MODES: frozenset[str] = frozenset(
    {"local_db", "external_db", "neuro_tutor", "neuro_research"}
)


def get_engine(request: Request) -> Engine:
    return request.app.state.engine


def get_vector_store(request: Request):
    return request.app.state.vector_store


def get_knowledge_store(request: Request):
    return request.app.state.knowledge_store


def get_chunk_store(request: Request):
    return request.app.state.chunk_store


def get_research_stores(request: Request) -> dict:
    return {
        "vector_store": request.app.state.vector_store,
        "knowledge_store": request.app.state.knowledge_store,
        "chunk_store": request.app.state.chunk_store,
        "context_store": request.app.state.context_store,
    }


def get_task_store(request: Request) -> dict:
    return request.app.state.tasks
