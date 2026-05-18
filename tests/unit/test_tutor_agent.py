import json
import uuid
from unittest.mock import MagicMock

import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.agents.tutor_agent import NeuroTutorAgent, normalize_title
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Base, Paper


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
    assert "search_literature" in names
    assert "query_db" in names


def test_tutor_tool_list_excludes_dataset_discovery_tools():
    names = {tool["name"] for tool in _agent()._get_active_tools()}
    assert "search_external" not in names
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


def test_system_prompt_contains_tutor_instructions():
    prompt = _agent()._build_system_prompt().lower()
    assert "knowledge library" in prompt
    assert "queue_source" in prompt
