"""Tests for GET /api/study-log route."""
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, IngestRun, DatasetIndex, StudyNote
from neurodb.api.routes.study_log import router
from neurodb.db import get_session


def _make_app(engine):
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api")
    return app


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    return TestClient(_make_app(engine)), engine


def _insert_note(engine, concept_tag: str):
    with get_session(engine) as session:
        idx = session.execute(
            select(DatasetIndex).where(
                DatasetIndex.source == "openneuro",
                DatasetIndex.source_id == "ds001",
            )
        ).scalar_one_or_none()
        if idx is None:
            run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
            session.add(run)
            session.flush()
            idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
            session.add(idx)
            session.flush()
        session.add(StudyNote(index_id=idx.id, concept_tag=concept_tag, tagged_at="2026-01-01T00:00:00"))


def test_get_study_log_empty():
    client, _ = _make_client()
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    assert resp.json() == []


def test_get_study_log_returns_notes():
    client, engine = _make_client()
    _insert_note(engine, "LTP")
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["concept_tag"] == "LTP"
    assert data[0]["source"] == "openneuro"
    assert "id" in data[0]


def test_get_study_log_multiple_notes():
    client, engine = _make_client()
    _insert_note(engine, "LTP")
    _insert_note(engine, "LTD")
    resp = client.get("/api/study-log")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def _insert_dataset(engine, source: str, source_id: str):
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1", notes=None)
        session.add(run)
        session.flush()
        session.add(DatasetIndex(source=source, source_id=source_id, run_id=run.id))


def test_post_study_log_creates_tag():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
        "concept_tag": "LTP",
        "section_ref": "Ch3",
        "note_text": "Relevant to plasticity",
    })

    assert resp.status_code == 200
    data = resp.json()
    assert data["concept_tag"] == "LTP"
    assert data["source"] == "openneuro"
    assert data["source_id"] == "ds001"
    assert data["section_ref"] == "Ch3"
    assert "id" in data


def test_post_study_log_422_on_missing_concept_tag():
    client, engine = _make_client()
    _insert_dataset(engine, "openneuro", "ds001")

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "ds001",
    })

    assert resp.status_code == 422


def test_post_study_log_404_when_dataset_not_in_index():
    client, _ = _make_client()

    resp = client.post("/api/study-log", json={
        "source": "openneuro",
        "source_id": "nonexistent",
        "concept_tag": "LTP",
    })

    assert resp.status_code == 404
