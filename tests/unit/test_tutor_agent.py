import json
import uuid
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.agents.tutor_agent import NeuroTutorAgent, normalize_title
from neurodb.db.grouping_store import get_or_create_grouping
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Base, Grouping, GroupingLink, Paper


class _StubEmbedder:
    def embed(self, texts):
        return [[0.2, 0.3, 0.4, 0.5] for _ in texts]


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _store():
    return KnowledgeLibraryStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"test_tutor_{uuid.uuid4().hex}",
    )


def _agent(engine=None):
    return NeuroTutorAgent(
        client=MagicMock(),
        engine=engine or _engine(),
        vector_store=None,
        knowledge_store=_store(),
    )


def test_tutor_agent_instantiates():
    assert _agent() is not None


def test_tutor_tool_list_contains_required_tools():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "search_knowledge_library" in names
    assert "queue_source" in names
    assert "update_source_metadata" in names
    assert "search_literature" in names
    assert "search_external" in names
    assert "inspect_external_dataset" in names
    assert "query_db" in names


def test_tutor_tool_list_excludes_write_dataset_discovery_tools():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "suggest_import" not in names


def test_normalize_title_strips_punctuation_and_spacing():
    assert normalize_title("  Principles of Neural Science! ") == "principles of neural science"


def test_queue_source_inserts_pending_row():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_queue_source({
        "title": "Principles of Neural Science",
        "source_type": "textbook",
        "topic_context": "synaptic plasticity",
    }))
    assert result["status"] == "queued"
    with Session(engine) as session:
        row = session.query(Paper).one()
        assert row.status == "pending"
        assert row.normalized_title == "principles of neural science"


def test_queue_source_dedups_by_doi():
    engine = _engine()
    agent = _agent(engine)
    params = {
        "title": "LTP Paper",
        "source_type": "paper",
        "topic_context": "LTP",
        "doi": "10.1234/ltp",
    }
    assert json.loads(agent._execute_queue_source(params))["status"] == "queued"
    assert json.loads(agent._execute_queue_source(params))["status"] == "already_exists"


def test_queue_source_dedups_by_normalized_title_without_doi():
    engine = _engine()
    agent = _agent(engine)
    assert json.loads(agent._execute_queue_source({
        "title": "Principles of Neural Science",
        "source_type": "textbook",
        "topic_context": "general",
    }))["status"] == "queued"
    assert json.loads(agent._execute_queue_source({
        "title": "  Principles of Neural Science!  ",
        "source_type": "textbook",
        "topic_context": "synaptic",
    }))["status"] == "already_exists"


def test_queue_source_updates_existing_title_match_with_new_url():
    engine = _engine()
    agent = _agent(engine)
    first = json.loads(agent._execute_queue_source({
        "title": "Modern Hopfield Networks and Attention",
        "source_type": "paper",
        "topic_context": "attention as associative memory",
    }))

    second = json.loads(agent._execute_queue_source({
        "title": "Modern Hopfield Networks and Attention",
        "source_type": "paper",
        "topic_context": "attention as associative memory",
        "url": "https://arxiv.org/abs/2008.02217",
        "doi": "10.48550/arXiv.2008.02217",
    }))

    assert second == {
        "status": "updated",
        "id": first["id"],
        "updated_fields": ["doi", "url"],
    }
    with Session(engine) as session:
        row = session.get(Paper, first["id"])
        assert row.url == "https://arxiv.org/abs/2008.02217"
        assert row.doi == "10.48550/arXiv.2008.02217"


def test_queue_source_reports_conflict_for_existing_url_without_overwrite():
    engine = _engine()
    agent = _agent(engine)
    first = json.loads(agent._execute_queue_source({
        "title": "Memory Consolidation Review",
        "source_type": "review",
        "topic_context": "memory consolidation",
        "url": "https://example.org/summary-page",
    }))

    second = json.loads(agent._execute_queue_source({
        "title": "Memory Consolidation Review",
        "source_type": "review",
        "topic_context": "memory consolidation",
        "url": "https://www.sciencedirect.com/science/article/pii/S0896627320300012",
    }))

    assert second["status"] == "already_exists"
    assert second["id"] == first["id"]
    assert second["updated_fields"] == []
    assert second["conflicts"] == [{
        "field": "url",
        "current": "https://example.org/summary-page",
        "submitted": "https://www.sciencedirect.com/science/article/pii/S0896627320300012",
    }]
    assert "update_source_metadata" in second["next_action"]
    with Session(engine) as session:
        row = session.get(Paper, first["id"])
        assert row.url == "https://example.org/summary-page"


def test_update_source_metadata_replaces_existing_url_by_source_id():
    engine = _engine()
    agent = _agent(engine)
    queued = json.loads(agent._execute_queue_source({
        "title": "Memory Consolidation Review",
        "source_type": "review",
        "topic_context": "memory consolidation",
        "url": "https://example.org/summary-page",
    }))

    result = json.loads(agent._execute_update_source_metadata({
        "source_id": queued["id"],
        "url": "https://www.sciencedirect.com/science/article/pii/S0896627320300012",
        "update_reason": "User confirmed the previous URL was a summary page.",
    }))

    assert result == {
        "status": "updated",
        "id": queued["id"],
        "updated_fields": ["url"],
        "previous_values": {"url": "https://example.org/summary-page"},
        "current_values": {
            "url": "https://www.sciencedirect.com/science/article/pii/S0896627320300012",
        },
        "update_reason": "User confirmed the previous URL was a summary page.",
    }
    with Session(engine) as session:
        row = session.get(Paper, queued["id"])
        assert row.url == "https://www.sciencedirect.com/science/article/pii/S0896627320300012"


def test_update_source_metadata_returns_unchanged_for_same_values():
    engine = _engine()
    agent = _agent(engine)
    queued = json.loads(agent._execute_queue_source({
        "title": "Memory Consolidation Review",
        "source_type": "review",
        "topic_context": "memory consolidation",
        "url": "https://example.org/article",
    }))

    result = json.loads(agent._execute_update_source_metadata({
        "source_id": queued["id"],
        "url": "https://example.org/article",
        "update_reason": "User asked to confirm the URL.",
    }))

    assert result["status"] == "unchanged"
    assert result["updated_fields"] == []
    assert result["current_values"]["url"] == "https://example.org/article"


def test_update_source_metadata_terminal_response_stops_tool_loop():
    engine = _engine()
    agent = _agent(engine)
    queued = json.loads(agent._execute_queue_source({
        "title": "Memory Consolidation Review",
        "source_type": "review",
        "topic_context": "memory consolidation",
        "url": "https://example.org/summary-page",
    }))
    block = SimpleNamespace(
        tool_name="update_source_metadata",
        tool_input={
            "source_id": queued["id"],
            "url": "https://example.org/article",
            "update_reason": "User provided corrected article URL.",
        },
    )

    result_text = agent._execute_tool_block(block)
    terminal = agent._build_terminal_tool_response([{
        "tool": "update_source_metadata",
        "input": block.tool_input,
        "result": result_text,
    }])

    assert terminal == f"Updated Knowledge Library source {queued['id']}: url."


def test_search_knowledge_library_uses_store():
    store = _store()
    store.add_summary(1, "LTP Review", None, "plasticity", "Hippocampus LTP summary")
    agent = NeuroTutorAgent(MagicMock(), _engine(), knowledge_store=store)

    results = json.loads(agent._execute_search_knowledge_library({"query": "LTP"}))
    assert len(results) == 1
    assert results[0]["metadata"]["title"] == "LTP Review"


def test_search_literature_uses_literature_client():
    class _LiteratureClient:
        def __init__(self):
            self.queries = []

        def search(self, query):
            self.queries.append(query)
            return [{
                "title": "Hippocampal long-term potentiation and memory",
                "doi": "10.1000/ltp",
                "abstract": "LTP abstract",
                "source_type": "paper",
                "year": 2024,
                "citation_count": 10,
                "source": "pubmed",
            }]

    literature_client = _LiteratureClient()
    agent = NeuroTutorAgent(
        MagicMock(),
        _engine(),
        knowledge_store=_store(),
        literature_client=literature_client,
    )

    results = json.loads(agent._execute_search_literature({"query": "LTP plasticity"}))

    assert literature_client.queries == ["LTP plasticity"]
    assert results[0]["source"] == "pubmed"
    assert results[0]["doi"] == "10.1000/ltp"


def test_search_external_dispatch_uses_discovery_tool():
    agent = _agent()
    block = SimpleNamespace(
        tool_name="search_external",
        tool_input={"source": "all", "query": "plasticity", "limit": 3},
    )

    with patch(
        "neurodb.agents.tutor_agent.run_search_external",
        return_value=json.dumps([{"source": "openneuro", "id": "ds000001"}]),
    ) as search_external:
        result = json.loads(agent._execute_tool_block(block))

    search_external.assert_called_once_with("all", "plasticity", 3)
    assert result == [{"source": "openneuro", "id": "ds000001"}]


def test_inspect_external_dataset_dispatch_uses_discovery_tool():
    agent = _agent()
    block = SimpleNamespace(
        tool_name="inspect_external_dataset",
        tool_input={"source": "auto", "reference": "https://openneuro.org/datasets/ds000001"},
    )

    with patch(
        "neurodb.agents.tutor_agent.run_inspect_external_dataset",
        return_value=json.dumps({"source": "openneuro", "source_id": "ds000001"}),
    ) as inspect_external:
        result = json.loads(agent._execute_tool_block(block))

    inspect_external.assert_called_once_with(
        "auto",
        "https://openneuro.org/datasets/ds000001",
    )
    assert result == {"source": "openneuro", "source_id": "ds000001"}


def test_system_prompt_contains_tutor_instructions():
    prompt = _agent()._build_system_prompt().lower()
    assert "knowledge library" in prompt
    assert "queue_source" in prompt
    assert "update_source_metadata" in prompt
    assert "search external sites" in prompt
    assert "call search_external" in prompt
    assert "call inspect_external_dataset" in prompt
    assert "do not say you cannot search or browse external sites" in prompt
    assert "never write that a source is queued" in prompt
    assert "audit those references against tool results" in prompt
    assert "readable markdown" in prompt
    assert "bold emphasis" in prompt
    assert "simple markdown tables" in prompt


def test_tutor_prompt_includes_context_mode_and_bundle():
    agent = _agent()
    agent._context_mode = "grounded"
    agent._context_bundle = {
        "prompt_block": "NeuroDb context mode: grounded\npapers=1",
    }

    prompt = agent._build_system_prompt()

    assert "Context mode: Strictly grounded" in prompt
    assert "NeuroDb context mode: grounded" in prompt


def test_search_topics_and_get_grouping_bundle_in_tool_list():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "search_topics" in names
    assert "get_grouping_bundle" in names


def test_queue_source_tool_schema_has_topics_field():
    tools = {t["name"]: t for t in _agent()._get_active_tools()}
    props = tools["queue_source"]["input_schema"]["properties"]
    assert "topics" in props
    assert props["topics"]["type"] == "array"


def test_search_topics_tool_returns_matching_topics():
    engine = _engine()
    with Session(engine) as s:
        get_or_create_grouping(s, "topic", "hippocampal plasticity")
        s.commit()
    agent = _agent(engine)
    block = SimpleNamespace(tool_name="search_topics", tool_input={"query": "hippocampal"})
    result = json.loads(agent._execute_tool_block(block))
    assert any(r["name"] == "hippocampal plasticity" for r in result)


def test_get_grouping_bundle_tool_returns_bundle():
    engine = _engine()
    with Session(engine) as s:
        topic = get_or_create_grouping(s, "topic", "stroke recovery")
        s.commit()
        topic_id = topic.id
    agent = _agent(engine)
    block = SimpleNamespace(tool_name="get_grouping_bundle", tool_input={"grouping_id": topic_id})
    result = json.loads(agent._execute_tool_block(block))
    assert result["grouping"]["name"] == "stroke recovery"


def test_queue_source_with_topics_creates_links():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_queue_source({
        "title": "LTP Review Paper",
        "source_type": "paper",
        "topic_context": "hippocampal plasticity",
        "topics": ["hippocampal plasticity", "synaptic potentiation"],
    }))
    assert result["status"] == "queued"
    paper_id = result["id"]
    with Session(engine) as s:
        links = s.query(GroupingLink).filter_by(
            anchor_type="paper", anchor_id=paper_id
        ).all()
        assert len(links) == 2
        grouping_ids = {link.grouping_id for link in links}
        names = {s.get(Grouping, grouping_id).name for grouping_id in grouping_ids}
    assert names == {"hippocampal plasticity", "synaptic potentiation"}


def test_tutor_tag_paper_writes_grouping_link():
    engine = _engine()
    agent = _agent(engine)
    result = json.loads(agent._execute_queue_source({
        "title": "Queued",
        "source_type": "paper",
        "topic_context": "",
        "topics": ["plasticity"],
    }))
    assert result["status"] == "queued"

    with Session(engine) as s:
        link = s.query(GroupingLink).filter_by(
            anchor_type="paper",
            anchor_id=result["id"],
        ).one()
        grouping = s.get(Grouping, link.grouping_id)
    assert grouping.type == "topic"
    assert grouping.name == "plasticity"


def test_system_prompt_mentions_topic_retrieval_tools():
    prompt = _agent()._build_system_prompt()
    assert "search_topics" in prompt
    assert "get_grouping_bundle" in prompt


def test_queue_source_tool_lists_preprint_type():
    from neurodb.agents.tutor_agent import _TUTOR_TOOLS

    queue_tool = next(t for t in _TUTOR_TOOLS if t["name"] == "queue_source")
    desc = queue_tool["input_schema"]["properties"]["source_type"]["description"]
    assert "preprint" in desc.lower()
