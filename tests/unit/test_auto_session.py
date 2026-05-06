from types import SimpleNamespace
from unittest.mock import MagicMock
import uuid

import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.schema import Base, ChatSession
from neurodb.session_manager import AgentContextStore, SessionManager
from neurodb.ui.pages import chat as chat_module


def _store():
    client = chromadb.EphemeralClient()
    return AgentContextStore(client=client, collection_name=f"auto_{uuid.uuid4().hex}")


def _manager(store=None, summary="Topic: LTP\nConcepts covered: plasticity"):
    block = SimpleNamespace(type="text", text=summary)
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(content=[block])
    return SessionManager(store or _store(), client=client)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_get_context_for_topic_returns_empty_when_no_sessions():
    assert _manager().get_context_for_topic("hippocampus") == ""


def test_get_context_for_topic_returns_context_string_after_session():
    store = _store()
    store.add_summary("s1", "Topic: LTP\nConcepts covered: hippocampus", {"session_id": "s1"})
    manager = _manager(store)
    context = manager.get_context_for_topic("LTP hippocampus", threshold=1.0)
    assert "LTP" in context


def test_end_session_returns_summary_string():
    conversation = [
        {"role": "user", "content": "What is LTP?"},
        {"role": "assistant", "content": [{"type": "text", "text": "LTP is..."}]},
    ]
    summary = _manager().end_session("session-abc", conversation)
    assert isinstance(summary, str)
    assert "LTP" in summary


def test_end_session_returns_none_on_empty_conversation():
    assert _manager().end_session("session-abc", []) is None


def test_auto_summarize_threshold_counts_user_turns():
    api_messages = [
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "resp1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "resp2"},
        {"role": "user", "content": "msg3"},
    ]
    user_turns = sum(1 for msg in api_messages if msg["role"] == "user")
    assert user_turns == 3


def test_chat_session_row_written_after_summary():
    engine = _engine()
    api_messages = [
        {"role": "user", "content": "What is LTP?"},
        {"role": "assistant", "content": "LTP is long-term potentiation."},
        {"role": "user", "content": "How does calcium help?"},
        {"role": "assistant", "content": "Calcium enters through NMDA receptors."},
        {"role": "user", "content": "What should I study next?"},
    ]
    summary = _manager().end_session("test-session-id", api_messages)
    assert summary is not None

    with Session(engine) as session:
        session.add(ChatSession(
            session_id="test-session-id",
            inferred_topic=api_messages[0]["content"][:200],
            agent_mode="neuro_tutor",
            started_at="2026-05-05T10:00:00",
            ended_at="2026-05-05T10:30:00",
            summary_preview=summary[:200],
            message_count=3,
        ))
        session.commit()

    with Session(engine) as session:
        row = session.query(ChatSession).one()
        assert row.session_id == "test-session-id"
        assert row.message_count == 3


def test_write_chat_session_draft_creates_row_with_no_ended_at(monkeypatch):
    """Draft row is written immediately on first message; ended_at and summary_preview are None."""
    engine = _engine()
    monkeypatch.setattr(chat_module.st, "session_state", {"agent_mode": "neuro_tutor"})

    chat_module._write_chat_session_draft(engine, "sess-draft", "What is LTP?")

    with Session(engine) as session:
        row = session.query(ChatSession).filter_by(session_id="sess-draft").one_or_none()
    assert row is not None
    assert row.ended_at is None
    assert row.summary_preview is None
    assert row.inferred_topic == "What is LTP?"
    assert row.agent_mode == "neuro_tutor"


def test_write_chat_session_row_updates_existing_draft(monkeypatch):
    """Finalizing a session updates the draft row in place — only one row exists after."""
    engine = _engine()
    session_id = "sess-finalize"
    monkeypatch.setattr(chat_module.st, "session_state", {
        "agent_mode": "neuro_tutor",
        "session_started_at": "2026-05-06T10:00:00",
    })

    chat_module._write_chat_session_draft(engine, session_id, "What is LTP?")

    api_messages = [
        {"role": "user", "content": "What is LTP?"},
        {"role": "assistant", "content": "LTP is long-term potentiation."},
        {"role": "user", "content": "Tell me more"},
        {"role": "assistant", "content": "Sure..."},
        {"role": "user", "content": "Thanks"},
    ]
    chat_module._write_chat_session_row(engine, session_id, api_messages, 3, "Topic: LTP\nDate: 2026-05-06")

    with Session(engine) as session:
        rows = session.query(ChatSession).filter_by(session_id=session_id).all()

    assert len(rows) == 1
    assert rows[0].ended_at is not None
    assert rows[0].summary_preview == "Topic: LTP\nDate: 2026-05-06"
    assert rows[0].message_count == 3


def test_write_chat_session_row_inserts_if_no_draft(monkeypatch):
    """If no draft row exists, _write_chat_session_row inserts a new complete row."""
    engine = _engine()
    monkeypatch.setattr(chat_module.st, "session_state", {
        "agent_mode": "neuro_tutor",
        "session_started_at": "2026-05-06T10:00:00",
    })

    api_messages = [
        {"role": "user", "content": "What is LTD?"},
        {"role": "assistant", "content": "LTD is long-term depression."},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "resp2"},
        {"role": "user", "content": "msg3"},
    ]
    chat_module._write_chat_session_row(engine, "sess-nodraft", api_messages, 3, "Topic: LTD")

    with Session(engine) as session:
        rows = session.query(ChatSession).filter_by(session_id="sess-nodraft").all()

    assert len(rows) == 1
    assert rows[0].ended_at is not None
    assert rows[0].message_count == 3

