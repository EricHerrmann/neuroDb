import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import (
    Base, Concept, DatasetIndex, DatasetResearchPacket,
    IngestRun, Paper, StudyNote, Topic,
)
from neurodb.db.topic_store import (
    get_or_create_concept,
    get_or_create_topic,
    get_topic_bundle,
    link_packet_paper,
    link_packet_topic,
    link_paper_concept,
    link_paper_topic,
    link_topic_concept,
    search_topics,
)


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def _make_paper(session):
    paper = Paper(
        title="LTP Paper", normalized_title="ltp paper",
        source_type="paper", topic_context="plasticity",
        status="approved", queued_at=_now(),
    )
    session.add(paper)
    session.flush()
    return paper


def _make_packet(session):
    run = IngestRun(source="test", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="test", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    packet = DatasetResearchPacket(
        index_id=idx.id, source="test", source_id="ds1",
        usefulness_state="partial",
        supported_workflows_json="[]", unsupported_workflows_json="[]",
        missing_context_json="[]", provenance_json="{}", confidence_json="{}",
        harvested_at=_now(), run_id=run.id,
    )
    session.add(packet)
    session.flush()
    return packet


# --- get_or_create_topic ---

def test_get_or_create_topic_creates_new(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    session.commit()
    assert topic.id is not None
    assert topic.name == "hippocampal plasticity"
    assert topic.status == "active"


def test_get_or_create_topic_is_idempotent(session):
    t1 = get_or_create_topic(session, "stroke recovery")
    session.flush()
    t2 = get_or_create_topic(session, "stroke recovery")
    session.flush()
    assert t1.id == t2.id


def test_get_or_create_topic_strips_whitespace(session):
    t1 = get_or_create_topic(session, "  basal ganglia  ")
    session.flush()
    t2 = get_or_create_topic(session, "basal ganglia")
    session.flush()
    assert t1.id == t2.id


# --- get_or_create_concept ---

def test_get_or_create_concept_creates_new(session):
    concept = get_or_create_concept(session, "neuroplasticity")
    session.commit()
    assert concept.id is not None
    assert concept.name == "neuroplasticity"


def test_get_or_create_concept_is_idempotent(session):
    c1 = get_or_create_concept(session, "GABA")
    session.flush()
    c2 = get_or_create_concept(session, "GABA")
    session.flush()
    assert c1.id == c2.id


# --- link functions ---

def test_link_paper_topic_is_idempotent(session):
    paper = _make_paper(session)
    topic = get_or_create_topic(session, "stroke recovery")
    session.flush()
    link_paper_topic(session, paper.id, topic.id)
    link_paper_topic(session, paper.id, topic.id)
    session.commit()


def test_link_paper_concept_is_idempotent(session):
    paper = _make_paper(session)
    concept = get_or_create_concept(session, "neuroplasticity")
    session.flush()
    link_paper_concept(session, paper.id, concept.id)
    link_paper_concept(session, paper.id, concept.id)
    session.commit()


def test_link_topic_concept_is_idempotent(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    concept = get_or_create_concept(session, "LTP")
    session.flush()
    link_topic_concept(session, topic.id, concept.id)
    link_topic_concept(session, topic.id, concept.id)
    session.commit()


def test_link_packet_topic_is_idempotent(session):
    packet = _make_packet(session)
    topic = get_or_create_topic(session, "memory consolidation")
    session.flush()
    link_packet_topic(session, packet.id, topic.id)
    link_packet_topic(session, packet.id, topic.id)
    session.commit()


def test_link_packet_paper_is_idempotent(session):
    packet = _make_packet(session)
    paper = _make_paper(session)
    session.flush()
    link_packet_paper(session, packet.id, paper.id)
    link_packet_paper(session, packet.id, paper.id)
    session.commit()


# --- search_topics ---

def test_search_topics_returns_name_match(session):
    get_or_create_topic(session, "hippocampal plasticity", "relates to memory")
    get_or_create_topic(session, "stroke recovery", "motor learning after stroke")
    session.commit()
    results = search_topics(session, "plasticity")
    names = [r["name"] for r in results]
    assert "hippocampal plasticity" in names
    assert "stroke recovery" not in names


def test_search_topics_returns_description_match(session):
    get_or_create_topic(session, "cortical remapping", "neuroplasticity after injury")
    session.commit()
    results = search_topics(session, "neuroplasticity")
    assert any(r["name"] == "cortical remapping" for r in results)


def test_search_topics_respects_limit(session):
    for i in range(12):
        get_or_create_topic(session, f"topic {i}")
    session.commit()
    results = search_topics(session, "topic", limit=5)
    assert len(results) <= 5


def test_search_topics_returns_dict_shape(session):
    get_or_create_topic(session, "basal ganglia")
    session.commit()
    results = search_topics(session, "basal")
    assert {"id", "name", "description", "status"}.issubset(results[0].keys())


# --- get_topic_bundle ---

def test_get_topic_bundle_returns_empty_for_unknown(session):
    assert get_topic_bundle(session, 9999) == {}


def test_get_topic_bundle_returns_linked_concepts(session):
    topic = get_or_create_topic(session, "hippocampal plasticity")
    concept = get_or_create_concept(session, "LTP")
    session.flush()
    link_topic_concept(session, topic.id, concept.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert bundle["topic"]["name"] == "hippocampal plasticity"
    assert any(c["name"] == "LTP" for c in bundle["concepts"])


def test_get_topic_bundle_returns_linked_papers(session):
    topic = get_or_create_topic(session, "stroke recovery")
    paper = _make_paper(session)
    session.flush()
    link_paper_topic(session, paper.id, topic.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert any(p["title"] == "LTP Paper" for p in bundle["papers"])


def test_get_topic_bundle_returns_study_notes(session):
    topic = get_or_create_topic(session, "memory consolidation")
    session.flush()
    session.add(StudyNote(topic_id=topic.id, concept_tag="replay", tagged_at=_now()))
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert any(n["concept_tag"] == "replay" for n in bundle["study_notes"])


def test_get_topic_bundle_returns_dataset_packets(session):
    topic = get_or_create_topic(session, "fMRI analysis")
    packet = _make_packet(session)
    session.flush()
    link_packet_topic(session, packet.id, topic.id)
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert len(bundle["dataset_packets"]) == 1
    assert bundle["dataset_packets"][0]["source"] == "test"


def test_get_topic_bundle_excludes_resources_linked_to_other_topics(session):
    topic_a = get_or_create_topic(session, "topic A")
    topic_b = get_or_create_topic(session, "topic B")
    paper = _make_paper(session)
    session.flush()
    link_paper_topic(session, paper.id, topic_b.id)
    session.commit()
    bundle = get_topic_bundle(session, topic_a.id)
    assert len(bundle["papers"]) == 0


def test_get_topic_bundle_has_all_keys(session):
    topic = get_or_create_topic(session, "empty topic")
    session.commit()
    bundle = get_topic_bundle(session, topic.id)
    assert set(bundle.keys()) == {"topic", "concepts", "papers", "study_notes", "dataset_packets"}
