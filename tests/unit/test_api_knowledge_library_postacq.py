"""Integration tests: acquisition triggers backfill + FullTextAcquired reconciliation."""
from __future__ import annotations

import json
import uuid

import chromadb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb import events
from neurodb.api.routes import knowledge_library as kl_module
from neurodb.api.routes.knowledge_library import router
from neurodb.chunk_store import ChunkStore
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.metadata_lookup import PaperMetadata
from neurodb.reconciliation import register_reconciliation
from neurodb.schema import Base, EventLog, Paper

_FOUND = PaperMetadata(
    source="semantic_scholar",
    authors=["J. Hopfield"],
    abstract="Collective properties emerge.",
    year=1982,
    doi="10.1073/pnas.79.8.2554",
    url="https://doi.org/10.1073/pnas.79.8.2554",
)

_BODY_TEXT = ("Content-addressable memory emerges from collective dynamics. " * 30)


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _StubMetadataClient:
    def lookup(self, *, doi=None, title=None):
        return _FOUND


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


@pytest.fixture(autouse=True)
def _stub_metadata_client(monkeypatch):
    monkeypatch.setattr(kl_module, "_build_metadata_client",
                        lambda: _StubMetadataClient())


def _make_env():
    engine = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    client = chromadb.EphemeralClient()
    knowledge_store = KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                                            collection_name=f"kl_{uuid.uuid4().hex}")
    chunk_store = ChunkStore(client=client, embedder=_StubEmbedder(),
                             collection_name=f"ck_{uuid.uuid4().hex}")
    register_reconciliation(engine, knowledge_store, chunk_store)

    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store
    app.state.chunk_store = chunk_store
    app.state.tasks = {}
    app.include_router(router, prefix="/api/knowledge-library")
    return TestClient(app), engine, knowledge_store, chunk_store


def _insert_approved_paper(engine, *, doi="10.1073/pnas.79.8.2554") -> int:
    with get_session(engine) as session:
        paper = Paper(title="Hopfield 1982", normalized_title="hopfield 1982",
                      source_type="paper", topic_context="memory",
                      status="approved", queued_at="2026-01-01T00:00:00",
                      reviewed_at="2026-01-02T00:00:00", doi=doi)
        session.add(paper)
        session.flush()
        return paper.id


def _acquire(client, source_id):
    resp = client.post(f"/api/knowledge-library/{source_id}/acquire-full-text",
                       json={"text": _BODY_TEXT, "format": "txt"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_acquire_backfills_authors_and_reconciles_stores():
    client, engine, knowledge_store, chunk_store = _make_env()
    source_id = _insert_approved_paper(engine)
    knowledge_store.add_summary(source_id=source_id, title="Hopfield 1982",
                                doi=None, topic_context="memory",
                                summary="summary body", data_tier="abstract")

    item = _acquire(client, source_id)
    assert item["data_tier"] == "full_text"

    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        assert json.loads(paper.authors_json) == ["J. Hopfield"]
        assert paper.year == 1982
        rows = session.query(EventLog).order_by(EventLog.id.asc()).all()
        assert [r.event_name for r in rows] == ["metadata_backfill", "full_text_acquired"]
        assert all(r.status == "ok" for r in rows)
        backfill_detail = json.loads(rows[0].detail_json)
        assert backfill_detail["filled"]["authors_json"] == "semantic_scholar"

    summary_meta = knowledge_store.search("summary body", n=1)[0]["metadata"]
    assert summary_meta["data_tier"] == "full_text"
    assert summary_meta["authors"] == "J. Hopfield"
    chunk_meta = chunk_store.search("collective dynamics", n=1, min_score=-1.0)[0]
    assert chunk_meta["year"] == "1982"


def test_reacquire_is_idempotent():
    client, engine, knowledge_store, chunk_store = _make_env()
    source_id = _insert_approved_paper(engine)
    knowledge_store.add_summary(source_id=source_id, title="Hopfield 1982",
                                doi=None, topic_context="memory",
                                summary="summary body", data_tier="abstract")

    _acquire(client, source_id)
    first_chunks = chunk_store._collection.count()
    first_meta = knowledge_store.search("summary body", n=1)[0]["metadata"]

    _acquire(client, source_id)
    assert chunk_store._collection.count() == first_chunks
    assert knowledge_store.search("summary body", n=1)[0]["metadata"] == first_meta
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        assert json.loads(paper.authors_json) == ["J. Hopfield"]


def test_lookup_failure_never_blocks_acquisition(monkeypatch):
    class _DownClient:
        def lookup(self, *, doi=None, title=None):
            raise RuntimeError("network down")

    monkeypatch.setattr(kl_module, "_build_metadata_client", lambda: _DownClient())
    client, engine, _ks, _cs = _make_env()
    source_id = _insert_approved_paper(engine)

    item = _acquire(client, source_id)
    assert item["data_tier"] == "full_text"  # acquisition still succeeded
    assert any("lookup failed" in w for w in item["warnings"])


def test_run_post_acquisition_reports_handler_errors_as_warnings():
    client, engine, _ks, _cs = _make_env()
    source_id = _insert_approved_paper(engine)

    def _broken(source_id):
        raise RuntimeError("handler exploded")

    events.subscribe(events.FULL_TEXT_ACQUIRED, _broken, key="broken")
    warnings = kl_module.run_post_acquisition(source_id, engine)
    assert any("handler exploded" in w for w in warnings)
