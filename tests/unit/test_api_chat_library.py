"""Tests for deterministic Knowledge-Library search on flagged chat turns."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import chromadb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.chat import AgentAttempt, router
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.config.task_router import ModelRoute
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Base


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def _make_stores():
    client = chromadb.EphemeralClient()
    chunk_store = ChunkStore(client=client, embedder=_StubEmbedder(),
                             collection_name=f"ck_{uuid.uuid4().hex}")
    knowledge_store = KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                                            collection_name=f"kl_{uuid.uuid4().hex}")
    return chunk_store, knowledge_store


def _make_client(chunk_store, knowledge_store):
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = knowledge_store
    app.state.context_store = None
    app.state.chunk_store = chunk_store
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _mock_attempt():
    agent = MagicMock()
    agent.chat.return_value = iter(["grounded answer"])
    route = ModelRoute(task_type="agent.loop.neuro_tutor", tier="standard",
                       provider="anthropic", model_client=MagicMock(),
                       model_id="anthropic-model", max_tokens=2048)
    return AgentAttempt(route=route, agent=agent)


def _events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines()
            if line.startswith("data: ")]


def _post(client, message):
    with patch("neurodb.api.routes.chat._build_agent_attempt",
               return_value=_mock_attempt()) as attempt_mock, \
         patch("neurodb.api.routes.chat.build_provider_clients",
               return_value={"anthropic": MagicMock()}):
        resp = client.post("/api/chat/turn", json={
            "message": message, "history": [], "agent_mode": "neuro_tutor"})
    assert resp.status_code == 200
    return _events(resp), attempt_mock


def test_flagged_turn_emits_library_search_first_and_injects_full_content():
    chunk_store, knowledge_store = _make_stores()
    chunk_store.add_chunks(
        paper_id=9, title="Hopfield 1982", year=1982, currency_status="current",
        text_source="pdf_pymupdf",
        chunks=[Chunk(chunk_index=0,
                      text="collective computational abilities emerge",
                      section="Abstract", char_start=0, char_end=42)])
    client = _make_client(chunk_store, knowledge_store)

    events, attempt_mock = _post(
        client, "Use the knowledge library: who wrote about collective computation?")

    library = [e for e in events if e["type"] == "library_search"]
    assert len(library) == 1
    assert library[0]["full_text_count"] == 1
    assert events[0]["type"] == "library_search"  # visible before any content
    bundle = attempt_mock.call_args.args[8]  # context_bundle positional arg
    assert "collective computational abilities emerge" in bundle["prompt_block"]
    assert "MUST ground" in bundle["prompt_block"]


def test_flagged_turn_with_empty_library_injects_empty_state():
    chunk_store, knowledge_store = _make_stores()
    client = _make_client(chunk_store, knowledge_store)

    events, attempt_mock = _post(client, "check the library for lattice QCD")

    library = [e for e in events if e["type"] == "library_search"]
    assert library[0]["full_text_count"] == 0
    assert library[0]["summary_count"] == 0
    bundle = attempt_mock.call_args.args[8]
    assert "nothing relevant" in bundle["prompt_block"]


def test_non_flagged_turn_emits_no_library_search_event():
    chunk_store, knowledge_store = _make_stores()
    client = _make_client(chunk_store, knowledge_store)

    events, _ = _post(client, "explain long-term potentiation")

    assert [e for e in events if e["type"] == "library_search"] == []


def test_tutor_prompt_covers_author_and_content_questions():
    from neurodb.agents.tutor_agent import _TUTOR_SYSTEM_PROMPT

    assert "authors" in _TUTOR_SYSTEM_PROMPT
    assert "Knowledge Library results" in _TUTOR_SYSTEM_PROMPT
