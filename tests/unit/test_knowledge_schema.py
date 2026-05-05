import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from neurodb.schema import Base, ChatSession, KnowledgeSource


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_knowledge_sources_table_created():
    inspector = inspect(_engine())
    assert "knowledge_sources" in inspector.get_table_names()


def test_chat_sessions_table_created():
    inspector = inspect(_engine())
    assert "chat_sessions" in inspector.get_table_names()


def test_knowledge_source_doi_unique():
    engine = _engine()
    with Session(engine) as session:
        session.add(KnowledgeSource(
            title="Paper A",
            normalized_title="paper a",
            doi="10.1234/test",
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        ))
        session.commit()
        session.add(KnowledgeSource(
            title="Paper B",
            normalized_title="paper b",
            doi="10.1234/test",
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_knowledge_source_normalized_title_unique():
    engine = _engine()
    with Session(engine) as session:
        session.add(KnowledgeSource(
            title="Paper A",
            normalized_title="paper a",
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        ))
        session.commit()
        session.add(KnowledgeSource(
            title="paper a",
            normalized_title="paper a",
            source_type="review",
            topic_context="hippocampus",
            status="pending",
            queued_at="2026-05-05T00:00:01",
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_chat_session_session_id_unique():
    engine = _engine()
    with Session(engine) as session:
        session.add(ChatSession(
            session_id="abc-123",
            inferred_topic="memory",
            agent_mode="neuro_tutor",
            started_at="2026-05-05T00:00:00",
            message_count=3,
        ))
        session.commit()
        session.add(ChatSession(
            session_id="abc-123",
            inferred_topic="LTP",
            agent_mode="neuro_tutor",
            started_at="2026-05-05T00:01:00",
            message_count=4,
        ))
        with pytest.raises(IntegrityError):
            session.commit()


def test_knowledge_source_optional_fields_default_to_none():
    engine = _engine()
    with Session(engine) as session:
        row = KnowledgeSource(
            title="Some Review",
            normalized_title="some review",
            source_type="review",
            topic_context="plasticity",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        )
        session.add(row)
        session.commit()
        assert row.id is not None
        assert row.doi is None
        assert row.url is None
        assert row.summary is None
        assert row.chroma_id is None
        assert row.reviewed_at is None

