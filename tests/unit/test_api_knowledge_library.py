"""Tests for /api/knowledge-library routes."""
from unittest.mock import MagicMock

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.knowledge_library import router
from neurodb.db import get_session
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.schema import Base, Claim, GroupingLink, Paper


def _make_app(engine, knowledge_store=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store if knowledge_store is not None else MagicMock()
    app.state.tasks = {}
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_client(knowledge_store=None):
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store)), engine


def _make_duckdb_client(knowledge_store=None):
    engine = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store)), engine


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
