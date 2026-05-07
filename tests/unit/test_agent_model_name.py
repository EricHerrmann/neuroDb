import os
from importlib import reload
from unittest.mock import MagicMock, patch


def test_agent_uses_neurodb_agent_model_env_var():
    """If NEURODB_AGENT_MODEL is set, NeuroDbAgent uses it as the model."""
    with patch.dict(os.environ, {"NEURODB_AGENT_MODEL": "claude-test-model"}, clear=False):
        import neurodb.agents.db_agent

        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent

        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == "claude-test-model"

    reload(neurodb.agents.db_agent)


def test_agent_falls_back_to_sonnet_when_env_var_not_set():
    """Without NEURODB_AGENT_MODEL, NeuroDbAgent defaults to claude-sonnet-4-6."""
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_AGENT_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        import neurodb.agents.db_agent

        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent

        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == "claude-sonnet-4-6"

    reload(neurodb.agents.db_agent)
