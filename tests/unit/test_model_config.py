"""Tests for config-driven model table — load_model_config and get_model_for_task."""
import pytest

from neurodb.model_config import get_model_for_task, load_model_config


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
    provider, model_id, max_tokens = get_model_for_task("summary.session")
    assert provider == "anthropic"
    assert "haiku" in model_id.lower()
    assert max_tokens == 512


def test_get_model_for_task_standard_tier():
    provider, model_id, max_tokens = get_model_for_task("agent.loop.research")
    assert provider == "anthropic"
    assert "sonnet" in model_id.lower()
    assert max_tokens == 2048


def test_get_model_for_task_premium_tier():
    provider, model_id, max_tokens = get_model_for_task("research.hypothesis_review")
    assert provider == "anthropic"
    assert "opus" in model_id.lower()
    assert max_tokens == 4096


def test_get_model_for_task_unknown_raises():
    with pytest.raises(KeyError, match="unknown.task.xyz"):
        get_model_for_task("unknown.task.xyz")
