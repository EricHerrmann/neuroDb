import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.agents.base import BaseAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.model_client import ContentBlock
from neurodb.schema import Base, ResearchHypothesis, ResearchQuestion


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _block(name: str, inputs: dict) -> ContentBlock:
    return ContentBlock(type="tool_use", tool_name=name, tool_use_id="test-id", tool_input=inputs)


def _tool_use_block(id_: str, name: str, inputs: dict):
    # Fake Anthropic SDK response block (mapped by AnthropicModelClient._map_response)
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=inputs)


def _response(stop_reason: str, content: list):
    return SimpleNamespace(stop_reason=stop_reason, content=content)


class _Stream:
    def __init__(self, events, final_message):
        self._events = events
        self._final_message = final_message

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def __iter__(self):
        return iter(self._events)

    def get_final_message(self):
        return self._final_message


def _agent(engine=None, **kwargs):
    return NeuroResearchAgent(
        client=MagicMock(),
        engine=engine or _engine(),
        **kwargs,
    )


def test_research_agent_inherits_base_agent():
    assert isinstance(_agent(), BaseAgent)


def test_research_tool_list_contains_expected_tools_and_excludes_tag_dataset():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "search_knowledge_library" in names
    assert "search_literature" in names
    assert "cross_reference_datasets" in names
    assert "get_knowledge_growth_metrics" in names
    assert "record_research_question" in names
    assert "draft_hypothesis" in names
    assert "query_db" in names
    assert "semantic_search" in names
    assert "get_study_notes" in names
    assert "tag_dataset" not in names


def test_research_prompt_includes_current_date_and_prior_context():
    agent = _agent(
        current_date="2026-05-06",
        prior_context="Prior sessions relevant to this topic: LTP",
    )

    prompt = agent._build_system_prompt()

    assert "Current date: 2026-05-06" in prompt
    assert "Prior sessions relevant" in prompt
    assert "confounds and limitations" in prompt


def test_research_agent_has_larger_default_tool_budget():
    agent = _agent()
    assert agent._max_tool_iterations > 10


def test_research_agent_saves_partial_progress_on_budget_exhaustion():
    engine = _engine()
    client = MagicMock()
    client.messages.create.return_value = SimpleNamespace(
        stop_reason="tool_use",
        content=[
            SimpleNamespace(type="text", text="I found candidate evidence."),
            SimpleNamespace(
                type="tool_use",
                id="tool-1",
                name="query_db",
                input={"sql": "SELECT count(*) AS count FROM research_questions"},
            ),
        ],
    )
    agent = NeuroResearchAgent(client, engine, max_tool_iterations=1)
    messages = []

    chunks = list(agent.chat("Draft a hypothesis", messages))

    assert "Partial research progress was saved" in chunks[0]
    assert len(messages) == 2
    assert messages[0] == {"role": "user", "content": "Draft a hypothesis"}
    saved_text = messages[1]["content"][0]["text"]
    assert "Partial research progress saved" in saved_text
    assert "I found candidate evidence" in saved_text
    assert "query_db" in saved_text
    assert not any(
        getattr(block, "type", None) == "tool_use"
        for message in messages
        for block in (
            message["content"]
            if isinstance(message.get("content"), list)
            else []
        )
    )


def test_research_agent_finishes_after_successful_draft_hypothesis_tool():
    engine = _engine()
    client = MagicMock()
    draft_input = {
        "title": "LTP learning hypothesis",
        "mechanism": "Hippocampal plasticity may affect learning-related measures.",
        "evidence": [{"source": "knowledge_library", "title": "LTP review"}],
        "predictions": ["Learning measures vary with LTP-related markers."],
        "datasets": [{"source": "openneuro", "source_id": "ds001"}],
        "confounds": ["task design"],
        "limitations": "Draft only; requires local testing.",
    }
    client.messages.create.return_value = _response("tool_use", [
        _tool_use_block("tool-1", "draft_hypothesis", draft_input)
    ])
    agent = NeuroResearchAgent(client, engine, max_tool_iterations=40)
    messages = []

    chunks = list(agent.chat("Draft a hypothesis", messages))

    assert client.messages.create.call_count == 1
    assert "Draft hypothesis saved" in chunks[0]
    assert "Confounds:" in chunks[0]
    assert "Limitations:" in chunks[0]
    assert len(messages) == 4
    assert messages[1]["content"][0]["type"] == "tool_use"
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[3]["role"] == "assistant"
    assert messages[3]["content"][0]["type"] == "text"
    with Session(engine) as session:
        assert session.query(ResearchHypothesis).count() == 1


def test_research_agent_stream_finishes_after_successful_draft_hypothesis_tool():
    engine = _engine()
    client = MagicMock()
    draft_input = {
        "title": "LTP learning hypothesis",
        "mechanism": "Hippocampal plasticity may affect learning-related measures.",
        "evidence": [{"source": "knowledge_library", "title": "LTP review"}],
        "predictions": ["Learning measures vary with LTP-related markers."],
        "datasets": [{"source": "openneuro", "source_id": "ds001"}],
        "confounds": ["task design"],
        "limitations": "Draft only; requires local testing.",
    }
    client.messages.stream.return_value = _Stream(
        [],
        _response("tool_use", [_tool_use_block("tool-1", "draft_hypothesis", draft_input)]),
    )
    agent = NeuroResearchAgent(client, engine, max_tool_iterations=40)
    messages = []

    events = list(agent.chat_stream("Draft a hypothesis", messages))

    assert client.messages.stream.call_count == 1
    assert events[0]["type"] == "tool_start"
    assert events[0]["iteration"] == 1
    assert events[0]["limit"] == 40
    assert events[-1]["type"] == "done"
    assert events[-1]["stop_reason"] == "terminal_tool_result"
    assert "Draft hypothesis saved" in events[-1]["text"]
    assert len(messages) == 4
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[3]["role"] == "assistant"


def test_search_knowledge_library_dispatch_uses_store():
    class _Store:
        def search(self, query, n=5):
            return [{"query": query, "n": n}]

    agent = _agent(knowledge_store=_Store())

    result = json.loads(agent._execute_tool_block(
        _block("search_knowledge_library", {"query": "LTP", "n_results": 2})
    ))

    assert result == [{"query": "LTP", "n": 2}]


def test_search_literature_dispatch_uses_literature_client():
    class _LiteratureClient:
        def search(self, query):
            return [{"title": "LTP Review", "query": query}]

    agent = _agent(literature_client=_LiteratureClient())

    result = json.loads(agent._execute_tool_block(
        _block("search_literature", {"query": "hippocampal LTP"})
    ))

    assert result[0]["title"] == "LTP Review"


def test_record_research_question_dispatch_persists_row():
    engine = _engine()
    agent = _agent(engine)

    result = json.loads(agent._execute_tool_block(_block(
        "record_research_question",
        {
            "question": "How does LTP relate to learning?",
            "topic_context": "hippocampal plasticity",
        },
    )))

    assert result["status"] == "recorded"
    with Session(engine) as session:
        assert session.query(ResearchQuestion).count() == 1


def test_draft_hypothesis_dispatch_persists_row():
    engine = _engine()
    agent = _agent(engine)

    result = json.loads(agent._execute_tool_block(_block(
        "draft_hypothesis",
        {
            "title": "LTP learning hypothesis",
            "mechanism": "LTP changes learning-related measures.",
            "evidence": [],
            "predictions": ["learning measures vary"],
            "datasets": [],
            "confounds": ["task differences"],
            "limitations": "Untested draft.",
        },
    )))

    assert result["status"] == "drafted"
    with Session(engine) as session:
        assert session.query(ResearchHypothesis).count() == 1


def test_research_agent_query_db_uses_read_only_db_tool():
    engine = _engine()
    agent = _agent(engine)

    result = json.loads(agent._execute_tool_block(_block(
        "query_db",
        {"sql": "SELECT count(*) AS count FROM research_questions"},
    )))

    assert result == [{"count": 0}]


def test_research_agent_uses_4096_max_tokens_by_default():
    engine = _engine()
    client = MagicMock()
    final_message = SimpleNamespace(
        stop_reason="end_turn",
        content=[SimpleNamespace(type="text", text="ok")],
    )
    client.messages.stream.return_value = _Stream([], final_message)

    agent = NeuroResearchAgent(client, engine)
    list(agent.chat_stream("test", []))

    assert client.messages.stream.call_args[1]["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# Per-agent model env vars (Phase 1.1)
# ---------------------------------------------------------------------------

def test_neuroresearch_agent_default_model_is_sonnet():
    import importlib
    import neurodb.agents.research_agent as mod
    assert mod._MODEL == "claude-sonnet-4-6"


def test_neuroresearch_agent_reads_neurodb_research_model_env_var():
    import importlib
    import os
    import unittest.mock
    with unittest.mock.patch.dict(os.environ, {"NEURODB_RESEARCH_MODEL": "claude-haiku-4-5"}, clear=False):
        import neurodb.agents.research_agent as mod
        reloaded = importlib.reload(mod)
        assert reloaded._MODEL == "claude-haiku-4-5"
    importlib.reload(mod)
