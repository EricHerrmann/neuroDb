"""The grouping matcher task type must be routable (Groupings Phase 3a)."""
from neurodb.config.model_config import get_task_config


def test_agent_extract_groupings_task_configured():
    tier, max_tokens = get_task_config("agent.extract.groupings")
    assert tier == "standard"
    assert max_tokens == 1024
