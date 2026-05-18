import json
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine, select

from neurodb.db import init_db, seed_learning_sources
from neurodb.discovery_tools import (
    run_inspect_external_dataset,
    run_search_external,
    run_suggest_import,
    run_suggest_learning_source,
    run_suggest_new_source,
)
from neurodb.schema import ImportQueue, SourceSuggestion


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    return engine


def test_suggest_import_writes_pending_row():
    engine = _engine()
    result = json.loads(
        run_suggest_import(
            source="openneuro",
            source_id="ds003787",
            title="NYU Retinotopy Dataset",
            reason="Matches Ch12 retinotopy topics",
            chapter_ref="Ch12",
            metadata={},
            engine=engine,
        )
    )
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(ImportQueue).where(ImportQueue.source_id == "ds003787")
            ).scalar_one()
    assert row.status == "pending"
    assert row.chapter_ref == "Ch12"


def test_suggest_learning_source_writes_source_suggestion():
    engine = _engine()
    result = json.loads(
        run_suggest_learning_source(
            suggestion_type="learning_source",
            reference="10.1167/19.10.23",
            display_name="Benson et al. 2018 retinotopy",
            reason="Primary paper for Ch12 retinotopic maps",
            engine=engine,
        )
    )
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
    result = json.loads(
        run_suggest_new_source(
            reference="https://human.brain-map.org/",
            display_name="Allen Human Brain Atlas",
            reason="Contains human cortical gene expression data relevant to V1",
            engine=engine,
        )
    )
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
            "advancedSearch": {
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


def test_search_external_all_uses_registered_connectors():
    with (
        patch(
            "neurodb.connectors.allen_brain.AllenBrainConnector.search_by_keyword",
            return_value=[{"id": 1}],
        ),
        patch(
            "neurodb.connectors.dandi.DandiConnector.search_by_keyword",
            return_value=[{"identifier": "000010"}],
        ),
        patch(
            "neurodb.connectors.neurovault.NeuroVaultConnector.search_by_keyword",
            return_value=[{"id": 2}],
        ),
        patch(
            "neurodb.connectors.openneuro.OpenNeuroConnector.search_by_keyword",
            return_value=[{"id": "ds000001"}],
        ),
    ):
        result = json.loads(run_search_external("all", "plasticity", limit=2))

    assert {row["source"] for row in result} == {
        "allen_brain",
        "dandi",
        "neurovault",
        "openneuro",
    }


def test_inspect_external_dataset_resolves_dandi_url():
    with patch(
        "neurodb.connectors.dandi.DandiConnector.fetch_by_id",
        return_value={"identifier": "000010", "name": "DANDI test"},
    ) as fetch_by_id:
        result = json.loads(
            run_inspect_external_dataset(
                "auto",
                "https://dandiarchive.org/dandiset/000010",
            )
        )

    fetch_by_id.assert_called_once_with("000010")
    assert result["source"] == "dandi"
    assert result["source_id"] == "000010"
    assert result["raw"]["identifier"] == "000010"


def test_inspect_external_dataset_resolves_openneuro_url():
    with patch(
        "neurodb.connectors.openneuro.OpenNeuroConnector.fetch_by_id",
        return_value={"id": "ds003787", "name": "OpenNeuro test"},
    ) as fetch_by_id:
        result = json.loads(run_inspect_external_dataset(
            "auto",
            "https://openneuro.org/datasets/ds003787/versions/1.0.0",
        ))

    fetch_by_id.assert_called_once_with("ds003787")
    assert result["source"] == "openneuro"
    assert result["source_id"] == "ds003787"


def test_inspect_external_dataset_resolves_neurovault_url():
    with patch(
        "neurodb.connectors.neurovault.NeuroVaultConnector.fetch_by_id",
        return_value={"id": 1234, "name": "NeuroVault test"},
    ) as fetch_by_id:
        result = json.loads(run_inspect_external_dataset(
            "auto",
            "https://neurovault.org/collections/1234/",
        ))

    fetch_by_id.assert_called_once_with("1234")
    assert result["source"] == "neurovault"
    assert result["source_id"] == "1234"


def test_inspect_external_dataset_resolves_allen_brain_url():
    with patch(
        "neurodb.connectors.allen_brain.AllenBrainConnector.fetch_by_id",
        return_value={"id": 999, "name": "Allen test"},
    ) as fetch_by_id:
        result = json.loads(run_inspect_external_dataset(
            "auto",
            "https://mouse.brain-map.org/experiment/show/999",
        ))

    fetch_by_id.assert_called_once_with("999")
    assert result["source"] == "allen_brain"
    assert result["source_id"] == "999"


def test_inspect_external_dataset_source_bare_id():
    with patch(
        "neurodb.connectors.neurovault.NeuroVaultConnector.fetch_by_id",
        return_value={"id": 1234},
    ) as fetch_by_id:
        result = json.loads(run_inspect_external_dataset("neurovault", "1234"))

    fetch_by_id.assert_called_once_with("1234")
    assert result["source"] == "neurovault"
    assert result["source_id"] == "1234"


def test_inspect_external_dataset_unknown_auto_reference_returns_error():
    result = json.loads(run_inspect_external_dataset("auto", "https://example.org/dataset/1"))
    assert "Could not infer source" in result["error"]


def test_search_external_unknown_source_returns_error():
    result = json.loads(run_search_external("unknown_source", "retinotopy"))
    assert "error" in result
