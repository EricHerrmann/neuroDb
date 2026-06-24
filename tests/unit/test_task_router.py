"""Tests for TaskRouter — routes task_type to (ModelClient, model_id, max_tokens)."""
from unittest.mock import MagicMock

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from neurodb.config.model_client import ModelClient
from neurodb.config.model_config import get_provider_fallback_order
from neurodb.config.task_router import ModelRoute, RoutingError, TaskRouter
from neurodb.schema import Base, SystemWarning


def _mock_client() -> ModelClient:
    client = MagicMock(spec=ModelClient)
    return client


def test_task_router_route_returns_three_tuple():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    route = router.route("agent.loop.research")
    assert isinstance(route, ModelRoute)
    assert route.model_client is anthropic_client
    assert route.provider == "anthropic"
    assert route.tier == "standard"
    assert isinstance(route.model_id, str)
    assert isinstance(route.max_tokens, int)


def test_task_router_research_loop_is_standard_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    route = router.route("agent.loop.research")
    assert "claude" in route.model_id.lower()


def test_task_router_hypothesis_review_is_premium_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    route = router.route("research.hypothesis_review")
    assert "claude" in route.model_id.lower()
    assert route.tier == "premium"


def test_task_router_session_summary_is_economy_tier():
    anthropic_client = _mock_client()
    router = TaskRouter({"anthropic": anthropic_client})
    route = router.route("summary.session")
    assert "haiku" in route.model_id.lower()
    assert route.max_tokens == 512
    assert route.tier == "economy"


def test_task_router_unknown_task_raises():
    router = TaskRouter({"anthropic": _mock_client()})
    with pytest.raises(KeyError):
        router.route("unknown.task.xyz")


def test_task_router_missing_provider_raises():
    router = TaskRouter({})  # no providers registered
    with pytest.raises(RoutingError):
        router.route("agent.loop.research")


def test_task_router_primary_selected_writes_no_warning():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    primary = get_provider_fallback_order("standard")[0]
    primary_client = _mock_client()
    router = TaskRouter({primary: primary_client})

    route = router.route("agent.loop.research", engine=engine)

    assert route.provider == primary
    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert warnings == []


def test_task_router_falls_back_when_primary_provider_missing():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    primary, fallback = get_provider_fallback_order("standard")[:2]
    fallback_client = _mock_client()
    router = TaskRouter({fallback: fallback_client})

    route = router.route("agent.loop.research", engine=engine)

    assert route.provider == fallback
    assert route.model_client is fallback_client
    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert [row.warning_type for row in warnings] == ["provider_missing", "routing_fallback"]
    assert warnings[0].requested_provider == primary
    assert warnings[1].selected_provider == fallback


def test_task_router_falls_back_when_primary_excluded_after_runtime_failure():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    primary, fallback = get_provider_fallback_order("standard")[:2]
    fallback_client = _mock_client()
    router = TaskRouter({primary: _mock_client(), fallback: fallback_client})

    route = router.route_excluding(
        "agent.loop.research",
        engine=engine,
        excluded_providers={primary},
    )

    assert route.provider == fallback
    assert route.model_client is fallback_client
    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert [row.warning_type for row in warnings] == [
        "provider_runtime_failed",
        "routing_fallback",
    ]
    assert warnings[0].requested_provider == primary
    assert warnings[1].selected_provider == fallback


def test_task_router_falls_back_when_primary_degraded(monkeypatch):
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    standard = base["tiers"]["standard"]
    patched_standard = {
        **standard,
        "providers": {
            **standard["providers"],
            "openai": {**standard["providers"]["openai"], "eval_status": "degraded"},
        },
    }
    patched = {
        **base,
        "routing": {**base["routing"], "standard": "openai"},
        "tiers": {**base["tiers"], "standard": patched_standard},
    }
    monkeypatch.setattr(mc, "_cache", patched)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    router = TaskRouter({"openai": _mock_client(), "deepseek": _mock_client()})

    route = router.route("agent.loop.research", engine=engine)

    assert route.provider == "deepseek"
    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert warnings[0].warning_type == "provider_degraded"
    assert warnings[-1].warning_type == "routing_fallback"


def test_task_router_falls_back_on_capability_mismatch(monkeypatch):
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    economy = base["tiers"]["economy"]
    patched_economy = {
        **economy,
        "providers": {
            **economy["providers"],
            "groq": {
                **economy["providers"]["groq"],
                "requires_tools": True,
                "eval_status": "baseline",
            },
        },
    }
    patched = {
        **base,
        "routing": {**base["routing"], "economy": "groq"},
        "tiers": {**base["tiers"], "economy": patched_economy},
    }
    monkeypatch.setattr(mc, "_cache", patched)
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    router = TaskRouter({"groq": _mock_client(), "openai": _mock_client()})

    route = router.route("summary.session", engine=engine)

    assert route.provider == "openai"
    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert warnings[0].warning_type == "capability_mismatch"
    assert warnings[0].requested_provider == "groq"


def test_task_router_exhausted_fallback_chain_records_failure():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    router = TaskRouter({})

    with pytest.raises(RoutingError, match="no viable provider"):
        router.route("agent.loop.research", engine=engine)

    with Session(engine) as session:
        warnings = session.execute(select(SystemWarning)).scalars().all()
    assert warnings[-1].warning_type == "routing_failed"
    assert warnings[-1].severity == "error"
