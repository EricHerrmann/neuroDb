import os
from unittest.mock import MagicMock, patch


def test_agent_uses_neurodb_model_env_var():
    """If NEURODB_MODEL is set, agent.__init__ uses it as the default model."""
    with patch.dict(os.environ, {"NEURODB_MODEL": "claude-test-model"}):
        from importlib import reload
        import neurodb.agent
        reload(neurodb.agent)
        from neurodb.agent import NeuroAgent
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_vs = MagicMock()
        a = NeuroAgent(client=mock_client, engine=mock_engine, vector_store=mock_vs)
        assert a._model == "claude-test-model"


def test_agent_falls_back_to_default_model():
    """Without NEURODB_MODEL, agent uses the hardcoded default."""
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import neurodb.agent
        reload(neurodb.agent)
        from neurodb.agent import NeuroAgent, _DEFAULT_MODEL
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_vs = MagicMock()
        a = NeuroAgent(client=mock_client, engine=mock_engine, vector_store=mock_vs)
        assert a._model == _DEFAULT_MODEL
