"""End-to-end Phase 2 integration: create topic → link concept, paper, packet, note → verify bundle."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.db.topic_store import (
    get_or_create_concept,
    get_or_create_topic,
    get_topic_bundle,
    link_packet_topic,
    link_paper_topic,
    link_topic_concept,
)
from neurodb.schema import (
    Base, DatasetIndex, DatasetResearchPacket, IngestRun, Paper, StudyNote,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_full_topic_bundle_round_trip(engine):
    with Session(engine) as session:
        # Create topic and concept
        topic = get_or_create_topic(session, "hippocampal plasticity",
                                    "memory formation and LTP")
        concept = get_or_create_concept(session, "LTP",
                                        "long-term potentiation")
        session.flush()
        link_topic_concept(session, topic.id, concept.id)

        # Approve a paper and link to topic
        paper = Paper(
            title="LTP and Memory Consolidation",
            normalized_title="ltp and memory consolidation",
            source_type="paper",
            topic_context="hippocampal plasticity",
            status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic.id)

        # Create dataset packet and link to topic
        run = IngestRun(source="openneuro", run_at=_now(), version="1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds000001", run_id=run.id)
        session.add(idx)
        session.flush()
        packet = DatasetResearchPacket(
            index_id=idx.id, source="openneuro", source_id="ds000001",
            title="Hippocampal fMRI Study",
            usefulness_state="partial",
            supported_workflows_json="[]", unsupported_workflows_json="[]",
            missing_context_json="[]", provenance_json="{}", confidence_json="{}",
            harvested_at=_now(), run_id=run.id,
        )
        session.add(packet)
        session.flush()
        link_packet_topic(session, packet.id, topic.id)

        # Add study note anchored to topic
        note = StudyNote(
            topic_id=topic.id,
            concept_tag="LTP",
            note_text="Key mechanism for memory encoding",
            tagged_at=_now(),
        )
        session.add(note)
        session.commit()

        bundle = get_topic_bundle(session, topic.id)

    assert bundle["topic"]["name"] == "hippocampal plasticity"
    assert any(c["name"] == "LTP" for c in bundle["concepts"])
    assert any(p["title"] == "LTP and Memory Consolidation" for p in bundle["papers"])
    assert any(n["note_text"] == "Key mechanism for memory encoding"
               for n in bundle["study_notes"])
    assert any(pkt["source"] == "openneuro" for pkt in bundle["dataset_packets"])


def test_study_note_anchored_to_topic_without_dataset(engine):
    with Session(engine) as session:
        topic = get_or_create_topic(session, "cortical remapping")
        session.flush()
        note = StudyNote(
            topic_id=topic.id,
            concept_tag="plasticity",
            note_text="Cortex reorganizes after lesion",
            tagged_at=_now(),
        )
        session.add(note)
        session.commit()
        bundle = get_topic_bundle(session, topic.id)
    assert len(bundle["study_notes"]) == 1
    assert bundle["study_notes"][0]["note_text"] == "Cortex reorganizes after lesion"


def test_unlinked_resources_do_not_appear_in_bundle(engine):
    with Session(engine) as session:
        topic_a = get_or_create_topic(session, "topic A")
        topic_b = get_or_create_topic(session, "topic B")
        paper = Paper(
            title="Only B Paper", normalized_title="only b paper",
            source_type="paper", topic_context="B", status="approved",
            queued_at=_now(),
        )
        session.add(paper)
        session.flush()
        link_paper_topic(session, paper.id, topic_b.id)
        session.commit()
        bundle = get_topic_bundle(session, topic_a.id)
    assert len(bundle["papers"]) == 0
    assert len(bundle["concepts"]) == 0
    assert len(bundle["study_notes"]) == 0
    assert len(bundle["dataset_packets"]) == 0
