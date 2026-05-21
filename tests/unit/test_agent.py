"""Unit tests for NeuroDb agent — mocks Anthropic client, no real API calls."""
import importlib
import json
import os
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, IngestRun
from neurodb.agents.db_agent import TOOLS, NeuroDbAgent, execute_tool


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _engine_with_dataset():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="dandi", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.commit()
    return engine


def _text_block(text: str):
    block = SimpleNamespace()
    block.type = "text"
    block.text = text
    return block


def _tool_use_block(tool_id: str, name: str, inputs: dict):
    block = SimpleNamespace()
    block.type = "tool_use"
    block.id = tool_id
    block.name = name
    block.input = inputs
    return block


def _response(stop_reason: str, content: list):
    r = SimpleNamespace()
    r.stop_reason = stop_reason
    r.content = content
    return r


def _text_delta_event(text: str):
    return SimpleNamespace(
        type="content_block_delta",
        delta=SimpleNamespace(type="text_delta", text=text),
    )


class _Stream:
    def __init__(self, events: list, final_message):
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


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

def test_tools_list_has_four_entries():
    assert len(TOOLS) == 4


def test_tool_names():
    names = {t["name"] for t in TOOLS}
    assert names == {"query_db", "semantic_search", "get_study_notes", "tag_dataset"}


def test_each_tool_has_required_fields():
    for tool in TOOLS:
        assert "name" in tool
        assert "description" in tool
        assert "input_schema" in tool
        assert tool["input_schema"]["type"] == "object"


# ---------------------------------------------------------------------------
# execute_tool — query_db
# ---------------------------------------------------------------------------

def test_execute_query_db_returns_json(tmp_path):
    engine = _engine_with_dataset()
    result = execute_tool("query_db", {"sql": "SELECT source_id FROM datasets_index"}, engine, None)
    rows = json.loads(result)
    assert isinstance(rows, list)


def test_execute_query_db_blocks_non_select():
    engine = _engine_with_dataset()
    result = execute_tool("query_db", {"sql": "DROP TABLE datasets_index"}, engine, None)
    obj = json.loads(result)
    assert "error" in obj


def test_execute_query_db_handles_bad_sql():
    engine = _engine_with_dataset()
    result = execute_tool("query_db", {"sql": "SELECT * FROM nonexistent_table_xyz"}, engine, None)
    obj = json.loads(result)
    assert "error" in obj


# ---------------------------------------------------------------------------
# execute_tool — get_study_notes
# ---------------------------------------------------------------------------

def test_execute_get_study_notes_returns_list():
    engine = _engine_with_dataset()
    result = execute_tool("get_study_notes", {}, engine, None)
    rows = json.loads(result)
    assert isinstance(rows, list)


def test_execute_get_study_notes_filters_concept():
    engine = _engine_with_dataset()
    from neurodb.study import tag_dataset
    with Session(engine) as session:
        tag_dataset(session, "dandi", "000003", "hippocampus place cells")
        session.commit()

    result = execute_tool("get_study_notes", {"concept": "hippocampus"}, engine, None)
    rows = json.loads(result)
    assert len(rows) == 1
    assert "hippocampus" in rows[0]["concept_tag"]


# ---------------------------------------------------------------------------
# execute_tool — tag_dataset
# ---------------------------------------------------------------------------

def test_execute_tag_dataset_success():
    engine = _engine_with_dataset()
    result = execute_tool(
        "tag_dataset",
        {"source": "dandi", "source_id": "000003", "concept_tag": "grid cells"},
        engine,
        None,
    )
    obj = json.loads(result)
    assert obj["success"] is True
    assert "tag_id" in obj


def test_execute_tag_dataset_unknown_dataset():
    engine = _engine_with_dataset()
    result = execute_tool(
        "tag_dataset",
        {"source": "dandi", "source_id": "does-not-exist", "concept_tag": "grid cells"},
        engine,
        None,
    )
    obj = json.loads(result)
    assert "error" in obj


# ---------------------------------------------------------------------------
# execute_tool — semantic_search
# ---------------------------------------------------------------------------

def test_execute_semantic_search_no_vector_store():
    engine = _engine_with_dataset()
    result = execute_tool("semantic_search", {"query": "place cells"}, engine, None)
    obj = json.loads(result)
    assert "error" in obj


def test_execute_semantic_search_with_store():
    import chromadb
    from neurodb.vector_store import VectorStore

    class _StubEmbedder:
        def embed(self, texts):
            return [[0.1, 0.2, 0.3, 0.4] for _ in texts]

    client = chromadb.EphemeralClient()
    vs = VectorStore(client=client, embedder=_StubEmbedder())
    vs.upsert_dataset("dandi", "000003", "Hippocampus Study", None, "icephys")

    engine = _engine_with_dataset()
    result = execute_tool("semantic_search", {"query": "hippocampus", "n_results": 3}, engine, vs)
    rows = json.loads(result)
    assert isinstance(rows, list)


# ---------------------------------------------------------------------------
# execute_tool — unknown tool
# ---------------------------------------------------------------------------

def test_execute_unknown_tool_returns_error():
    engine = _engine_with_dataset()
    result = execute_tool("nonexistent_tool", {}, engine, None)
    obj = json.loads(result)
    assert "error" in obj


# ---------------------------------------------------------------------------
# NeuroDbAgent loop
# ---------------------------------------------------------------------------

def test_agent_system_prompt_allows_rich_chat_formatting():
    agent = NeuroDbAgent(MagicMock(), _engine_with_dataset())

    prompt = agent._build_system_prompt()

    assert "readable Markdown" in prompt
    assert "bold emphasis" in prompt
    assert "simple Markdown tables" in prompt


def test_agent_end_turn_yields_text():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _response(
        "end_turn", [_text_block("There are 1 datasets.")]
    )

    agent = NeuroDbAgent(mock_client, engine)
    chunks = list(agent.chat("How many datasets?", []))
    assert "".join(chunks) == "There are 1 datasets."
    assert mock_client.messages.create.call_count == 1


def test_agent_tool_use_then_end_turn():
    engine = _engine_with_dataset()
    mock_client = MagicMock()

    first_response = _response("tool_use", [
        _tool_use_block("t1", "query_db", {"sql": "SELECT COUNT(*) FROM datasets_index"})
    ])
    second_response = _response("end_turn", [_text_block("Found 1 dataset.")])
    mock_client.messages.create.side_effect = [first_response, second_response]

    agent = NeuroDbAgent(mock_client, engine)
    chunks = list(agent.chat("Count datasets", []))
    assert "".join(chunks) == "Found 1 dataset."
    assert mock_client.messages.create.call_count == 2


def test_agent_passes_history_to_api():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _response("end_turn", [_text_block("ok")])

    history = [
        {"role": "user", "content": "hello"},
        {"role": "assistant", "content": [_text_block("hi")]},
    ]
    agent = NeuroDbAgent(mock_client, engine)
    list(agent.chat("next question", history))

    call_messages = mock_client.messages.create.call_args[1]["messages"]
    # history is [user, assistant] + the new user message at index 2
    assert call_messages[0]["role"] == "user"
    assert call_messages[0]["content"] == "hello"
    assert call_messages[2]["content"] == "next question"


def test_agent_tool_use_blocks_preserved_in_messages():
    """Tool-use and tool-result blocks must be appended to the caller's messages list
    so subsequent turns see the full conversation — not just the extracted text."""
    engine = _engine_with_dataset()
    mock_client = MagicMock()

    first_response = _response("tool_use", [
        _tool_use_block("t1", "query_db", {"sql": "SELECT COUNT(*) FROM datasets_index"})
    ])
    second_response = _response("end_turn", [_text_block("Found 1 dataset.")])
    mock_client.messages.create.side_effect = [first_response, second_response]

    agent = NeuroDbAgent(mock_client, engine)
    messages = []
    list(agent.chat("Count datasets", messages))

    # messages must contain all four turns: user, assistant(tool_use), user(tool_result), assistant(text)
    assert len(messages) == 4
    assert messages[0] == {"role": "user", "content": "Count datasets"}
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert isinstance(messages[2]["content"], list)
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[3]["role"] == "assistant"


def test_agent_max_turns_guard():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _response("tool_use", [
        _tool_use_block("t1", "query_db", {"sql": "SELECT 1"})
    ])

    agent = NeuroDbAgent(mock_client, engine)
    chunks = list(agent.chat("loop forever", []))
    assert any("maximum" in c.lower() for c in chunks)


def test_agent_max_turns_rolls_back_partial_api_history():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _response("tool_use", [
        _tool_use_block("t1", "query_db", {"sql": "SELECT 1"})
    ])

    agent = NeuroDbAgent(mock_client, engine, max_tool_iterations=1)
    messages = []
    chunks = list(agent.chat("loop forever", messages))

    assert any("maximum" in c.lower() for c in chunks)
    assert messages == []


def test_agent_chat_stream_yields_text_deltas_and_done():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    final_message = _response("end_turn", [_text_block("There are 1 datasets.")])
    mock_client.messages.stream.return_value = _Stream(
        [_text_delta_event("There are "), _text_delta_event("1 datasets.")],
        final_message,
    )

    agent = NeuroDbAgent(mock_client, engine)
    messages = []
    events = list(agent.chat_stream("How many datasets?", messages))

    assert events[0] == {"type": "text_delta", "text": "There are "}
    assert events[1] == {"type": "text_delta", "text": "1 datasets."}
    assert events[-1]["type"] == "done"
    assert events[-1]["text"] == "There are 1 datasets."
    assert messages[0] == {"role": "user", "content": "How many datasets?"}
    assert messages[1]["role"] == "assistant"


def test_agent_chat_stream_surfaces_tool_activity_and_preserves_messages():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = [
        _Stream([], _response("tool_use", [
            _tool_use_block("t1", "query_db", {"sql": "SELECT COUNT(*) FROM datasets_index"})
        ])),
        _Stream([_text_delta_event("Found 1 dataset.")], _response("end_turn", [_text_block("Found 1 dataset.")])),
    ]

    agent = NeuroDbAgent(mock_client, engine)
    messages = []
    events = list(agent.chat_stream("Count datasets", messages))

    assert any(event["type"] == "tool_start" for event in events)
    tool_start = next(event for event in events if event["type"] == "tool_start")
    assert tool_start["iteration"] == 1
    assert tool_start["limit"] == 10
    assert any(event["type"] == "tool_result" for event in events)
    assert events[-1]["type"] == "done"
    assert len(messages) == 4
    assert messages[0] == {"role": "user", "content": "Count datasets"}
    assert messages[1]["role"] == "assistant"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"][0]["type"] == "tool_result"
    assert messages[3]["role"] == "assistant"


def test_agent_chat_stream_max_turns_rolls_back_partial_api_history():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.stream.return_value = _Stream([], _response("tool_use", [
        _tool_use_block("t1", "query_db", {"sql": "SELECT 1"})
    ]))

    agent = NeuroDbAgent(mock_client, engine, max_tool_iterations=1)
    messages = []
    events = list(agent.chat_stream("loop forever", messages))

    assert events[-1]["type"] == "error"
    assert "maximum tool iterations" in events[-1]["text"]
    assert messages == []


def test_chat_stream_yields_token_limit_error_when_max_tokens_fires():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.stream.side_effect = [
        _Stream([], _response("tool_use", [
            _tool_use_block("t1", "query_db", {"sql": "SELECT 1"})
        ])),
        _Stream([], _response("max_tokens", [
            _tool_use_block("t2", "query_db", {"sql": "SELECT 2"})
        ])),
    ]

    agent = NeuroDbAgent(mock_client, engine)
    messages = []
    events = list(agent.chat_stream("test", messages))

    assert events[-1]["type"] == "error"
    assert "token" in events[-1]["text"].lower()
    assert "maximum tool iterations" not in events[-1]["text"]
    assert messages == []


def test_chat_yields_token_limit_error_when_max_tokens_fires():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.side_effect = [
        _response("tool_use", [_tool_use_block("t1", "query_db", {"sql": "SELECT 1"})]),
        _response("max_tokens", [_tool_use_block("t2", "query_db", {"sql": "SELECT 2"})]),
    ]

    agent = NeuroDbAgent(mock_client, engine)
    messages = []
    chunks = list(agent.chat("test", messages))

    assert any("token" in c.lower() for c in chunks)
    assert not any("maximum tool iterations" in c for c in chunks)
    assert messages == []


def test_agent_uses_max_tokens_constructor_param_in_stream_calls():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    final_message = _response("end_turn", [_text_block("ok")])
    mock_client.messages.stream.return_value = _Stream([], final_message)

    agent = NeuroDbAgent(mock_client, engine, max_tokens=4096)
    list(agent.chat_stream("test", []))

    assert mock_client.messages.stream.call_args[1]["max_tokens"] == 4096


def test_agent_uses_max_tokens_constructor_param_in_non_stream_calls():
    engine = _engine_with_dataset()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = _response("end_turn", [_text_block("ok")])

    agent = NeuroDbAgent(mock_client, engine, max_tokens=4096)
    list(agent.chat("test", []))

    assert mock_client.messages.create.call_args[1]["max_tokens"] == 4096


# ---------------------------------------------------------------------------
# Per-agent model env vars (Phase 1.1)
# ---------------------------------------------------------------------------

def test_neurodb_agent_default_model_is_sonnet():
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_AGENT_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        import neurodb.agents.db_agent as mod
        importlib.reload(mod)
        assert mod._MODEL == "claude-sonnet-4-6"
    importlib.reload(mod)


def test_neurodb_agent_reads_neurodb_agent_model_env_var():
    with patch.dict(os.environ, {"NEURODB_AGENT_MODEL": "claude-haiku-4-5"}, clear=False):
        import neurodb.agents.db_agent as mod
        reloaded = importlib.reload(mod)
        assert reloaded._MODEL == "claude-haiku-4-5"
    # Reload back to normal state so other tests are not affected
    importlib.reload(mod)


def test_neurotutoragent_default_model_is_sonnet():
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_AGENT_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        import neurodb.agents.tutor_agent as mod
        importlib.reload(mod)
        assert mod._MODEL == "claude-sonnet-4-6"
    importlib.reload(mod)


def test_neurotutoragent_reads_neurodb_agent_model_env_var():
    with patch.dict(os.environ, {"NEURODB_AGENT_MODEL": "claude-haiku-4-5"}, clear=False):
        import neurodb.agents.tutor_agent as mod
        reloaded = importlib.reload(mod)
        assert reloaded._MODEL == "claude-haiku-4-5"
    importlib.reload(mod)
