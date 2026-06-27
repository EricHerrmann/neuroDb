"""Tests for config-driven model table — load_model_config and get_model_for_task."""
import pytest

from neurodb.config.model_config import (
    get_context_budget,
    get_model_for_task,
    get_provider_fallback_order,
    get_task_config,
    get_tier_provider_config,
    load_model_config,
)


def test_load_model_config_returns_dict():
    config = load_model_config()
    assert isinstance(config, dict)


def test_load_model_config_has_tiers():
    config = load_model_config()
    assert "tiers" in config
    assert "economy" in config["tiers"]
    assert "standard" in config["tiers"]
    assert "premium" in config["tiers"]


def test_load_model_config_has_tasks():
    config = load_model_config()
    assert "tasks" in config


def test_get_model_for_task_economy_tier():
    """Primary provider/model come from whatever [routing] defaults the economy tier to."""
    config = load_model_config()
    expected_provider = config["routing"]["economy"]
    expected_model = config["tiers"]["economy"]["providers"][expected_provider]["model"]

    provider, model_id, max_tokens = get_model_for_task("summary.session")

    assert provider == expected_provider
    assert model_id == expected_model
    assert max_tokens == 512


def test_get_model_for_task_standard_tier():
    """Primary provider/model come from whatever [routing] defaults the standard tier to."""
    config = load_model_config()
    expected_provider = config["routing"]["standard"]
    expected_model = config["tiers"]["standard"]["providers"][expected_provider]["model"]

    provider, model_id, max_tokens = get_model_for_task("agent.loop.research")

    assert provider == expected_provider
    assert model_id == expected_model
    assert max_tokens == 8192


def test_get_model_for_task_routing_section_selects_openai(monkeypatch):
    """Provider comes from [routing] section in TOML — openai case."""
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    patched = {**base, "routing": {**base.get("routing", {}), "standard": "openai"}}
    monkeypatch.setattr(mc, "_cache", patched)

    provider, model_id, max_tokens = get_model_for_task("agent.loop.research")

    assert provider == "openai"
    assert model_id == "gpt-5.4"
    assert max_tokens == 8192


def test_get_model_for_task_routing_section_selects_gemini(monkeypatch):
    """Provider comes from [routing] section in TOML — gemini case."""
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    patched = {**base, "routing": {**base.get("routing", {}), "standard": "gemini"}}
    monkeypatch.setattr(mc, "_cache", patched)

    provider, model_id, max_tokens = get_model_for_task("agent.loop.research")

    assert provider == "gemini"
    assert model_id == "gemini-3.5-flash"
    assert max_tokens == 8192


def test_get_model_for_task_routing_section_unknown_provider_raises(monkeypatch):
    """KeyError if [routing] names a provider not in the tier's providers table."""
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    patched = {**base, "routing": {**base.get("routing", {}), "standard": "missing"}}
    monkeypatch.setattr(mc, "_cache", patched)

    with pytest.raises(KeyError, match="missing.*standard"):
        get_model_for_task("agent.loop.research")


def test_get_model_for_task_tier_env_var_has_no_effect(monkeypatch):
    """NEURODB_STANDARD_PROVIDER env var is ignored — provider comes from [routing] only."""
    routing_provider = load_model_config()["routing"]["standard"]
    # Force the env var to a value that differs from the configured routing provider,
    # so a passing test proves the env var had no effect.
    monkeypatch.setenv(
        "NEURODB_STANDARD_PROVIDER",
        "gemini" if routing_provider != "gemini" else "openai",
    )

    provider, _, _ = get_model_for_task("agent.loop.research")

    assert provider == routing_provider


def test_get_model_for_task_premium_tier():
    """Primary provider/model come from whatever [routing] defaults the premium tier to."""
    config = load_model_config()
    expected_provider = config["routing"]["premium"]
    expected_model = config["tiers"]["premium"]["providers"][expected_provider]["model"]

    provider, model_id, max_tokens = get_model_for_task("research.hypothesis_review")

    assert provider == expected_provider
    assert model_id == expected_model
    assert max_tokens == 4096


def test_get_task_config_returns_tier_and_tokens():
    tier, max_tokens = get_task_config("agent.loop.neuro_tutor")

    assert tier == "standard"
    # 8192 so tutor study-plan turns don't truncate mid-tool-call (was 4096).
    assert max_tokens == 8192


@pytest.mark.parametrize("tier", ["economy", "standard", "premium"])
def test_provider_fallback_order_primary_then_first_fallback(tier):
    """Accept whatever [routing] defaults to as primary, and also exercise the first fallback."""
    config = load_model_config()
    primary = config["routing"][tier]
    declared_fallback = config["routing"].get(f"{tier}_fallback", [])

    order = get_provider_fallback_order(tier)

    # Primary is whatever the model file defaults to, listed first, exactly once.
    assert order[0] == primary
    assert order.count(primary) == 1

    # First fallback is the first declared fallback that isn't the primary.
    expected_first_fallback = next(p for p in declared_fallback if p != primary)
    assert order[1] == expected_first_fallback
    # The first fallback must be a usable provider in this tier (resolves to a model).
    assert get_tier_provider_config(tier, expected_first_fallback)["model"]

    # All declared fallbacks remain present after dedup.
    assert set(declared_fallback).issubset(set(order))


def test_provider_fallback_order_tracks_primary_change(monkeypatch):
    import neurodb.config.model_config as mc

    base = mc.load_model_config()
    patched = {**base, "routing": {**base.get("routing", {}), "standard": "gemini"}}
    monkeypatch.setattr(mc, "_cache", patched)

    order = get_provider_fallback_order("standard")

    assert order[0] == "gemini"
    assert order.count("gemini") == 1
    assert "anthropic" in order[1:]


def test_provider_config_exposes_capability_flags():
    gemini = get_tier_provider_config("economy", "gemini")
    groq = get_tier_provider_config("premium", "groq")

    assert gemini["tool_loop_reliable"] is False
    assert groq["requires_tools"] is True
    assert groq["tool_loop_reliable"] is False


def test_get_model_for_task_unknown_raises():
    with pytest.raises(KeyError, match="unknown.task.xyz"):
        get_model_for_task("unknown.task.xyz")


def test_get_task_config_returns_agent_extract():
    tier, max_tokens = get_task_config("agent.extract")
    assert tier == "economy"
    assert max_tokens == 1024


def test_get_task_config_returns_agent_claim_review():
    tier, max_tokens = get_task_config("agent.claim_review")
    assert tier == "premium"
    assert max_tokens == 2048


def test_get_task_config_returns_agent_synthesis():
    tier, max_tokens = get_task_config("agent.synthesis")
    assert tier == "premium"
    assert max_tokens == 4096


def test_get_task_config_returns_agent_grounded_review():
    tier, max_tokens = get_task_config("agent.grounded_review")
    assert tier == "premium"
    assert max_tokens == 2048


def test_get_context_budget_returns_grounded_limits(tmp_path, monkeypatch):
    toml_content = b"""
[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("grounded")
    assert budget["papers"] == 10
    assert budget["notes"] == 15
    assert budget["claims"] == 12
    assert budget["datasets"] == 5


def test_get_context_budget_returns_none_when_section_absent(tmp_path, monkeypatch):
    toml_content = b"""
[routing]
economy = "anthropic"
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("grounded")
    assert budget is None


def test_get_context_budget_returns_none_for_unconfigured_mode(tmp_path, monkeypatch):
    toml_content = b"""
[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("general")
    assert budget is None
