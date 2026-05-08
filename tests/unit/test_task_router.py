"""Tests for TaskRouter — routes task_type to (ModelClient, model_id, max_tokens)."""
from unittest.mock import MagicMock

import pytest

from neurodb.model_client import ModelClient
from neurodb.task_router import TaskRouter


def _mock_client() -> ModelClient:
    client = MagicMock(spec=ModelClient)
    return client


def test_task_router_route_returns_three_tuple():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    model_client, model_id, max_tokens = router.route("agent.loop.research")
    assert model_client is anthropic_client
    assert isinstance(model_id, str)
    assert isinstance(max_tokens, int)


def test_task_router_research_loop_is_standard_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    _, model_id, _ = router.route("agent.loop.research")
    assert "sonnet" in model_id.lower()


def test_task_router_hypothesis_review_is_premium_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    _, model_id, _ = router.route("research.hypothesis_review")
    assert "opus" in model_id.lower()


def test_task_router_session_summary_is_economy_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    _, model_id, max_tokens = router.route("summary.session")
    assert "haiku" in model_id.lower()
    assert max_tokens == 512


def test_task_router_unknown_task_raises():
    router = TaskRouter({"anthropic": _mock_client()})
    with pytest.raises(KeyError):
        router.route("unknown.task.xyz")


def test_task_router_missing_provider_raises():
    router = TaskRouter({})  # no providers registered
    with pytest.raises(KeyError):
        router.route("agent.loop.research")
