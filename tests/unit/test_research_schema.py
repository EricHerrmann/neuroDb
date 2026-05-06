import json

from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from neurodb.schema import (
    AppPreference,
    Base,
    KnowledgeGrowthSnapshot,
    ResearchHypothesis,
    ResearchQuestion,
)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_research_tables_created():
    inspector = inspect(_engine())
    assert "research_questions" in inspector.get_table_names()
    assert "research_hypotheses" in inspector.get_table_names()
    assert "knowledge_growth_snapshots" in inspector.get_table_names()
    assert "app_preferences" in inspector.get_table_names()


def test_research_question_required_columns():
    cols = {c.key for c in ResearchQuestion.__table__.columns}
    assert {"question", "topic_context", "status", "created_at", "updated_at"} <= cols


def test_research_hypothesis_required_columns():
    cols = {c.key for c in ResearchHypothesis.__table__.columns}
    assert {
        "question_id",
        "title",
        "mechanism",
        "evidence_json",
        "predictions_json",
        "datasets_json",
        "confounds_json",
        "limitations",
        "status",
        "created_at",
        "updated_at",
    } <= cols


def test_knowledge_growth_snapshot_required_columns():
    cols = {c.key for c in KnowledgeGrowthSnapshot.__table__.columns}
    assert {
        "snapshot_at",
        "approved_sources_count",
        "pending_sources_count",
        "chat_sessions_count",
        "literature_searches_count",
        "study_notes_count",
        "research_questions_count",
        "research_hypotheses_count",
        "metrics_json",
    } <= cols


def test_app_preference_round_trip():
    engine = _engine()
    with Session(engine) as session:
        row = AppPreference(
            key="agent_mode",
            value="neuro_research",
            updated_at="2026-05-06T00:00:00+00:00",
        )
        session.add(row)
        session.commit()

    with Session(engine) as session:
        row = session.get(AppPreference, "agent_mode")
        assert row is not None
        assert row.value == "neuro_research"


def test_research_hypothesis_json_fields_store_valid_json():
    engine = _engine()
    with Session(engine) as session:
        row = ResearchHypothesis(
            title="LTP hypothesis",
            mechanism="Synaptic plasticity changes learning measures.",
            evidence_json=json.dumps([{"source": "knowledge_library"}]),
            predictions_json=json.dumps(["learning signal changes"]),
            datasets_json=json.dumps([]),
            confounds_json=json.dumps(["task differences"]),
            limitations="Untested draft.",
            status="draft",
            created_at="2026-05-06T00:00:00+00:00",
            updated_at="2026-05-06T00:00:00+00:00",
        )
        session.add(row)
        session.commit()

    with Session(engine) as session:
        row = session.query(ResearchHypothesis).one()
        assert json.loads(row.confounds_json) == ["task differences"]
