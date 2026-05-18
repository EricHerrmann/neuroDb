import json

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.research_tools import (
    create_hypothesis_review,
    cross_reference_datasets,
    draft_hypothesis,
    get_knowledge_growth_metrics,
    load_app_preference,
    record_research_question,
    save_app_preference,
)
from neurodb.schema import (
    Base,
    ChatSession,
    DatasetIndex,
    HypothesisReview,
    IngestRun,
    KnowledgeGrowthSnapshot,
    Paper,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _engine_with_dataset():
    engine = _engine()
    with Session(engine) as session:
        run = IngestRun(source="openneuro", run_at="2026-05-06T00:00:00", version="test")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        session.add(StudyNote(
            index_id=idx.id,
            concept_tag="hippocampal plasticity",
            section_ref="LTP notes",
            note_text="Learning-related LTP candidate dataset.",
            tagged_at="2026-05-06T00:00:00",
        ))
        session.commit()
    return engine


def test_app_preference_helpers_save_and_load_agent_mode():
    engine = _engine()

    assert load_app_preference(engine, "agent_mode", "local_db") == "local_db"
    save_app_preference(
        engine,
        "agent_mode",
        "neuro_research",
        now="2026-05-06T00:00:00+00:00",
    )

    assert load_app_preference(engine, "agent_mode") == "neuro_research"


def test_record_research_question_persists_row():
    engine = _engine()
    result = record_research_question(
        engine,
        "How does LTP relate to learning?",
        "hippocampal plasticity",
        now="2026-05-06T00:00:00+00:00",
    )

    assert result["status"] == "recorded"
    with Session(engine) as session:
        row = session.query(ResearchQuestion).one()
        assert row.question.startswith("How does LTP")
        assert row.created_at == "2026-05-06T00:00:00+00:00"


def test_draft_hypothesis_requires_confounds_and_limitations():
    engine = _engine()

    missing_confounds = draft_hypothesis(
        engine,
        title="LTP hypothesis",
        mechanism="LTP supports learning.",
        evidence=[],
        predictions=[],
        datasets=[],
        confounds=[],
        limitations="Untested.",
    )
    assert "error" in missing_confounds

    missing_limitations = draft_hypothesis(
        engine,
        title="LTP hypothesis",
        mechanism="LTP supports learning.",
        evidence=[],
        predictions=[],
        datasets=[],
        confounds=["task design"],
        limitations="",
    )
    assert "error" in missing_limitations


def test_draft_hypothesis_persists_json_fields():
    engine = _engine()
    result = draft_hypothesis(
        engine,
        title="LTP learning hypothesis",
        mechanism="Hippocampal LTP changes measurable learning.",
        evidence=[{"source": "knowledge_library", "title": "LTP Review"}],
        predictions=["Learning measures covary with LTP-related signals."],
        datasets=[{"source": "openneuro", "source_id": "ds001"}],
        confounds=["task differences"],
        limitations="Draft only.",
        now="2026-05-06T00:00:00+00:00",
    )

    assert result["status"] == "drafted"
    with Session(engine) as session:
        row = session.query(ResearchHypothesis).one()
        assert json.loads(row.predictions_json) == [
            "Learning measures covary with LTP-related signals."
        ]


def test_create_hypothesis_review_persists_without_duplicating_hypothesis():
    engine = _engine()
    result = draft_hypothesis(
        engine,
        title="LTP learning hypothesis",
        mechanism="Hippocampal LTP changes measurable learning.",
        evidence=[{"source": "knowledge_library", "title": "LTP Review"}],
        predictions=["Learning measures covary with LTP-related signals."],
        datasets=[{"source": "openneuro", "source_id": "ds001"}],
        confounds=["task differences"],
        limitations="Draft only.",
        now="2026-05-06T00:00:00+00:00",
    )

    review = create_hypothesis_review(
        engine,
        result["id"],
        model="claude-opus-4-7",
        critique_text="The causal language is not yet supported.",
        unsupported_claims=["LTP causes learning improvement"],
        missing_confounds=["task design"],
        suggested_revisions="Frame as a testable association.",
        now="2026-05-08T00:00:00+00:00",
    )

    assert review["status"] == "reviewed"
    with Session(engine) as session:
        assert session.query(ResearchHypothesis).count() == 1
        row = session.query(HypothesisReview).one()
        assert row.hypothesis_id == result["id"]
        assert row.model == "claude-opus-4-7"
        assert row.status == "pending"
        assert json.loads(row.missing_confounds_json) == ["task design"]


def test_knowledge_growth_metrics_computes_counts_and_persists_on_demand():
    engine = _engine()
    with Session(engine) as session:
        session.add(Paper(
            title="LTP Review",
            normalized_title="ltp review",
            source_type="review",
            topic_context="plasticity",
            status="approved",
            queued_at="2026-05-06T00:00:00",
        ))
        session.add(ChatSession(
            session_id="sess-1",
            inferred_topic="LTP",
            agent_mode="neuro_tutor",
            started_at="2026-05-06T00:00:00",
            message_count=3,
        ))
        session.commit()

    metrics = get_knowledge_growth_metrics(engine)
    assert metrics["approved_sources_count"] == 1
    assert metrics["chat_sessions_count"] == 1

    persisted = get_knowledge_growth_metrics(
        engine,
        persist=True,
        now="2026-05-06T00:00:00+00:00",
    )
    assert persisted["snapshot_id"]
    with Session(engine) as session:
        row = session.query(KnowledgeGrowthSnapshot).one()
        assert row.approved_sources_count == 1


def test_cross_reference_datasets_matches_study_notes_without_vector_store():
    engine = _engine_with_dataset()

    result = cross_reference_datasets(engine, "hippocampal LTP learning")

    assert result["candidates"]
    candidate = result["candidates"][0]
    assert candidate["source"] == "openneuro"
    assert candidate["source_id"] == "ds001"
    assert candidate["matched_notes"][0]["concept_tag"] == "hippocampal plasticity"
    assert "semantic search unavailable" in result["limitations"][0]


def test_cross_reference_datasets_returns_empty_with_limitation_on_no_match():
    engine = _engine_with_dataset()

    result = cross_reference_datasets(engine, "retinotopy visual cortex")

    assert result["candidates"] == []
    assert any("no local datasets matched" in item for item in result["limitations"])
