import json
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.agents.base import BaseAgent
from neurodb.agents.research_agent import NeuroResearchAgent
from neurodb.config.model_client import ContentBlock
from neurodb.schema import Base, Paper, ResearchHypothesis, ResearchQuestion


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
    assert "search_external" in names
    assert "inspect_external_dataset" in names
    assert "cross_reference_datasets" in names
    assert "get_knowledge_growth_metrics" in names
    assert "record_research_question" in names
    assert "draft_hypothesis" in names
    assert "query_db" in names
    assert "semantic_search" in names
    assert "get_study_notes" in names
    assert "tag_dataset" not in names
    assert "suggest_import" not in names


def test_all_array_properties_in_tool_schemas_have_items():
    # OpenAI rejects array schemas that are missing an 'items' field.
    def check_schema(schema, path=""):
        if isinstance(schema, dict):
            if schema.get("type") == "array":
                assert "items" in schema, f"Array at {path!r} is missing 'items'"
            for key, value in schema.items():
                check_schema(value, f"{path}.{key}")
        elif isinstance(schema, list):
            for i, item in enumerate(schema):
                check_schema(item, f"{path}[{i}]")

    for tool in _agent()._get_active_tools():
        check_schema(tool.get("input_schema", {}), tool["name"])


def test_research_prompt_includes_current_date_and_prior_context():
    agent = _agent(
        current_date="2026-05-06",
        prior_context="Prior sessions relevant to this topic: LTP",
    )

    prompt = agent._build_system_prompt()

    assert "Current date: 2026-05-06" in prompt
    assert "Prior sessions relevant" in prompt
    assert "confounds and limitations" in prompt
    assert "inspect_external_dataset" in prompt


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
        "evidence": [
            {
                "source": "knowledge_library",
                "summary": "LTP review supports plasticity hypothesis",
            }
        ],
        "predictions": ["Learning measures vary with LTP-related markers."],
        "datasets": [{"dataset_id": "ds001", "relevance": "contains LTP behavioral data"}],
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
        "evidence": [
            {
                "source": "knowledge_library",
                "summary": "LTP review supports plasticity hypothesis",
            }
        ],
        "predictions": ["Learning measures vary with LTP-related markers."],
        "datasets": [{"dataset_id": "ds001", "relevance": "contains LTP behavioral data"}],
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


def test_inspect_external_dataset_dispatch_uses_discovery_tool():
    agent = _agent()

    with patch(
        "neurodb.agents.research_agent.run_inspect_external_dataset",
        return_value='{"source": "dandi", "source_id": "000010"}',
    ) as inspect_dataset:
        result = json.loads(agent._execute_tool_block(
            _block(
                "inspect_external_dataset",
                {
                    "source": "auto",
                    "reference": "https://dandiarchive.org/dandiset/000010",
                },
            )
        ))

    inspect_dataset.assert_called_once_with("auto", "https://dandiarchive.org/dandiset/000010")
    assert result["source"] == "dandi"


def test_search_external_dispatch_uses_discovery_tool():
    agent = _agent()

    with patch(
        "neurodb.agents.research_agent.run_search_external",
        return_value='[{"source": "openneuro", "id": "ds000001"}]',
    ) as search_external:
        result = json.loads(agent._execute_tool_block(
            _block("search_external", {"source": "all", "query": "plasticity", "limit": 3})
        ))

    search_external.assert_called_once_with("all", "plasticity", 3)
    assert result[0]["source"] == "openneuro"


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
    import neurodb.agents.research_agent as mod
    assert mod._MODEL == "claude-sonnet-4-6"


def test_neuroresearch_agent_reads_neurodb_research_model_env_var():
    import importlib
    import os
    import unittest.mock
    with unittest.mock.patch.dict(
        os.environ,
        {"NEURODB_RESEARCH_MODEL": "claude-haiku-4-5"},
        clear=False,
    ):
        import neurodb.agents.research_agent as mod
        reloaded = importlib.reload(mod)
        assert reloaded._MODEL == "claude-haiku-4-5"
    importlib.reload(mod)


# ---------------------------------------------------------------------------
# Phase 3 — 6 new claim/evidence/gap tools
# ---------------------------------------------------------------------------

def test_new_claim_tools_present_in_active_tools():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "extract_claims" in names
    assert "update_claim_status" in names
    assert "add_evidence_link" in names
    assert "add_gap" in names
    assert "resolve_gap" in names
    assert "get_question_bundle" in names


def test_draft_hypothesis_evidence_is_optional():
    tool = next(
        t for t in _agent()._get_active_tools()
        if t["name"] == "draft_hypothesis"
    )
    assert "evidence" not in tool["input_schema"].get("required", [])


def test_system_prompt_mentions_get_question_bundle():
    prompt = _agent()._build_system_prompt()
    assert "get_question_bundle" in prompt


def test_update_claim_status_dispatch_updates_db():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        paper = Paper(
            title="Test Paper", normalized_title="test paper",
            source_type="paper", topic_context="test", status="approved",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        from neurodb.db.claim_store import create_claim
        claim = create_claim(session, paper.id, "A finding.", "finding")
        session.commit()
        claim_id = claim.id

    result = json.loads(agent._execute_tool_block(_block(
        "update_claim_status", {"claim_id": claim_id, "status": "approved"}
    )))
    assert result["status"] == "approved"


def test_add_gap_dispatch_persists_row():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="Does LTP matter?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.commit()
        q_id = q.id

    result = json.loads(agent._execute_tool_block(_block(
        "add_gap",
        {
            "description": "No fMRI data for this topic.",
            "gap_type": "missing_dataset",
            "question_id": q_id,
        },
    )))
    assert "id" in result


def test_resolve_gap_dispatch_updates_status():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="LTP and memory?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.flush()
        from neurodb.db.claim_store import add_gap
        gap = add_gap(session, "Missing data.", "missing_paper", question_id=q.id)
        session.commit()
        gap_id = gap.id

    result = json.loads(agent._execute_tool_block(_block(
        "resolve_gap", {"gap_id": gap_id}
    )))
    assert result["status"] == "resolved"


def test_get_question_bundle_dispatch_returns_bundle_shape():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        q = ResearchQuestion(
            question="LTP question?", topic_context="plasticity",
            status="open", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(q)
        session.commit()
        q_id = q.id

    result = json.loads(agent._execute_tool_block(_block(
        "get_question_bundle", {"question_id": q_id}
    )))
    assert set(result.keys()) == {"question", "topic", "hypotheses", "claims", "gaps"}


def test_extract_claims_dispatch_returns_error_for_missing_paper():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_tool_block(_block(
        "extract_claims", {"paper_id": 9999}
    )))
    assert "error" in result


def test_extract_claims_dispatch_returns_error_for_unapproved_paper():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        paper = Paper(
            title="Pending Paper", normalized_title="pending paper",
            source_type="paper", topic_context="test", status="pending",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.commit()
        paper_id = paper.id

    result = json.loads(agent._execute_tool_block(_block(
        "extract_claims", {"paper_id": paper_id}
    )))
    assert "error" in result
    assert "not approved" in result["error"]


def test_add_evidence_link_dispatch_persists_link():
    engine = _engine()
    agent = _agent(engine)
    with Session(engine) as session:
        paper = Paper(
            title="LTP Paper", normalized_title="ltp paper",
            source_type="paper", topic_context="plasticity", status="approved",
            queued_at="2026-01-01T00:00:00",
        )
        session.add(paper)
        session.flush()
        hyp = ResearchHypothesis(
            title="Test hyp", mechanism="LTP.",
            predictions_json="[]", limitations="draft",
            status="draft", created_at="2026-01-01T00:00:00", updated_at="2026-01-01T00:00:00",
        )
        session.add(hyp)
        session.commit()
        paper_id = paper.id
        hyp_id = hyp.id

    result = json.loads(agent._execute_tool_block(_block(
        "add_evidence_link",
        {
            "hypothesis_id": hyp_id,
            "link_type": "contextualizes",
            "source_type": "paper",
            "source_id": paper_id,
        },
    )))
    assert "id" in result
    assert result["link_type"] == "contextualizes"
    assert result["source_type"] == "paper"


def test_add_evidence_link_dispatch_returns_error_for_unknown_source_type():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_tool_block(_block(
        "add_evidence_link",
        {
            "hypothesis_id": 1,
            "link_type": "supports",
            "source_type": "unknown_type",
            "source_id": 1,
        },
    )))
    assert "error" in result
