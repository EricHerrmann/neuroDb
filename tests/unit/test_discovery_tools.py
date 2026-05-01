import json
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, select
from neurodb.db import init_db, seed_learning_sources
from neurodb.schema import ImportQueue, SourceSuggestion
from neurodb.discovery_tools import (
    run_search_external,
    run_suggest_import,
    run_suggest_learning_source,
    run_suggest_new_source,
)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    return engine


def test_suggest_import_writes_pending_row():
    engine = _engine()
    result = json.loads(run_suggest_import(
        source="openneuro",
        source_id="ds003787",
        title="NYU Retinotopy Dataset",
        reason="Matches Ch12 retinotopy topics",
        chapter_ref="Ch12",
        metadata={},
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(select(ImportQueue).where(ImportQueue.source_id == "ds003787")).scalar_one()
    assert row.status == "pending"
    assert row.chapter_ref == "Ch12"


def test_suggest_learning_source_writes_source_suggestion():
    engine = _engine()
    result = json.loads(run_suggest_learning_source(
        suggestion_type="learning_source",
        reference="10.1167/19.10.23",
        display_name="Benson et al. 2018 retinotopy",
        reason="Primary paper for Ch12 retinotopic maps",
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(SourceSuggestion).where(SourceSuggestion.reference == "10.1167/19.10.23")
            ).scalar_one()
    assert row.status == "pending"
    assert row.suggestion_type == "learning_source"


def test_suggest_new_source_writes_new_connector_suggestion():
    engine = _engine()
    result = json.loads(run_suggest_new_source(
        reference="https://human.brain-map.org/",
        display_name="Allen Human Brain Atlas",
        reason="Contains human cortical gene expression data relevant to V1",
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(SourceSuggestion).where(SourceSuggestion.suggestion_type == "new_connector")
            ).scalar_one()
    assert row.status == "pending"


def test_search_external_openneuro_returns_results():
    search_body = {
        "data": {
            "datasets": {
                "edges": [{"node": {
                    "id": "ds003787", "name": "NYU Retinotopy Dataset",
                    "metadata": {"modalities": ["mri"], "associatedPaperDOI": None,
                                 "ages": [], "species": "Human"},
                    "draft": {"readme": "pRF mapping", "description": {"BIDSVersion": "1.4.0"}},
                }}]
            }
        }
    }
    mock = MagicMock()
    mock.json.return_value = search_body
    mock.raise_for_status.return_value = None
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        result = json.loads(run_search_external("openneuro", "retinotopy"))
    assert len(result) == 1
    assert result[0]["id"] == "ds003787"
    assert result[0]["source"] == "openneuro"


def test_search_external_unknown_source_returns_error():
    result = json.loads(run_search_external("unknown_source", "retinotopy"))
    assert "error" in result
