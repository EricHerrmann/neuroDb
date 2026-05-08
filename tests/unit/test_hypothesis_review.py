import importlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import neurodb.hypothesis_review as hypothesis_review
from neurodb.hypothesis_review import run_hypothesis_review
from neurodb.research_tools import draft_hypothesis
from neurodb.schema import Base, HypothesisReview, ModelCallLog, ResearchHypothesis


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _seed_hypothesis(engine) -> int:
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
    return result["id"]


def _client_response():
    return SimpleNamespace(
        content=[SimpleNamespace(
            type="text",
            text=json.dumps({
                "critique_text": "The draft needs stronger causal evidence.",
                "unsupported_claims": ["LTP changes directly improve learning"],
                "missing_confounds": ["task difficulty"],
                "suggested_revisions": "Limit the claim to a testable association.",
            }),
        )],
        usage=SimpleNamespace(input_tokens=321, output_tokens=123),
        stop_reason="end_turn",
    )


def test_run_hypothesis_review_uses_premium_model_and_persists_review(monkeypatch):
    monkeypatch.setenv("NEURODB_PREMIUM_MODEL", "claude-test-premium")
    importlib.reload(hypothesis_review)
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=_client_response())))

    result = hypothesis_review.run_hypothesis_review(hypothesis_id, engine, client)

    assert result["status"] == "reviewed"
    assert result["model"] == "claude-test-premium"
    assert result["unsupported_claims"] == ["LTP changes directly improve learning"]
    assert result["missing_confounds"] == ["task difficulty"]
    assert result["suggested_revisions"] == "Limit the claim to a testable association."
    assert client.messages.create.call_args.kwargs["model"] == "claude-test-premium"
    assert "critique" in client.messages.create.call_args.kwargs["system"].lower()

    with Session(engine) as session:
        assert session.query(ResearchHypothesis).count() == 1
        review = session.query(HypothesisReview).one()
        assert review.hypothesis_id == hypothesis_id
        log = session.query(ModelCallLog).one()
        assert log.task_type == "review.hypothesis"
        assert log.model == "claude-test-premium"
        assert log.input_tokens == 321
        assert log.output_tokens == 123


def test_run_hypothesis_review_accepts_explicit_model_override():
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)
    client = SimpleNamespace(messages=SimpleNamespace(create=Mock(return_value=_client_response())))

    result = run_hypothesis_review(
        hypothesis_id,
        engine,
        client,
        model="claude-explicit-premium",
    )

    assert result["model"] == "claude-explicit-premium"
    assert client.messages.create.call_args.kwargs["model"] == "claude-explicit-premium"
