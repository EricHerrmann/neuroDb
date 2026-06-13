"""Tests for Phase 2b API integration: async dispatch, staging preview, review endpoint."""
from __future__ import annotations

from unittest.mock import MagicMock

import chromadb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.knowledge_library import router
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Section
from neurodb.db import get_session
from neurodb.fulltext_staging import stage_artifact
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base, Paper


# ---------------------------------------------------------------------------
# Test app + client helpers (mirrors test_api_knowledge_library._make_duckdb_client)
# ---------------------------------------------------------------------------

def _make_app(engine, knowledge_store=None, chunk_store=None):
    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store if knowledge_store is not None else MagicMock()
    app.state.tasks = {}
    app.state.chunk_store = chunk_store
    app.include_router(router, prefix="/api/knowledge-library")
    return app


def _make_duckdb_client(knowledge_store=None, chunk_store=None):
    engine = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine, knowledge_store, chunk_store)), engine


def _make_stub_chunk_store():
    class _StubEmbedder:
        def embed(self, texts):
            return [[0.1, 0.2, 0.3] for _ in texts]

    import uuid as _uuid
    return ChunkStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"ck_{_uuid.uuid4().hex}",
    )


def _insert_approved_paper(engine, *, title="Test Paper", url=None, doi=None,
                            full_text_status=None):
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
            full_text_status=full_text_status,
        )
        session.add(paper)
        session.flush()
        return paper.id


def _high_confidence_artifact(text_source="html_extracted") -> ParsedArtifact:
    """A ParsedArtifact with parse_confidence above the accept threshold (0.8)."""
    body = "memory " * 200  # 1400 chars of prose → score > 0.8
    sections = [Section(label="Abstract", text=body, char_start=0, char_end=len(body))]
    return ParsedArtifact(sections=sections, parse_confidence=0.95, text_source=text_source)


def _medium_confidence_artifact(text_source="html_extracted") -> ParsedArtifact:
    """A ParsedArtifact with parse_confidence in the review band (0.4–0.8)."""
    body = "memory " * 100
    sections = [Section(label="Abstract", text=body, char_start=0, char_end=len(body))]
    return ParsedArtifact(sections=sections, parse_confidence=0.6, text_source=text_source)


# ---------------------------------------------------------------------------
# Review endpoint tests
# ---------------------------------------------------------------------------

class TestFulltextReviewConfirm:
    """POST /{source_id}/fulltext-review with decision=confirm."""

    def test_commits_chunks_and_marks_verified(self):
        chunk_store = _make_stub_chunk_store()
        client, engine = _make_duckdb_client(chunk_store=chunk_store)
        source_id = _insert_approved_paper(engine, title="Review Confirm Paper",
                                           full_text_status="needs_review")

        # Seed the staging row directly
        artifact = _medium_confidence_artifact()
        stage_artifact(engine, source_id=source_id, artifact=artifact)

        resp = client.post(
            f"/api/knowledge-library/{source_id}/fulltext-review",
            json={"decision": "confirm"},
        )

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["full_text_status"] == "verified"
        assert data["data_tier"] == "full_text"

        # Staging row must be gone
        from neurodb.fulltext_staging import read_staging
        assert read_staging(engine, source_id) is None

    def test_staging_row_gone_after_confirm(self):
        chunk_store = _make_stub_chunk_store()
        client, engine = _make_duckdb_client(chunk_store=chunk_store)
        source_id = _insert_approved_paper(engine, title="Confirm Cleanup Paper",
                                           full_text_status="needs_review")
        artifact = _medium_confidence_artifact()
        stage_artifact(engine, source_id=source_id, artifact=artifact)

        client.post(
            f"/api/knowledge-library/{source_id}/fulltext-review",
            json={"decision": "confirm"},
        )

        from neurodb.fulltext_staging import read_staging
        assert read_staging(engine, source_id) is None


class TestFulltextReviewReject:
    """POST /{source_id}/fulltext-review with decision=reject."""

    def test_reject_drops_staging_and_marks_unavailable(self):
        client, engine = _make_duckdb_client()
        source_id = _insert_approved_paper(engine, title="Review Reject Paper",
                                           full_text_status="needs_review")
        artifact = _medium_confidence_artifact()
        stage_artifact(engine, source_id=source_id, artifact=artifact)

        resp = client.post(
            f"/api/knowledge-library/{source_id}/fulltext-review",
            json={"decision": "reject"},
        )

        assert resp.status_code == 200, resp.json()
        data = resp.json()
        assert data["full_text_status"] == "unavailable"

        from neurodb.fulltext_staging import read_staging
        assert read_staging(engine, source_id) is None

    def test_review_404_when_no_staging_row(self):
        client, engine = _make_duckdb_client()
        source_id = _insert_approved_paper(engine, title="No Staging Paper")

        resp = client.post(
            f"/api/knowledge-library/{source_id}/fulltext-review",
            json={"decision": "confirm"},
        )

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Phase 2b async dispatch tests
# ---------------------------------------------------------------------------

class TestAcquirePhase2bDispatch:
    """POST /{source_id}/acquire-full-text for papers routed through phase2b."""

    def test_dispatches_and_verifies_when_parse_succeeds(self, monkeypatch):
        """High-confidence parse → background task → verified end state.

        Starlette TestClient runs background tasks synchronously during the
        response cycle, so the DB is in the terminal state once client.post()
        returns, even though the response body shows 'pending' (built before
        the background task runs).
        """
        import neurodb.api.routes.knowledge_library as mod
        chunk_store = _make_stub_chunk_store()
        client, engine = _make_duckdb_client(chunk_store=chunk_store)

        # Paper with a semanticscholar-style URL (no arxiv, no PMC → phase2b)
        source_id = _insert_approved_paper(
            engine,
            title="Phase2b Dispatch Paper",
            url="https://api.semanticscholar.org/graph/v1/paper/abc123",
        )

        artifact = _high_confidence_artifact()
        monkeypatch.setattr(mod, "_phase2b_parse", lambda paper, supplied: artifact)

        resp = client.post(
            f"/api/knowledge-library/{source_id}/acquire-full-text",
            json={},
        )

        assert resp.status_code == 200, resp.json()
        # Response may show 'pending' (snapshot before background task ran).
        # Check the DB for the terminal state.
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            assert paper.full_text_status == "verified", paper.full_text_status

    def test_source_url_triggers_phase2b_dispatch(self, monkeypatch):
        """A user-supplied source_url (no text) routes to phase2b.

        After the call the DB should reach the terminal state (verified for a
        high-confidence parse).
        """
        import neurodb.api.routes.knowledge_library as mod
        chunk_store = _make_stub_chunk_store()
        client, engine = _make_duckdb_client(chunk_store=chunk_store)

        source_id = _insert_approved_paper(
            engine,
            title="Source URL Phase2b Paper",
            url=None,
            doi=None,
        )

        artifact = _high_confidence_artifact()
        monkeypatch.setattr(mod, "_phase2b_parse", lambda paper, supplied: artifact)

        resp = client.post(
            f"/api/knowledge-library/{source_id}/acquire-full-text",
            json={"source_url": "https://publisher.example.com/paper.pdf"},
        )

        assert resp.status_code == 200, resp.json()
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            assert paper.full_text_status == "verified", paper.full_text_status

    def test_no_source_sets_unavailable(self, monkeypatch):
        """When _phase2b_parse returns None, end state is unavailable."""
        import neurodb.api.routes.knowledge_library as mod
        client, engine = _make_duckdb_client()

        source_id = _insert_approved_paper(
            engine,
            title="No Source Phase2b Paper",
            url="https://api.semanticscholar.org/graph/v1/paper/xyz",
        )

        monkeypatch.setattr(mod, "_phase2b_parse", lambda paper, supplied: None)

        resp = client.post(
            f"/api/knowledge-library/{source_id}/acquire-full-text",
            json={},
        )

        assert resp.status_code == 200, resp.json()
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            assert paper.full_text_status == "unavailable", paper.full_text_status


# ---------------------------------------------------------------------------
# Staging preview in PaperItem
# ---------------------------------------------------------------------------

class TestStagingPreview:
    """When full_text_status == needs_review, PaperItem should include fulltext_staging."""

    def test_paper_item_includes_staging_when_needs_review(self):
        client, engine = _make_duckdb_client()
        source_id = _insert_approved_paper(engine, title="Staging Preview Paper",
                                           full_text_status="needs_review")
        artifact = _medium_confidence_artifact()
        stage_artifact(engine, source_id=source_id, artifact=artifact)

        resp = client.get("/api/knowledge-library")

        assert resp.status_code == 200
        papers = [p for p in resp.json() if p["id"] == source_id]
        assert len(papers) == 1
        staging = papers[0].get("fulltext_staging")
        assert staging is not None
        assert "sections" in staging
        assert len(staging["sections"]) == 1

    def test_paper_item_staging_none_when_not_needs_review(self):
        client, engine = _make_duckdb_client()
        source_id = _insert_approved_paper(engine, title="No Staging Preview Paper")

        resp = client.get("/api/knowledge-library")

        assert resp.status_code == 200
        papers = [p for p in resp.json() if p["id"] == source_id]
        assert len(papers) == 1
        # fulltext_staging should be absent or None
        assert papers[0].get("fulltext_staging") is None
