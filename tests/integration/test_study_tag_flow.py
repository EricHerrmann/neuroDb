from sqlalchemy import create_engine

from neurodb.db import get_session, init_db
from neurodb.schema import DatasetIndex, IngestRun, StudyNote
from neurodb.study import list_tags, search_tags, tag_dataset


def _engine_with_dataset(source: str, source_id: str):
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with get_session(engine) as session:
        run = IngestRun(source=source, run_at="2026-04-24T00:00:00+00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source=source, source_id=source_id, run_id=run.id)
        session.add(idx)
    return engine


def test_tag_then_list_round_trip():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source="dandi",
            source_id="000003",
            concept_tag="primary visual cortex",
            section_ref="Augustine Ch13 p.312",
            note_text="V1 electrode recordings confirm retinotopic org",
        )
    assert note is not None
    assert note.id is not None

    with get_session(engine) as session:
        tags = list_tags(session)
    assert len(tags) == 1
    assert tags[0]["concept_tag"] == "primary visual cortex"
    assert tags[0]["source"] == "dandi"
    assert tags[0]["source_id"] == "000003"
    assert tags[0]["section_ref"] == "Augustine Ch13 p.312"


def test_tag_then_search_round_trip():
    engine = _engine_with_dataset("openneuro", "ds003684")
    with get_session(engine) as session:
        tag_dataset(
            session,
            source="openneuro",
            source_id="ds003684",
            concept_tag="auditory cortex",
            note_text="fMRI paradigm matches tonotopy discussion",
        )

    with get_session(engine) as session:
        results = search_tags(session, "tonotopy")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "auditory cortex"


def test_double_tag_creates_two_rows():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        tag_dataset(session, "dandi", "000003", "primary visual cortex")
        tag_dataset(session, "dandi", "000003", "retinotopic mapping")

    with get_session(engine) as session:
        count = session.query(StudyNote).count()
    assert count == 2


def test_tag_unknown_dataset_returns_none():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        result = tag_dataset(session, "dandi", "not-in-db", "some concept")
    assert result is None

    with get_session(engine) as session:
        assert session.query(StudyNote).count() == 0
