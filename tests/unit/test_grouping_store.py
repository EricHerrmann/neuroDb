"""Unit tests for the type-agnostic grouping engine."""
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.db.grouping_store import (
    get_children,
    get_anchor_ids_for_grouping,
    get_grouping_bundle,
    get_grouping,
    get_groupings_for_anchor,
    get_or_create_grouping,
    link_grouping,
    list_groupings,
    resolve_filter_ids,
    rollup_parents,
    search_groupings,
    set_parent,
    unlink_grouping,
    update_link_status,
)
from neurodb.db.grouping_types import GroupingHierarchyError, UnknownGroupingType
from neurodb.schema import Base


def _now():
    return datetime.now(UTC).isoformat()


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


def test_get_or_create_creates_then_dedups(session):
    g1 = get_or_create_grouping(session, "topic", "plasticity", description="d")
    g2 = get_or_create_grouping(session, "topic", "plasticity")
    assert g1.id == g2.id
    assert g1.type == "topic"
    assert g1.status == "active"
    assert g1.description == "d"


def test_same_name_different_type_are_distinct(session):
    gt = get_or_create_grouping(session, "topic", "memory")
    gc = get_or_create_grouping(session, "concept", "memory")
    assert gt.id != gc.id


def test_get_or_create_rejects_unknown_type(session):
    with pytest.raises(UnknownGroupingType):
        get_or_create_grouping(session, "method", "fMRI")


def test_get_or_create_strips_name(session):
    grouping = get_or_create_grouping(session, "topic", "  stroke  ")
    assert grouping.name == "stroke"


def test_get_grouping(session):
    grouping = get_or_create_grouping(session, "topic", "stroke")
    assert get_grouping(session, grouping.id).name == "stroke"
    assert get_grouping(session, 999999) is None


def test_list_groupings_filters(session):
    get_or_create_grouping(session, "topic", "stroke")
    get_or_create_grouping(session, "topic", "plasticity", status="proposed")
    get_or_create_grouping(session, "concept", "LTP")
    topics = list_groupings(session, gtype="topic")
    assert {row["name"] for row in topics} == {"stroke", "plasticity"}
    active_topics = list_groupings(session, gtype="topic", status="active")
    assert {row["name"] for row in active_topics} == {"stroke"}
    assert len(list_groupings(session)) == 3


def test_search_groupings_scoped_to_type(session):
    get_or_create_grouping(session, "topic", "stroke recovery", description="rehab")
    get_or_create_grouping(session, "concept", "stroke marker")
    hits = search_groupings(session, "topic", "stroke")
    assert [hit["name"] for hit in hits] == ["stroke recovery"]
    by_desc = search_groupings(session, "topic", "rehab")
    assert [hit["name"] for hit in by_desc] == ["stroke recovery"]


def test_link_grouping_is_idempotent(session):
    grouping = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, grouping.id, "question", 7, status="pending")
    link_grouping(session, grouping.id, "question", 7, status="confirmed")
    n = session.execute(
        text(
            "SELECT COUNT(*) FROM grouping_links "
            "WHERE grouping_id=:g AND anchor_type='question' AND anchor_id=7"
        ),
        {"g": grouping.id},
    ).scalar()
    assert n == 1
    status = session.execute(
        text("SELECT status FROM grouping_links WHERE grouping_id=:g AND anchor_id=7"),
        {"g": grouping.id},
    ).scalar()
    assert status == "pending"


def test_update_link_status(session):
    grouping = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, grouping.id, "question", 7, status="pending")
    assert update_link_status(session, grouping.id, "question", 7, "confirmed") is True
    assert update_link_status(session, grouping.id, "question", 999, "confirmed") is False
    rows = get_groupings_for_anchor(session, "question", 7)
    assert rows[0]["link_status"] == "confirmed"


def test_unlink_grouping(session):
    grouping = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, grouping.id, "question", 7)
    assert unlink_grouping(session, grouping.id, "question", 7) is True
    assert unlink_grouping(session, grouping.id, "question", 7) is False
    assert get_groupings_for_anchor(session, "question", 7) == []


def test_get_groupings_for_anchor_filters_status(session):
    gt = get_or_create_grouping(session, "topic", "stroke")
    gc = get_or_create_grouping(session, "concept", "LTP")
    link_grouping(session, gt.id, "question", 7, status="confirmed")
    link_grouping(session, gc.id, "question", 7, status="pending")
    all_rows = get_groupings_for_anchor(session, "question", 7)
    assert {row["name"] for row in all_rows} == {"stroke", "LTP"}
    confirmed = get_groupings_for_anchor(session, "question", 7, status="confirmed")
    assert {row["name"] for row in confirmed} == {"stroke"}


def test_set_parent_happy_path_and_clear(session):
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "topic", "neuroplasticity")
    set_parent(session, child.id, parent.id)
    assert get_grouping(session, child.id).parent_id == parent.id
    assert [grouping.name for grouping in get_children(session, parent.id)] == [
        "neuroplasticity"
    ]
    set_parent(session, child.id, None)
    assert get_grouping(session, child.id).parent_id is None


def test_set_parent_rejects_self(session):
    grouping = get_or_create_grouping(session, "topic", "plasticity")
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, grouping.id, grouping.id)


def test_set_parent_rejects_cross_type(session):
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "concept", "LTP")
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, child.id, parent.id)


def test_set_parent_rejects_grandchild(session):
    top = get_or_create_grouping(session, "topic", "plasticity")
    mid = get_or_create_grouping(session, "topic", "neuroplasticity")
    leaf = get_or_create_grouping(session, "topic", "circuit plasticity")
    set_parent(session, mid.id, top.id)
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, leaf.id, mid.id)


def test_set_parent_rejects_parenting_a_parent(session):
    top = get_or_create_grouping(session, "topic", "plasticity")
    mid = get_or_create_grouping(session, "topic", "neuroplasticity")
    other = get_or_create_grouping(session, "topic", "stroke")
    set_parent(session, mid.id, top.id)
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, top.id, other.id)


def test_resolve_filter_ids(session):
    parent = get_or_create_grouping(session, "topic", "plasticity")
    c1 = get_or_create_grouping(session, "topic", "neuroplasticity")
    c2 = get_or_create_grouping(session, "topic", "circuit plasticity")
    set_parent(session, c1.id, parent.id)
    set_parent(session, c2.id, parent.id)
    assert set(resolve_filter_ids(session, parent.id)) == {parent.id, c1.id, c2.id}
    assert resolve_filter_ids(session, c1.id) == [c1.id]


def test_rollup_parents(session):
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "topic", "neuroplasticity")
    top_only = get_or_create_grouping(session, "topic", "stroke")
    set_parent(session, child.id, parent.id)
    assert set(rollup_parents(session, [child.id])) == {child.id, parent.id}
    assert rollup_parents(session, [top_only.id]) == [top_only.id]
    assert sorted(rollup_parents(session, [child.id, parent.id])) == sorted(
        [child.id, parent.id]
    )


def test_get_anchor_ids_for_grouping(session):
    grouping = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, grouping.id, "paper", 11, status="confirmed")
    link_grouping(session, grouping.id, "paper", 12, status="confirmed")
    link_grouping(session, grouping.id, "study_note", 5, status="confirmed")
    papers = get_anchor_ids_for_grouping(session, grouping.id, "paper")
    assert sorted(papers) == [11, 12]
    assert get_anchor_ids_for_grouping(session, grouping.id, "study_note") == [5]
    assert get_anchor_ids_for_grouping(session, grouping.id, "dataset_packet") == []


def test_get_grouping_bundle(session):
    from neurodb.schema import Paper

    topic = get_or_create_grouping(session, "topic", "plasticity", description="d")
    concept = get_or_create_grouping(session, "concept", "LTP")
    paper = Paper(
        title="P1",
        normalized_title="p1",
        source_type="paper",
        topic_context="",
        status="approved",
        queued_at=_now(),
    )
    session.add(paper)
    session.flush()
    link_grouping(session, topic.id, "grouping", concept.id, status="confirmed")
    link_grouping(session, topic.id, "paper", paper.id, status="confirmed")
    bundle = get_grouping_bundle(session, topic.id)
    assert bundle["grouping"]["name"] == "plasticity"
    assert [c["name"] for c in bundle["concepts"]] == ["LTP"]
    assert [p["id"] for p in bundle["papers"]] == [paper.id]
    assert bundle["study_notes"] == []
    assert bundle["dataset_packets"] == []


def test_get_grouping_bundle_missing(session):
    assert get_grouping_bundle(session, 999999) == {}


def test_get_grouping_bundle_papers_include_data_tier_and_url(session):
    from neurodb.schema import Paper

    topic = get_or_create_grouping(session, "topic", "plasticity")
    paper = Paper(
        title="LTP paper",
        normalized_title="ltp paper",
        source_type="paper",
        topic_context="",
        status="approved",
        queued_at=_now(),
        data_tier="full_text",
        url="https://doi.org/10.1/ltp",
    )
    session.add(paper)
    session.flush()
    link_grouping(session, topic.id, "paper", paper.id, status="confirmed")

    bundle = get_grouping_bundle(session, topic.id)

    p = bundle["papers"][0]
    assert p["data_tier"] == "full_text"
    assert p["url"] == "https://doi.org/10.1/ltp"
    assert p["title"] == "LTP paper"


def test_get_groupings_for_anchor_includes_grouping_status(session):
    from neurodb.db.grouping_store import link_grouping
    g = get_or_create_grouping(session, "topic", "plasticity", status="proposed")
    link_grouping(session, g.id, "question", 5, status="pending")
    rows = get_groupings_for_anchor(session, "question", 5)
    assert rows[0]["grouping_status"] == "proposed"
    assert rows[0]["link_status"] == "pending"
