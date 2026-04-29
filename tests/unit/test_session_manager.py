"""Unit tests for session_manager — uses ephemeral ChromaDB and mocked Anthropic client."""
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock

import chromadb
import pytest

from neurodb.session_manager import AgentContextStore, SessionManager, format_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _store():
    """Each call gets an isolated collection — EphemeralClient shares state in chromadb 1.x."""
    client = chromadb.EphemeralClient()
    return AgentContextStore(client=client, collection_name=f"test_{uuid.uuid4().hex}")


def _mock_client(summary_text: str = "Topic: hippocampus\nConcepts covered: place cells"):
    block = SimpleNamespace(type="text", text=summary_text)
    response = SimpleNamespace(content=[block])
    client = MagicMock()
    client.messages.create.return_value = response
    return client


# ---------------------------------------------------------------------------
# AgentContextStore
# ---------------------------------------------------------------------------

def test_context_store_empty_returns_empty():
    store = _store()
    results = store.get_relevant("hippocampus", n=3)
    assert results == []


def test_context_store_add_and_retrieve():
    store = _store()
    store.add_summary("sess-1", "Topic: hippocampus\nConcepts covered: place cells", {"date": "2026-04-27"})
    results = store.get_relevant("hippocampus", n=3)
    assert len(results) == 1
    assert "place cells" in results[0]


def test_context_store_add_multiple_returns_most_relevant():
    store = _store()
    store.add_summary("sess-1", "Topic: hippocampus\nConcepts: place cells", {"date": "2026-04-27"})
    store.add_summary("sess-2", "Topic: motor cortex\nConcepts: M1 neurons", {"date": "2026-04-27"})
    results = store.get_relevant("hippocampus spatial navigation", n=3)
    assert any("place cells" in r for r in results)


def test_context_store_is_append_only():
    store = _store()
    store.add_summary("sess-1", "Topic: V1\nConcepts: retinotopy", {"date": "2026-04-27"})
    store.add_summary("sess-1", "Topic: V1 updated\nConcepts: orientation columns", {"date": "2026-04-28"})
    results = store.get_relevant("visual cortex", n=5)
    # Both entries exist (append-only, no upsert)
    assert len(results) == 2


# ---------------------------------------------------------------------------
# format_context
# ---------------------------------------------------------------------------

def test_format_context_empty():
    assert format_context([]) == ""


def test_format_context_single():
    result = format_context(["Topic: hippocampus\nConcepts: place cells"])
    assert "Prior sessions" in result
    assert "place cells" in result


def test_format_context_multiple():
    result = format_context(["Session A", "Session B"])
    assert "Session A" in result
    assert "Session B" in result


# ---------------------------------------------------------------------------
# SessionManager.start_session
# ---------------------------------------------------------------------------

def test_start_session_returns_session_id_and_context():
    store = _store()
    manager = SessionManager(store)
    session_id, context = manager.start_session("hippocampus")
    assert isinstance(session_id, str)
    assert len(session_id) > 0
    assert isinstance(context, str)


def test_start_session_cold_start_returns_empty_context():
    store = _store()
    manager = SessionManager(store)
    _, context = manager.start_session("hippocampus")
    assert context == ""


def test_start_session_with_prior_returns_context():
    store = _store()
    store.add_summary("old", "Topic: hippocampus\nConcepts: place cells", {})
    manager = SessionManager(store)
    _, context = manager.start_session("hippocampus")
    assert "place cells" in context


def test_start_session_ids_are_unique():
    store = _store()
    manager = SessionManager(store)
    id1, _ = manager.start_session("topic A")
    id2, _ = manager.start_session("topic B")
    assert id1 != id2


def test_start_session_empty_topic_returns_empty_context():
    store = _store()
    store.add_summary("old", "Topic: hippocampus\nConcepts: place cells", {})
    manager = SessionManager(store)
    _, context = manager.start_session("")
    assert context == ""


# ---------------------------------------------------------------------------
# SessionManager.end_session
# ---------------------------------------------------------------------------

def test_end_session_empty_conversation_skips_storage():
    store = _store()
    manager = SessionManager(store, client=_mock_client())
    manager.end_session("sess-1", [])
    assert store.get_relevant("anything", n=3) == []


def test_end_session_stores_summary():
    store = _store()
    manager = SessionManager(store, client=_mock_client("Topic: hippocampus\nConcepts: place cells"))
    conversation = [
        {"role": "user", "content": "Tell me about place cells"},
        {"role": "assistant", "content": "Place cells are neurons in the hippocampus..."},
    ]
    manager.end_session("sess-1", conversation)
    results = store.get_relevant("hippocampus", n=3)
    assert len(results) == 1
    assert "place cells" in results[0].lower()


def test_end_session_no_client_skips_silently():
    store = _store()
    manager = SessionManager(store, client=None)
    conversation = [{"role": "user", "content": "hi"}]
    manager.end_session("sess-1", conversation)
    assert store.get_relevant("hi", n=3) == []


def test_end_session_api_failure_does_not_raise():
    store = _store()
    bad_client = MagicMock()
    bad_client.messages.create.side_effect = RuntimeError("API down")
    manager = SessionManager(store, client=bad_client)
    conversation = [{"role": "user", "content": "something"}]
    # Must not raise
    manager.end_session("sess-1", conversation)


# ---------------------------------------------------------------------------
# NeuroAgent prior_context injection
# ---------------------------------------------------------------------------

def test_agent_injects_prior_context_into_system_prompt():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from sqlalchemy import create_engine
    from neurodb.schema import DatasetIndex
    from neurodb.agent import NeuroAgent

    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)

    mock_client = MagicMock()
    resp = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])
    mock_client.messages.create.return_value = resp

    agent = NeuroAgent(mock_client, engine, prior_context="Prior sessions: place cells explored")
    list(agent.chat("hello", []))

    system_arg = mock_client.messages.create.call_args[1]["system"]
    assert "Prior sessions" in system_arg
    assert "place cells" in system_arg


def test_agent_no_prior_context_omits_block():
    from types import SimpleNamespace
    from unittest.mock import MagicMock
    from sqlalchemy import create_engine
    from neurodb.schema import DatasetIndex
    from neurodb.agent import NeuroAgent

    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)

    mock_client = MagicMock()
    resp = SimpleNamespace(stop_reason="end_turn", content=[SimpleNamespace(type="text", text="ok")])
    mock_client.messages.create.return_value = resp

    agent = NeuroAgent(mock_client, engine)
    list(agent.chat("hello", []))

    system_arg = mock_client.messages.create.call_args[1]["system"]
    assert "Prior sessions" not in system_arg
