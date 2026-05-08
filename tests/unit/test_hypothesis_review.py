import importlib
import json
from types import SimpleNamespace
from unittest.mock import MagicMock, Mock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

import neurodb.research.hypothesis_review as hypothesis_review
from neurodb.research.hypothesis_review import run_hypothesis_review
from neurodb.config.model_client import ContentBlock, ModelResponse
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


def _critique_tool_response(model="claude-opus-4-7"):
    """Build a ModelResponse with a submit_critique tool_use block."""
    return ModelResponse(
        stop_reason="tool_use",
        content=[ContentBlock(
            type="tool_use",
            tool_name="submit_critique",
            tool_use_id="tu_review_1",
            tool_input={
                "critique_text": "The draft needs stronger causal evidence.",
                "unsupported_claims": ["LTP changes directly improve learning"],
                "missing_confounds": ["task difficulty"],
                "suggested_revisions": "Limit the claim to a testable association.",
            },
        )],
        input_tokens=321,
        output_tokens=123,
    )


def _make_model_client(response: ModelResponse):
    """Build a minimal ModelClient mock that returns the given response."""
    mc = MagicMock()
    mc.create_message.return_value = response
    mc.format_tool.side_effect = lambda t: t
    return mc


def test_run_hypothesis_review_uses_premium_model_and_persists_review(monkeypatch):
    monkeypatch.setenv("NEURODB_PREMIUM_MODEL", "claude-test-premium")
    importlib.reload(hypothesis_review)
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)
    mc = _make_model_client(_critique_tool_response())

    result = hypothesis_review.run_hypothesis_review(
        hypothesis_id, engine, model_client=mc, model="claude-test-premium"
    )

    assert result["status"] == "reviewed"
    assert result["model"] == "claude-test-premium"
    assert result["unsupported_claims"] == ["LTP changes directly improve learning"]
    assert result["missing_confounds"] == ["task difficulty"]
    assert result["suggested_revisions"] == "Limit the claim to a testable association."
    assert mc.create_message.call_args.kwargs["model"] == "claude-test-premium"
    assert "critique" in mc.create_message.call_args.kwargs["system"].lower()

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
    mc = _make_model_client(_critique_tool_response())

    result = run_hypothesis_review(
        hypothesis_id,
        engine,
        model_client=mc,
        model="claude-explicit-premium",
    )

    assert result["model"] == "claude-explicit-premium"
    assert mc.create_message.call_args.kwargs["model"] == "claude-explicit-premium"


def test_run_hypothesis_review_with_legacy_sdk_client():
    """Backward compat: raw Anthropic SDK client is wrapped in AnthropicModelClient."""
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)

    # Legacy SDK client returns SDK response with text block containing JSON
    sdk_response = SimpleNamespace(
        content=[SimpleNamespace(
            type="text",
            text=json.dumps({
                "critique_text": "Needs causal evidence.",
                "unsupported_claims": ["claim A"],
                "missing_confounds": ["confound B"],
                "suggested_revisions": "Clarify the causal chain.",
            }),
        )],
        usage=SimpleNamespace(input_tokens=100, output_tokens=50),
        stop_reason="end_turn",
    )
    legacy_client = SimpleNamespace(
        messages=SimpleNamespace(create=Mock(return_value=sdk_response))
    )

    result = run_hypothesis_review(hypothesis_id, engine, client=legacy_client)

    assert result["status"] == "reviewed"
    assert result["critique_text"] == "Needs causal evidence."


def test_run_hypothesis_review_tool_use_populates_all_fields():
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)
    mc = _make_model_client(_critique_tool_response())

    result = run_hypothesis_review(hypothesis_id, engine, model_client=mc)

    assert result["critique_text"] == "The draft needs stronger causal evidence."
    assert isinstance(result["unsupported_claims"], list)
    assert len(result["unsupported_claims"]) == 1
    assert isinstance(result["missing_confounds"], list)
    assert result["suggested_revisions"] != ""


def test_run_hypothesis_review_uses_submit_critique_tool_in_request():
    engine = _engine()
    hypothesis_id = _seed_hypothesis(engine)
    mc = _make_model_client(_critique_tool_response())

    run_hypothesis_review(hypothesis_id, engine, model_client=mc)

    tools_arg = mc.create_message.call_args.kwargs["tools"]
    tool_names = [t["name"] for t in tools_arg]
    assert "submit_critique" in tool_names
