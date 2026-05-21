"""Tests for Phase 5b: usefulness_state and missing_context in GET /api/datasets."""
from __future__ import annotations

import json

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.datasets import router
from neurodb.db import get_session
from neurodb.schema import Base, DatasetIndex, DatasetResearchPacket, IngestRun


def _make_client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.include_router(router, prefix="/api/datasets")
    return TestClient(app), engine


def _insert_dataset_with_packet(engine, source_id: str, usefulness: str, missing: list[str]) -> int:
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01", version="1", notes=None)
        session.add(run)
        session.flush()
        dataset = DatasetIndex(source="openneuro", source_id=source_id, run_id=run.id)
        session.add(dataset)
        session.flush()
        packet = DatasetResearchPacket(
            index_id=dataset.id,
            source="openneuro",
            source_id=source_id,
            usefulness_state=usefulness,
            supported_workflows_json="[]",
            unsupported_workflows_json="[]",
            missing_context_json=json.dumps(missing),
            provenance_json="{}",
            confidence_json="{}",
            harvested_at="2026-01-01T00:00:00",
            run_id=run.id,
        )
        session.add(packet)
        session.flush()
        return dataset.id


def _insert_dataset_without_packet(engine, source_id: str) -> int:
    with get_session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01", version="1", notes=None)
        session.add(run)
        session.flush()
        dataset = DatasetIndex(source="openneuro", source_id=source_id, run_id=run.id)
        session.add(dataset)
        session.flush()
        return dataset.id


def test_dataset_with_packet_returns_usefulness_state():
    client, engine = _make_client()
    _insert_dataset_with_packet(engine, "ds001", "sparse", ["no linked paper"])
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["usefulness_state"] == "sparse"
    assert data[0]["missing_context"] == "no linked paper"


def test_dataset_without_packet_returns_null_fields():
    client, engine = _make_client()
    _insert_dataset_without_packet(engine, "ds002")
    resp = client.get("/api/datasets")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == 1
    assert data[0]["usefulness_state"] is None
    assert data[0]["missing_context"] is None


def test_dataset_with_research_ready_state():
    client, engine = _make_client()
    _insert_dataset_with_packet(engine, "ds003", "research_context_ready", [])
    resp = client.get("/api/datasets")
    data = resp.json()
    assert data[0]["usefulness_state"] == "research_context_ready"
    assert data[0]["missing_context"] == ""
