import os
from unittest.mock import MagicMock, patch


def test_agent_uses_neurodb_model_env_var():
    """If NEURODB_MODEL is set, agent.__init__ uses it as the default model."""
    with patch.dict(os.environ, {"NEURODB_MODEL": "claude-test-model"}):
        from importlib import reload
        import neurodb.agents.db_agent

        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent

        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == "claude-test-model"


def test_agent_falls_back_to_default_model():
    """Without NEURODB_MODEL, agent uses the hardcoded default."""
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import neurodb.agents.db_agent

        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent, _DEFAULT_MODEL

        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == _DEFAULT_MODEL

