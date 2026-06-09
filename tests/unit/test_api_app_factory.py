"""Tests for FastAPI app factory runtime store wiring."""
from types import SimpleNamespace
from unittest.mock import patch

from neurodb.api.app import _build_runtime_stores, _chroma_path_for_db


def test_chroma_path_for_duckdb_matches_legacy_ui_convention():
    assert _chroma_path_for_db("neurodb.duckdb") == "neurodb_chroma"
    assert _chroma_path_for_db("/tmp/manual.duckdb") == "/tmp/manual_chroma"
    assert _chroma_path_for_db("/tmp/manual") == "/tmp/manual_chroma"


def test_build_runtime_stores_initializes_chroma_backed_stores():
    engine = object()

    with (
        patch("neurodb.embedder.Embedder") as embedder_cls,
        patch("neurodb.vector_store.VectorStore") as vector_cls,
        patch("neurodb.knowledge_store.KnowledgeLibraryStore") as knowledge_cls,
        patch("neurodb.session_manager.AgentContextStore") as context_cls,
        patch("neurodb.session_manager.SessionManager") as session_cls,
        patch("neurodb.config.provider_factory.build_provider_clients", return_value={}),
    ):
        embedder = embedder_cls.return_value
        vector_store = vector_cls.return_value
        knowledge_store = knowledge_cls.return_value
        context_store = context_cls.return_value
        session_manager = session_cls.return_value

        stores = _build_runtime_stores("neurodb.duckdb", engine)

    vector_cls.assert_called_once_with(path="neurodb_chroma", embedder=embedder)
    knowledge_cls.assert_called_once_with(path="neurodb_chroma", embedder=embedder)
    context_cls.assert_called_once_with(path="neurodb_chroma")
    session_cls.assert_called_once_with(context_store, engine=engine)
    assert stores == {
        "vector_store": vector_store,
        "knowledge_store": knowledge_store,
        "context_store": context_store,
        "session_manager": session_manager,
    }


def test_build_runtime_stores_passes_summary_route_to_session_manager():
    engine = object()
    route = SimpleNamespace(
        model_client=object(),
        model_id="summary-model",
        provider="anthropic",
        max_tokens=512,
    )

    class FakeTaskRouter:
        def __init__(self, providers):
            self.providers = providers

        def route(self, task_type, *, engine=None):
            assert task_type == "summary.session"
            assert engine is not None
            return route

    with (
        patch("neurodb.embedder.Embedder"),
        patch("neurodb.vector_store.VectorStore"),
        patch("neurodb.knowledge_store.KnowledgeLibraryStore"),
        patch("neurodb.session_manager.AgentContextStore") as context_cls,
        patch("neurodb.session_manager.SessionManager") as session_cls,
        patch(
            "neurodb.config.provider_factory.build_provider_clients",
            return_value={"anthropic": object()},
        ),
        patch("neurodb.config.task_router.TaskRouter", FakeTaskRouter),
    ):
        context_store = context_cls.return_value
        _build_runtime_stores("neurodb.duckdb", engine)

    session_cls.assert_called_once_with(
        context_store,
        engine=engine,
        model_client=route.model_client,
        summary_model="summary-model",
        summary_provider="anthropic",
        summary_max_tokens=512,
    )
