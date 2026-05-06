import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.agents.base import BaseAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.schema import Base, ResearchHypothesis, ResearchQuestion


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _block(name: str, inputs: dict):
    return SimpleNamespace(name=name, input=inputs)


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
