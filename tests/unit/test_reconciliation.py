"""Tests for the FullTextAcquired reconciliation handler + event_log audit."""
from __future__ import annotations

import json
import uuid

import chromadb
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb import events
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.reconciliation import (
    reconcile_full_text_acquired,
    register_reconciliation,
)
from neurodb.schema import Base, EventLog, Paper


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


def _engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _stores():
    client = chromadb.EphemeralClient()
    return (
        KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                              collection_name=f"kl_{uuid.uuid4().hex}"),
        ChunkStore(client=client, embedder=_StubEmbedder(),
                   collection_name=f"ck_{uuid.uuid4().hex}"),
    )


def _add_full_text_paper(engine) -> int:
    with get_session(engine) as session:
        paper = Paper(title="Hopfield 1982", normalized_title="hopfield 1982",
                      source_type="paper", topic_context="memory",
                      status="approved", queued_at="2026-01-01T00:00:00",
                      authors_json=json.dumps(["J. Hopfield"]), year=1982,
                      data_tier="full_text", currency_status="current")
        session.add(paper)
        session.flush()
        return paper.id


def _seed_stale_stores(knowledge_store, chunk_store, paper_id):
    knowledge_store.add_summary(source_id=paper_id, title="Hopfield 1982", doi=None,
                                topic_context="memory", summary="summary body",
                                data_tier="abstract")  # stale tier
    chunk_store.add_chunks(paper_id=paper_id, title="Hopfield 1982", year=None,
                           currency_status="current", text_source="pdf_pymupdf",
                           chunks=[Chunk(chunk_index=0, text="alpha",
                                         section=None, char_start=0, char_end=5)])


def _summary_meta(knowledge_store, paper_id):
    return knowledge_store.search("summary body", n=1)[0]["metadata"]


def _chunk_meta(chunk_store):
    return chunk_store.search("alpha", n=1, min_score=-1.0)[0]


def test_reconcile_flips_stale_tier_and_pushes_authors():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    detail = reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                          source_id=paper_id)
    assert detail["summary_updated"] is True and detail["chunks_updated"] == 1
    meta = _summary_meta(knowledge_store, paper_id)
    assert meta["data_tier"] == "full_text"
    assert meta["authors"] == "J. Hopfield"
    assert meta["year"] == "1982"
    chunk = _chunk_meta(chunk_store)
    assert chunk["year"] == "1982"

    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert len(rows) == 1
        assert rows[0].event_name == "full_text_acquired"
        assert rows[0].entity_id == str(paper_id)
        assert rows[0].status == "ok"


def test_reconcile_is_idempotent():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                 source_id=paper_id)
    first_summary = _summary_meta(knowledge_store, paper_id)
    reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                 source_id=paper_id)
    assert _summary_meta(knowledge_store, paper_id) == first_summary
    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert [r.status for r in rows] == ["ok", "ok"]  # append-only audit


def test_reconcile_missing_paper_logs_error_row_and_raises():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    with pytest.raises(RuntimeError):
        reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                     source_id=999)
    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert len(rows) == 1 and rows[0].status == "error"


def test_reconcile_tolerates_missing_stores():
    engine = _engine()
    paper_id = _add_full_text_paper(engine)
    detail = reconcile_full_text_acquired(engine, None, None, source_id=paper_id)
    assert detail["summary_updated"] is False and detail["chunks_updated"] == 0
    assert len(detail["skipped"]) == 2


def test_register_reconciliation_reacts_to_emit():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    register_reconciliation(engine, knowledge_store, chunk_store)
    register_reconciliation(engine, knowledge_store, chunk_store)  # keyed: no dup
    outcomes = events.emit(events.FULL_TEXT_ACQUIRED, source_id=paper_id)
    assert len(outcomes) == 1 and outcomes[0]["status"] == "ok"
    assert _summary_meta(knowledge_store, paper_id)["data_tier"] == "full_text"
