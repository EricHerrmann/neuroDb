import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from neurodb.dataset_packets import (
    get_dataset_packet_coverage,
    make_dataset_research_packet,
    upsert_dataset_research_packet,
)
from neurodb.db import init_db
from neurodb.schema import DatasetIndex, DatasetResearchPacket, IngestRun


def _seed_index(engine, source="openneuro", source_id="ds001"):
    with Session(engine) as session:
        run = IngestRun(source=source, run_at="2026-05-18T00:00:00+00:00", version="test")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source=source, source_id=source_id, run_id=run.id)
        session.add(idx)
        session.commit()
        return idx.id, run.id


def test_openneuro_packet_extracts_publication_summary_and_state():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine)
    raw = {
        "id": "ds001",
        "name": "Risk task",
        "metadata": {
            "modalities": ["mri"],
            "associatedPaperDOI": "10.123/test",
            "ages": [20, 21],
        },
        "draft": {
            "readme": "Task fMRI dataset with methods context.",
            "description": {"BIDSVersion": "1.8.0"},
        },
    }

    packet = make_dataset_research_packet(
        source="openneuro",
        source_id="ds001",
        raw=raw,
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    assert packet.title == "Risk task"
    assert packet.doi == "10.123/test"
    assert packet.landing_url == "https://openneuro.org/datasets/ds001"
    assert packet.source_summary == "Task fMRI dataset with methods context."
    assert packet.usefulness_state == "research_context_ready"
    assert "asset_manifest" in json.loads(packet.missing_context_json)
    assert json.loads(packet.modalities_json) == ["mri"]


def test_sparse_packet_stays_sparse_when_only_identity_exists():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine, source="fake", source_id="fake001")

    packet = make_dataset_research_packet(
        source="fake",
        source_id="fake001",
        raw={"id": "fake001"},
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    assert packet.usefulness_state == "sparse"
    assert json.loads(packet.supported_workflows_json) == []
    assert "research_synthesis" in json.loads(packet.unsupported_workflows_json)


def test_dandi_packet_extracts_asset_manifest_and_methods():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine, source="dandi", source_id="000003")
    raw = {
        "identifier": "000003",
        "most_recent_published_version": {
            "name": "Hippocampus navigation",
            "description": "Spatial navigation electrophysiology dataset.",
            "doi": "10.80507/dandi.000003",
            "asset_summary": {
                "numberOfSubjects": 5,
                "numberOfFiles": 25,
                "dataStandard": [{"name": "NWB"}],
                "species": [{"name": "Mus musculus"}],
                "approach": [{"name": "electrophysiology"}],
                "measurementTechnique": [{"name": "spike sorting"}],
            },
        },
    }

    packet = make_dataset_research_packet(
        source="dandi",
        source_id="000003",
        raw=raw,
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    assert packet.doi == "10.80507/dandi.000003"
    assert packet.participant_summary == "5 subject(s)"
    assert json.loads(packet.assets_json)["number_of_files"] == 25
    assert "electrophysiology" in json.loads(packet.topics_json)
    assert packet.usefulness_state == "analysis_ready"


def test_neurovault_packet_extracts_topics_and_asset_manifest():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine, source="neurovault", source_id="1")
    raw = {
        "id": 1,
        "name": "Working Memory fMRI",
        "description": "Working memory statistical maps.",
        "doi": "10.1016/example",
        "cognitive_paradigm_cog_atlas": "working memory",
        "number_of_images": 42,
        "number_of_subjects": 30,
        "repetition_time": 2.0,
        "resolution": "2mm",
        "images": "https://neurovault.org/api/collections/1/images/",
    }

    packet = make_dataset_research_packet(
        source="neurovault",
        source_id="1",
        raw=raw,
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    assert packet.paper_url is None
    assert json.loads(packet.topics_json) == ["working memory"]
    assert json.loads(packet.assets_json)["number_of_images"] == 42
    assert packet.usefulness_state == "analysis_ready"


def test_allen_packet_is_partial_without_publication_link():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine, source="allen_brain", source_id="100")
    raw = {
        "id": 100,
        "name": "Gene expression in cortex",
        "description": "In situ hybridization section dataset.",
        "plane_of_section_id": 1,
        "specimen_id": 2,
    }

    packet = make_dataset_research_packet(
        source="allen_brain",
        source_id="100",
        raw=raw,
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    assert packet.landing_url == "https://mouse.brain-map.org/experiment/show/100"
    assert json.loads(packet.modalities_json) == ["ISH"]
    assert "publication_link" in json.loads(packet.missing_context_json)
    assert packet.usefulness_state == "partial"


def test_upsert_dataset_research_packet_updates_existing_row():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine)
    first = make_dataset_research_packet(
        source="openneuro",
        source_id="ds001",
        raw={"id": "ds001", "name": "Old"},
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )
    second = make_dataset_research_packet(
        source="openneuro",
        source_id="ds001",
        raw={"id": "ds001", "name": "New", "draft": {"readme": "new summary"}},
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )

    with Session(engine) as session:
        upsert_dataset_research_packet(session, first)
        session.commit()
        upsert_dataset_research_packet(session, second)
        session.commit()
        rows = session.execute(select(DatasetResearchPacket)).scalars().all()

    assert len(rows) == 1
    assert rows[0].title == "New"
    assert rows[0].source_summary == "new summary"


def test_packet_coverage_groups_by_source():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    index_id, run_id = _seed_index(engine)
    packet = make_dataset_research_packet(
        source="openneuro",
        source_id="ds001",
        raw={
            "id": "ds001",
            "name": "Risk task",
            "metadata": {"associatedPaperDOI": "10.123/test"},
            "draft": {"readme": "summary", "description": {"BIDSVersion": "1.8.0"}},
        },
        index_id=index_id,
        run_id=run_id,
        connector_version="test",
    )
    with Session(engine) as session:
        session.add(packet)
        session.commit()

    report = get_dataset_packet_coverage(engine)

    assert report[0]["source"] == "openneuro"
    assert report[0]["total_packets"] == 1
    assert report[0]["doi_or_paper_url"] == 1
    assert report[0]["source_summary"] == 1
