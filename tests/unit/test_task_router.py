"""Tests for TaskRouter — routes task_type to (ModelClient, model_id, max_tokens)."""
from unittest.mock import MagicMock

import pytest

from neurodb.config.model_client import ModelClient
from neurodb.config.task_router import ModelRoute, TaskRouter


def _mock_client() -> ModelClient:
    client = MagicMock(spec=ModelClient)
    return client


def test_task_router_route_returns_three_tuple():
    openai_client = _mock_client()
    router = TaskRouter({"openai": openai_client})
    route = router.route("agent.loop.research")
    assert isinstance(route, ModelRoute)
    assert route.model_client is openai_client
    assert route.provider == "openai"
    assert route.tier == "standard"
    assert isinstance(route.model_id, str)
    assert isinstance(route.max_tokens, int)


def test_task_router_research_loop_is_standard_tier():
    openai_client = _mock_client()
    router = TaskRouter({"openai": openai_client})
    route = router.route("agent.loop.research")
    assert "gpt" in route.model_id.lower()


def test_task_router_hypothesis_review_is_premium_tier():
    openai_client = _mock_client()
    router = TaskRouter({"openai": openai_client})
    route = router.route("research.hypothesis_review")
    assert "gpt" in route.model_id.lower()
    assert route.tier == "premium"


def test_task_router_session_summary_is_economy_tier():
    openai_client = _mock_client()
    router = TaskRouter({"openai": openai_client})
    route = router.route("summary.session")
    assert "mini" in route.model_id.lower()
    assert route.max_tokens == 512
    assert route.tier == "economy"


def test_task_router_unknown_task_raises():
    router = TaskRouter({"anthropic": _mock_client()})
    with pytest.raises(KeyError):
        router.route("unknown.task.xyz")


def test_task_router_missing_provider_raises():
    router = TaskRouter({})  # no providers registered
    with pytest.raises(KeyError):
        router.route("agent.loop.research")
