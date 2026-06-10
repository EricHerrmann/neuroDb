"""Tests for /api/knowledge-library routes."""
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.knowledge_library import router, _summary_prompt, _fallback_summary
from neurodb.db import get_session
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.schema import Base, Claim, GroupingLink, Paper


def _make_app(engine, knowledge_store=None, chunk_store=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store if knowledge_store is not None else MagicMock()
    app.state.tasks = {}
    app.state.chunk_store = chunk_store
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_client(knowledge_store=None, chunk_store=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store, chunk_store)), engine


def _make_duckdb_client(knowledge_store=None, chunk_store=None):
    engine = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store, chunk_store)), engine


def _insert_source(engine, title: str = "Test Source", status: str = "pending"):
    with get_session(engine) as session:
        session.add(Paper(
            title=title,
            normalized_title=title.lower(),
            source_type="paper",
            topic_context="neuroscience",
            status=status,
            queued_at="2026-01-01T00:00:00",
        ))


def test_get_knowledge_library_empty():
    client, _ = _make_client()
    resp = client.get("/api/knowledge-library")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_knowledge_library_returns_all_by_default():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")

    resp = client.get("/api/knowledge-library")

    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_get_knowledge_library_filter_by_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    _insert_source(engine, "Paper B", "approved")

    resp = client.get("/api/knowledge-library?status=pending")

    data = resp.json()
    assert resp.status_code == 200
    assert len(data) == 1
    assert data[0]["title"] == "Paper A"


def test_get_knowledge_library_returns_review_detail_fields():
    client, engine = _make_client()
    with get_session(engine) as session:
        session.add(Paper(
            title="Detailed Paper",
            normalized_title="detailed paper",
            source_type="review",
            topic_context="memory consolidation",
            status="pending",
            queued_at="2026-06-02T00:00:00",
            abstract="Review abstract",
            year=2020,
        ))

    resp = client.get("/api/knowledge-library")

    data = resp.json()
    assert resp.status_code == 200
    assert data[0]["abstract"] == "Review abstract"
    assert data[0]["year"] == 2020


def test_get_knowledge_library_returns_grouping_link_indicators():
    client, engine = _make_client()
    with get_session(engine) as session:
        paper = Paper(
            title="Linked Paper",
            normalized_title="linked paper",
            source_type="paper",
            topic_context="stroke",
            status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        grouping = get_or_create_grouping(session, "topic", "stroke recovery")
        grouping_id = grouping.id
        link_grouping(session, grouping_id, "paper", paper.id, status="confirmed")

    resp = client.get("/api/knowledge-library?status=pending")

    assert resp.status_code == 200
    data = resp.json()
    assert data[0]["grouping_links"] == [{
        "grouping_id": grouping_id,
        "grouping_type": "topic",
        "grouping_name": "stroke recovery",
        "status": "confirmed",
    }]


def test_approve_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["reviewed_at"] is not None


def test_reject_source_sets_status():
    client, engine = _make_client()
    _insert_source(engine, "Paper A", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"
    assert resp.json()["reviewed_at"] is not None


def test_approve_source_404_for_unknown():
    client, _ = _make_client()
    resp = client.post("/api/knowledge-library/9999/approve")
    assert resp.status_code == 404


def test_approve_source_calls_add_summary():
    mock_ks = MagicMock()
    mock_ks.add_summary.return_value = "knowledge_source:1"
    client, engine = _make_client(mock_ks)
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["warnings"] == []
    mock_ks.add_summary.assert_called_once()


def test_approve_source_preserves_grouping_links_with_duckdb():
    mock_ks = MagicMock()
    mock_ks.add_summary.return_value = "knowledge_source:1"
    client, engine = _make_duckdb_client(mock_ks)
    with get_session(engine) as session:
        paper = Paper(
            title="Linked Paper",
            normalized_title="linked paper",
            source_type="paper",
            topic_context="stroke",
            status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        source_id = paper.id
        grouping = get_or_create_grouping(session, "topic", "stroke recovery")
        grouping_id = grouping.id
        link_grouping(session, grouping_id, "paper", source_id, status="confirmed")

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    with get_session(engine) as session:
        link = session.query(GroupingLink).filter_by(
            grouping_id=grouping_id,
            anchor_type="paper",
            anchor_id=source_id,
        ).one_or_none()
        assert link is not None


def test_approve_source_preserves_claims_with_duckdb():
    mock_ks = MagicMock()
    mock_ks.add_summary.return_value = "knowledge_source:1"
    client, engine = _make_duckdb_client(mock_ks)
    with get_session(engine) as session:
        paper = Paper(
            title="Claimed Paper",
            normalized_title="claimed paper",
            source_type="paper",
            topic_context="stroke",
            status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        source_id = paper.id
        claim = Claim(
            paper_id=source_id,
            text="A real extracted claim.",
            claim_type="finding",
            status="approved",
            created_at="2026-01-01T00:00:00",
            updated_at="2026-01-01T00:00:00",
        )
        session.add(claim)
        session.flush()
        claim_id = claim.id

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    with get_session(engine) as session:
        claim = session.get(Claim, claim_id)
        assert claim is not None
        assert claim.paper_id == source_id
        assert claim.text == "A real extracted claim."


def test_reject_source_handles_legacy_study_notes_without_paper_id_duckdb():
    client, engine = _make_legacy_study_notes_duckdb_client()
    with get_session(engine) as session:
        paper = Paper(
            title="Legacy Paper",
            normalized_title="legacy paper",
            source_type="paper",
            topic_context="legacy",
            status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        source_id = paper.id

    resp = client.post(f"/api/knowledge-library/{source_id}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_approve_source_handles_legacy_study_notes_without_paper_id_duckdb():
    mock_ks = MagicMock()
    mock_ks.add_summary.return_value = "knowledge_source:1"
    client, engine = _make_legacy_study_notes_duckdb_client(mock_ks)
    with get_session(engine) as session:
        paper = Paper(
            title="Legacy Approve Paper",
            normalized_title="legacy approve paper",
            source_type="paper",
            topic_context="legacy",
            status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        source_id = paper.id

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    assert resp.json()["status"] == "approved"
    assert resp.json()["warnings"] == []


def _make_legacy_study_notes_duckdb_client(knowledge_store=None):
    client, engine = _make_duckdb_client(knowledge_store)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE evidence_links"))
        conn.execute(text("DROP TABLE study_notes"))
        conn.execute(text("""
            CREATE TABLE study_notes (
                id INTEGER PRIMARY KEY,
                index_id INTEGER,
                topic_id INTEGER,
                concept_id INTEGER,
                concept_tag VARCHAR(128) NOT NULL,
                section_ref VARCHAR(64),
                note_text TEXT,
                tagged_at VARCHAR(32) NOT NULL
            )
        """))
    return client, engine


def test_approve_source_returns_warning_when_chroma_fails():
    mock_ks = MagicMock()
    mock_ks.add_summary.side_effect = RuntimeError("chroma down")
    client, engine = _make_client(mock_ks)
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve")

    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "approved"
    assert len(data["warnings"]) == 1
    assert "ChromaDB indexing failed" in data["warnings"][0]


def test_reject_source_has_no_warnings_field_interaction():
    client, engine = _make_client()
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/reject")

    assert resp.status_code == 200
    assert resp.json()["status"] == "rejected"


def test_duplicate_check_returns_near_candidates():
    mock_ks = MagicMock()
    mock_ks.search.return_value = [{
        "id": "knowledge_source:2",
        "metadata": {"source_id": "2", "title": "Similar Paper", "doi": "10.1/test"},
        "distance": 0.05,
    }]
    client, engine = _make_client(mock_ks)
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.get(f"/api/knowledge-library/{source_id}/duplicates")

    assert resp.status_code == 200
    assert resp.json()["candidates"][0]["title"] == "Similar Paper"


def test_approve_with_summary_returns_task_id():
    client, engine = _make_client()
    _insert_source(engine, "LTP Paper", "pending")
    source_id = client.get("/api/knowledge-library").json()[0]["id"]

    resp = client.post(f"/api/knowledge-library/{source_id}/approve-with-summary")

    assert resp.status_code == 200
    assert resp.json()["task_id"]


def _paper(**kw):
    base = dict(
        title="CREB and engram allocation", normalized_title="creb",
        source_type="paper", topic_context="memory", status="approved",
        queued_at="now",
    )
    base.update(kw)
    return Paper(**base)


def test_summary_prompt_includes_abstract_when_present():
    row = _paper(abstract="CREB overexpression biases engram allocation.")
    prompt = _summary_prompt(row)
    assert "CREB overexpression biases engram allocation." in prompt
    assert "Abstract:" in prompt
    assert "Summarize PRIMARILY" in prompt


def test_summary_prompt_omits_abstract_label_when_absent():
    row = _paper(abstract=None)
    prompt = _summary_prompt(row)
    assert "Abstract:" not in prompt
    assert "Summarize PRIMARILY" not in prompt


def test_fallback_summary_uses_abstract_when_present():
    row = _paper(abstract="CREB overexpression biases engram allocation.")
    assert "CREB overexpression biases engram allocation." in _fallback_summary(row)


def _insert_approved_source(engine, title="Approved Paper", url=None, doi=None):
    """Insert a paper directly in approved status; returns the paper id."""
    with get_session(engine) as session:
        paper = Paper(
            title=title,
            normalized_title=title.lower(),
            source_type="paper",
            topic_context="neuroscience",
            status="approved",
            queued_at="2026-01-01T00:00:00",
            reviewed_at="2026-01-02T00:00:00",
            url=url,
            doi=doi,
        )
        session.add(paper)
        session.flush()
        return paper.id


def test_acquire_full_text_user_supplied():
    """User-supplied text routes through acquire step 1; no network call needed."""
    client, engine = _make_client()
    source_id = _insert_approved_source(engine, title="DG Pattern Separation")

    resp = client.post(
        f"/api/knowledge-library/{source_id}/acquire-full-text",
        json={"text": "# Intro\nThe dentate gyrus supports pattern separation.", "format": "md"},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["full_text_status"] == "verified"
    assert data["data_tier"] == "full_text"


def test_acquire_full_text_no_source_is_unavailable():
    """Paper with no url and no doi returns unavailable without any network call."""
    client, engine = _make_client()
    source_id = _insert_approved_source(engine, title="No Source Paper", url=None, doi=None)

    resp = client.post(
        f"/api/knowledge-library/{source_id}/acquire-full-text",
        json={},
    )

    assert resp.status_code == 200
    data = resp.json()
    assert data["full_text_status"] == "unavailable"
    assert data["data_tier"] != "full_text"


def _make_stub_chunk_store():
    """Return a real ephemeral ChunkStore with a stub embedder for unit tests."""
    import uuid as _uuid

    import chromadb

    from neurodb.chunk_store import ChunkStore

    class _StubEmbedder:
        def embed(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    return ChunkStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"ck_{_uuid.uuid4().hex}",
    )


def _assert_chunk_idempotency(client, engine, chunk_store, source_id):
    """Shared idempotency assertion: acquire twice, count must not grow."""
    body = {
        "text": "# Intro\nThe dentate gyrus supports pattern separation.\n\n## Methods\nWe recorded CA3.",
        "format": "md",
    }
    r1 = client.post(f"/api/knowledge-library/{source_id}/acquire-full-text", json=body)
    assert r1.status_code == 200
    assert r1.json()["data_tier"] == "full_text"

    with get_session(engine) as s:
        from neurodb.schema import PaperChunk
        n1 = s.query(PaperChunk).filter(PaperChunk.paper_id == source_id).count()
    assert n1 >= 1

    # Re-acquire — must not duplicate rows in DB or Chroma.
    client.post(f"/api/knowledge-library/{source_id}/acquire-full-text", json=body)

    with get_session(engine) as s:
        from neurodb.schema import PaperChunk
        n2 = s.query(PaperChunk).filter(PaperChunk.paper_id == source_id).count()
    assert n2 == n1

    hits = [h for h in chunk_store.search("dentate", n=50, min_score=-1.0)
            if h["source_id"] == source_id]
    assert len(hits) == n1


def test_acquire_full_text_stores_chunks_and_is_idempotent_sqlite():
    """SQLite backend: real ChunkStore stores chunks and re-acquire is idempotent."""
    chunk_store = _make_stub_chunk_store()
    client, engine = _make_client(chunk_store=chunk_store)
    source_id = _insert_approved_source(engine, title="DG Pattern Separation")
    _assert_chunk_idempotency(client, engine, chunk_store, source_id)


def test_acquire_full_text_stores_chunks_and_is_idempotent_duckdb():
    """DuckDB backend: guards the delete-then-insert ordering on the real analytical backend."""
    chunk_store = _make_stub_chunk_store()
    client, engine = _make_duckdb_client(chunk_store=chunk_store)
    source_id = _insert_approved_source(engine, title="DG Pattern Separation DuckDB")
    _assert_chunk_idempotency(client, engine, chunk_store, source_id)
