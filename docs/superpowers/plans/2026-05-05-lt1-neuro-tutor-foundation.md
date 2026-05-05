# LT-1 Neuro-Tutor Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stand up the `BaseAgent` architecture, migrate `NeuroDbAgent`, introduce `NeuroTutorAgent` with a persistent knowledge library, replace session ceremony with auto-session, and deliver the Knowledge Library UI page.

**Architecture:** All agents inherit a `BaseAgent` abstract class that owns the conversation loop, checkpoint/rollback, and streaming protocol. Subclasses implement three methods: `_get_active_tools()`, `_build_system_prompt()`, `_execute_tool_block()`. `NeuroTutorAgent` wraps a `KnowledgeLibraryStore` (ChromaDB `knowledge_library` collection) and a `KnowledgeSource` SQLite table for structured metadata and status tracking. Auto-session replaces the explicit Start/End buttons: a session begins silently on the first message, and summarizes on Clear (if ≥ 3 user turns).

**Tech Stack:** Python, Anthropic SDK (claude-opus-4-7), SQLAlchemy ORM, ChromaDB persistent client, Streamlit, pytest + monkeypatch.

---

## File Map

| Action | Path | Purpose |
|--------|------|---------|
| Create | `src/neurodb/agents/__init__.py` | Package marker |
| Create | `src/neurodb/agents/base.py` | `BaseAgent` abstract class — chat loop, rollback, streaming |
| Create | `src/neurodb/agents/db_agent.py` | `NeuroDbAgent` (migrated from `agent.py`); modes `local_db` / `external_db` |
| Modify | `src/neurodb/agent.py` | Temporary compatibility shim for legacy imports; removed after LT-1 manual test passes |
| Modify | `src/neurodb/schema.py` | Add `KnowledgeSource` and `ChatSession` tables |
| Create | `src/neurodb/knowledge_store.py` | `KnowledgeLibraryStore` — ChromaDB `knowledge_library` wrapper |
| Create | `src/neurodb/agents/tutor_agent.py` | `NeuroTutorAgent` with `queue_source`, `search_knowledge_library`, `search_literature` |
| Modify | `src/neurodb/session_manager.py` | Add `get_context_for_topic()`; `end_session` returns summary str |
| Modify | `src/neurodb/ui/pages/chat.py` | Remove Start/End session; 3-option mode toggle; auto-session; re-init agent on mode switch |
| Modify | `src/neurodb/ui/app.py` | Init `KnowledgeLibraryStore`; add Knowledge Library tab |
| Create | `src/neurodb/ui/pages/knowledge_library.py` | Knowledge Library page: Pending queue + Library browser |
| Create | `docs/testsPlans/manualTestPlan_agent_lt1.md` | Manual phase-gate test plan for LT-1 |
| Create | `tests/unit/test_base_agent.py` | BaseAgent contract tests |
| Modify | `tests/unit/test_agent.py` | Update imports: `neurodb.agent` → `neurodb.agents.db_agent` |
| Modify | `tests/unit/test_agent_model_name.py` | Update imports and module reload target |
| Modify | `tests/unit/test_agent_recovery.py` | Update imports |
| Modify | `tests/integration/test_agent_modes.py` | Update imports; rename `learning` → `local_db`, `discovery` → `external_db` |
| Create | `tests/unit/test_agent_compat.py` | Legacy `neurodb.agent` import shim test |
| Create | `tests/unit/test_knowledge_schema.py` | KnowledgeSource + ChatSession table tests |
| Create | `tests/unit/test_knowledge_store.py` | KnowledgeLibraryStore add/search round-trip |
| Create | `tests/unit/test_tutor_agent.py` | NeuroTutorAgent instantiation, tool list, `queue_source` dedup |
| Create | `tests/unit/test_auto_session.py` | Auto-start trigger; auto-summarize threshold; ChatSession row |
| Modify | `tests/unit/test_chat_ui.py` | Remove session_active tests; update to auto-session signature |
| Modify | `tests/unit/test_chat_clear_button.py` | Verify structural tests still pass (likely no changes needed) |
| Create | `tests/unit/test_knowledge_library_page.py` | Structural tests for Knowledge Library page |

---

## Task 0: Manual Test Planning Gate

Manual test planning is required before implementation because LT-1 changes user-visible chat, session, mode, and Knowledge Library workflows.

**Files:**
- Create: `docs/testsPlans/manualTestPlan_agent_lt1.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Create the LT-1 manual test plan**

The manual plan must cover:
- Streamlit startup against a disposable LT-1 database
- Local DB mode behavior
- External DB mode behavior
- Neuro-Tutor source queuing
- Knowledge Library approve/reject flow
- Auto-session Clear behavior below and above the three-user-turn threshold
- Mode switching persistence
- Post-manual-test compatibility-shim cleanup

- [ ] **Step 2: Sync projectStatus.md**

Update `docs/projectStatus.md`:
- Add the LT-1 manual test plan to Key References
- Set Next to LT-1 implementation gate
- Keep LT-1 status as plan/manual-test review pending until the user approves implementation

- [ ] **Step 3: Review gate**

Expected: user has reviewed the implementation plan and manual test plan before Task 1 starts.

---

## Task 1: BaseAgent Abstract Class

**Files:**
- Create: `src/neurodb/agents/__init__.py`
- Create: `src/neurodb/agents/base.py`
- Create: `tests/unit/test_base_agent.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_base_agent.py
import pytest
from unittest.mock import MagicMock
from neurodb.agents.base import BaseAgent


class _ConcreteAgent(BaseAgent):
    def _get_active_tools(self):
        return []

    def _build_system_prompt(self):
        return "You are a test agent."

    def _execute_tool_block(self, block):
        return '{"ok": true}'


def _make_concrete_agent():
    return _ConcreteAgent(
        client=MagicMock(),
        engine=MagicMock(),
        vector_store=None,
        model="claude-opus-4-7",
        prior_context="",
    )


def test_base_agent_cannot_be_instantiated_directly():
    with pytest.raises(TypeError):
        BaseAgent(MagicMock(), MagicMock(), None, "model", "")


def test_concrete_subclass_instantiates():
    agent = _make_concrete_agent()
    assert agent is not None


def test_concrete_subclass_has_chat_method():
    agent = _make_concrete_agent()
    assert callable(agent.chat)


def test_concrete_subclass_has_chat_stream_method():
    agent = _make_concrete_agent()
    assert callable(agent.chat_stream)


def test_chat_rollback_on_exception():
    """If _execute_tool_block raises, messages must be rolled back."""
    from types import SimpleNamespace

    agent = _make_concrete_agent()
    tool_block = SimpleNamespace(type="tool_use", id="t1", name="test_tool", input={})
    mock_response = SimpleNamespace(stop_reason="tool_use", content=[tool_block])
    agent._client.messages.create.return_value = mock_response

    messages = []
    import unittest.mock as mock
    with mock.patch.object(agent, "_execute_tool_block", side_effect=RuntimeError("fail")):
        with pytest.raises(RuntimeError):
            list(agent.chat("test", messages))

    assert len(messages) == 0


def test_chat_yields_text_on_end_turn():
    from types import SimpleNamespace

    agent = _make_concrete_agent()
    text_block = SimpleNamespace(type="text", text="Hello from agent")
    mock_response = SimpleNamespace(stop_reason="end_turn", content=[text_block])
    agent._client.messages.create.return_value = mock_response

    chunks = list(agent.chat("hi", []))
    assert "".join(chunks) == "Hello from agent"
```

- [ ] **Step 2: Run test to verify it fails**

```
cd /home/oldha/projects/neuroDb
uv run pytest tests/unit/test_base_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.agents'`

- [ ] **Step 3: Create the agents package and BaseAgent**

Create `src/neurodb/agents/__init__.py` (empty):
```python
```

Create `src/neurodb/agents/base.py`:
```python
"""Abstract base class for all NeuroDb agents."""
import os
from abc import ABC, abstractmethod
from collections.abc import Generator, Iterable

_DEFAULT_MODEL = "claude-opus-4-7"
_MAX_TURNS = 10


class BaseAgent(ABC):
    def __init__(
        self,
        client,
        engine,
        vector_store,
        model: str = _DEFAULT_MODEL,
        prior_context: str = "",
    ) -> None:
        self._client = client
        self._engine = engine
        self._vector_store = vector_store
        self._model = model
        self.prior_context = prior_context

    @abstractmethod
    def _get_active_tools(self) -> list[dict]: ...

    @abstractmethod
    def _build_system_prompt(self) -> str: ...

    @abstractmethod
    def _execute_tool_block(self, block) -> str: ...

    def chat(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        """Run one user turn with checkpoint/rollback. Mutates messages in place."""
        checkpoint = len(messages)
        try:
            yield from self._chat_inner(user_message, messages)
        except Exception:
            del messages[checkpoint:]
            raise

    def _chat_inner(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()
        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            response = self._client.messages.create(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            )
            messages.append({"role": "assistant", "content": response.content})

            if response.stop_reason == "end_turn":
                for block in response.content:
                    if block.type == "text":
                        yield block.text
                return

            if response.stop_reason == "tool_use":
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result_text = self._execute_tool_block(block)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": [{"type": "text", "text": result_text}],
                        })
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield "[Agent reached maximum tool iterations without a final answer]"

    def chat_stream(self, user_message: str, messages: list[dict]) -> Iterable[dict]:
        """Run one user turn with streaming output and visible tool activity."""
        active_tools = self._get_active_tools()
        system = self._build_system_prompt()
        messages.append({"role": "user", "content": user_message})

        for _ in range(_MAX_TURNS):
            with self._client.messages.stream(
                model=self._model,
                max_tokens=2048,
                system=system,
                tools=active_tools,
                messages=messages,
            ) as stream:
                for event in stream:
                    if (
                        event.type == "content_block_delta"
                        and event.delta.type == "text_delta"
                    ):
                        yield {"type": "text_delta", "text": event.delta.text}
                final_message = stream.get_final_message()

            messages.append({"role": "assistant", "content": final_message.content})

            if final_message.stop_reason == "end_turn":
                text_blocks = [
                    block.text
                    for block in final_message.content
                    if block.type == "text"
                ]
                yield {
                    "type": "done",
                    "text": "".join(text_blocks),
                    "stop_reason": final_message.stop_reason,
                }
                return

            if final_message.stop_reason == "tool_use":
                tool_results = []
                for block in final_message.content:
                    if block.type != "tool_use":
                        continue
                    yield {
                        "type": "tool_start",
                        "tool_name": block.name,
                        "tool_input": block.input,
                    }
                    result_text = self._execute_tool_block(block)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [{"type": "text", "text": result_text}],
                    })
                    yield {
                        "type": "tool_result",
                        "tool_name": block.name,
                        "result": result_text,
                    }
                messages.append({"role": "user", "content": tool_results})
                continue

            break

        yield {
            "type": "error",
            "text": "[Agent reached maximum tool iterations without a final answer]",
        }
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_base_agent.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/__init__.py src/neurodb/agents/base.py tests/unit/test_base_agent.py
git commit -m "feat(agents): add BaseAgent abstract class with chat loop and rollback"
```

---

## Task 2: NeuroDbAgent Migration

Rename `NeuroAgent` → `NeuroDbAgent`; mode values `"learning"` → `"local_db"` and `"discovery"` → `"external_db"`; inherit from `BaseAgent`; update all first-party import sites. Keep `src/neurodb/agent.py` as a temporary compatibility shim during LT-1 to avoid breaking ad hoc scripts or older local workflows. The shim is removed only after LT-1 passes manual test.

**Files:**
- Create: `src/neurodb/agents/db_agent.py`
- Modify: `tests/unit/test_agent.py` — update imports, rename class references
- Modify: `tests/unit/test_agent_model_name.py` — update imports and reload target
- Modify: `tests/unit/test_agent_recovery.py` — update imports
- Modify: `tests/integration/test_agent_modes.py` — update imports and mode strings
- Modify: `src/neurodb/agent.py` — compatibility shim
- Create: `tests/unit/test_agent_compat.py` — shim behavior test

- [ ] **Step 1: Write failing tests (updated test files)**

Update `tests/unit/test_agent.py` — change all occurrences of `neurodb.agent` to `neurodb.agents.db_agent` and `NeuroAgent` to `NeuroDbAgent`:

```python
# tests/unit/test_agent.py  — top imports (replace existing)
from neurodb.agents.db_agent import TOOLS, NeuroDbAgent, execute_tool
```

Replace every `NeuroAgent(` with `NeuroDbAgent(` throughout the file. The test bodies are otherwise unchanged.

Update `tests/unit/test_agent_model_name.py`:
```python
import os
from unittest.mock import MagicMock, patch


def test_agent_uses_neurodb_model_env_var():
    with patch.dict(os.environ, {"NEURODB_MODEL": "claude-test-model"}):
        from importlib import reload
        import neurodb.agents.db_agent
        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent
        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == "claude-test-model"


def test_agent_falls_back_to_default_model():
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import neurodb.agents.db_agent
        reload(neurodb.agents.db_agent)
        from neurodb.agents.db_agent import NeuroDbAgent, _DEFAULT_MODEL
        a = NeuroDbAgent(client=MagicMock(), engine=MagicMock(), vector_store=MagicMock())
        assert a._model == _DEFAULT_MODEL
```

Update `tests/unit/test_agent_recovery.py`:
```python
import pytest
from unittest.mock import MagicMock, patch

from neurodb.agents.db_agent import NeuroDbAgent


def _make_agent():
    return NeuroDbAgent(
        client=MagicMock(),
        engine=MagicMock(),
        vector_store=MagicMock(),
    )


def test_messages_rolled_back_on_tool_execution_exception():
    agent = _make_agent()

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tu_001"
    tool_use_block.name = "list_datasets"
    tool_use_block.input = {}

    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    mock_response.content = [tool_use_block]

    agent._client.messages.create.return_value = mock_response

    messages = []
    with patch.object(agent, "_execute_tool_block", side_effect=RuntimeError("tool failed")):
        with pytest.raises(RuntimeError, match="tool failed"):
            list(agent.chat("test", messages))

    assert len(messages) == 0


def test_messages_unchanged_before_any_api_call_on_exception():
    agent = _make_agent()
    agent._client.messages.create.side_effect = RuntimeError("network error")

    messages = []
    with pytest.raises(RuntimeError, match="network error"):
        list(agent.chat("test", messages))

    assert len(messages) == 0
```

Update `tests/integration/test_agent_modes.py`:
```python
from unittest.mock import MagicMock

from sqlalchemy import create_engine

from neurodb.agents.db_agent import NeuroDbAgent
from neurodb.db import init_db, seed_learning_sources
from neurodb.discovery_tools import DISCOVERY_TOOLS


def _make_agent(mode="local_db"):
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    client = MagicMock()
    agent = NeuroDbAgent(client, engine, mode=mode)
    return agent, client


def test_local_db_mode_passes_only_local_tools():
    agent, client = _make_agent(mode="local_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("what datasets do you have?", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {tool["name"] for tool in call_kwargs["tools"]}
    discovery_names = {tool["name"] for tool in DISCOVERY_TOOLS}
    assert tool_names.isdisjoint(discovery_names), "Discovery tools leaked into local_db mode"
    assert "query_db" in tool_names


def test_external_db_mode_includes_discovery_tools():
    agent, client = _make_agent(mode="external_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("search for retinotopy datasets", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {tool["name"] for tool in call_kwargs["tools"]}
    assert "search_external" in tool_names
    assert "suggest_import" in tool_names
    assert "query_db" in tool_names


def test_chapter_context_injected_into_system_prompt():
    agent, client = _make_agent()
    agent.chapter_context = "Ch12 — Central Visual Pathways\nTopics: retinotopy, LGN"
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("tell me about V1", []))

    call_kwargs = client.messages.create.call_args[1]
    assert "Central Visual Pathways" in call_kwargs["system"]


def test_mode_can_be_changed_between_calls():
    agent, client = _make_agent(mode="local_db")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("first message", []))
    call1 = client.messages.create.call_args[1]
    assert "search_external" not in {tool["name"] for tool in call1["tools"]}

    agent.mode = "external_db"
    list(agent.chat("second message", []))
    call2 = client.messages.create.call_args[1]
    assert "search_external" in {tool["name"] for tool in call2["tools"]}
```

- [ ] **Step 2: Run tests to verify they fail**

```
uv run pytest tests/unit/test_agent.py tests/unit/test_agent_model_name.py tests/unit/test_agent_recovery.py tests/integration/test_agent_modes.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.agents.db_agent'`

- [ ] **Step 3: Create NeuroDbAgent**

Create `src/neurodb/agents/db_agent.py` by migrating and adapting `src/neurodb/agent.py`:

```python
"""NeuroDbAgent — local DB and external DB query agent."""
import json
import os

from sqlalchemy import Engine, text

from neurodb.agents.base import BaseAgent, _MAX_TURNS
from neurodb.db import get_session
from neurodb.study import list_tags, tag_dataset as _tag_dataset
from neurodb.vector_store import VectorStore

_DEFAULT_MODEL = "claude-opus-4-7"
_MODEL = os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)

TOOLS = [
    {
        "name": "query_db",
        "description": (
            "Execute a read-only SQL SELECT query against the NeuroDb database "
            "and return results as JSON. Use this to count datasets, list sources, "
            "or retrieve any structured information from the database."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "sql": {
                    "type": "string",
                    "description": "A SQL SELECT statement to execute.",
                }
            },
            "required": ["sql"],
        },
    },
    {
        "name": "semantic_search",
        "description": (
            "Search datasets and study notes by semantic similarity using vector embeddings. "
            "Use this for natural language queries like 'find datasets related to spatial navigation'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum number of results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_study_notes",
        "description": (
            "Retrieve study notes and concept tags from the database. "
            "Optionally filter by concept substring or data source."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "concept": {
                    "type": "string",
                    "description": "Filter by concept tag substring (optional).",
                },
                "source": {
                    "type": "string",
                    "description": "Filter by data source — dandi, openneuro, etc. (optional).",
                },
            },
        },
    },
    {
        "name": "tag_dataset",
        "description": (
            "Tag a dataset with a study concept, creating a study note in the database. "
            "The dataset must already be ingested."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Data source name (dandi, openneuro, etc.).",
                },
                "source_id": {
                    "type": "string",
                    "description": "Dataset ID within the source (e.g. 000003).",
                },
                "concept_tag": {
                    "type": "string",
                    "description": "Concept tag to apply.",
                },
                "section_ref": {
                    "type": "string",
                    "description": "Optional section reference (e.g. 'Augustine Ch13 p.312').",
                },
                "note_text": {
                    "type": "string",
                    "description": "Optional free-form note text.",
                },
            },
            "required": ["source", "source_id", "concept_tag"],
        },
    },
]

_SYSTEM_PROMPT = (
    "You are a helpful neuroscience research assistant with access to a local database "
    "of neuroscience datasets and study notes. "
    "When a question asks about specific datasets, records, study notes, or what is in the database, "
    "use your tools to retrieve data and ground your answer in real results. "
    "When a question is about general neuroscience knowledge or concepts (anatomy, physiology, theory), "
    "answer directly from your training knowledge — do not call tools to search for data that is unlikely to exist. "
    "Never fabricate dataset IDs, counts, or details — if something is not in the database, say so clearly."
)


def execute_tool(
    name: str,
    inputs: dict,
    engine: Engine,
    vector_store: VectorStore | None,
) -> str:
    """Dispatch a tool call and return the result as a JSON string."""
    if name == "query_db":
        return _run_query_db(inputs["sql"], engine)
    if name == "semantic_search":
        return _run_semantic_search(inputs["query"], inputs.get("n_results", 5), vector_store)
    if name == "get_study_notes":
        return _run_get_study_notes(inputs.get("concept"), inputs.get("source"), engine)
    if name == "tag_dataset":
        return _run_tag_dataset(
            inputs["source"],
            inputs["source_id"],
            inputs["concept_tag"],
            inputs.get("section_ref"),
            inputs.get("note_text"),
            engine,
            vector_store,
        )
    return json.dumps({"error": f"Unknown tool: {name}"})


def _execute_discovery_tool(name: str, inputs: dict, engine: Engine) -> str:
    from neurodb.discovery_tools import (
        run_search_external,
        run_suggest_import,
        run_suggest_learning_source,
        run_suggest_new_source,
    )

    if name == "search_external":
        return run_search_external(inputs["source"], inputs["query"], inputs.get("limit", 10))
    if name == "suggest_import":
        return run_suggest_import(
            inputs["source"],
            inputs["source_id"],
            inputs["title"],
            inputs["reason"],
            inputs.get("chapter_ref"),
            inputs.get("metadata", {}),
            engine,
        )
    if name == "suggest_learning_source":
        return run_suggest_learning_source(
            inputs["suggestion_type"],
            inputs["reference"],
            inputs["display_name"],
            inputs["reason"],
            engine,
        )
    if name == "suggest_new_source":
        return run_suggest_new_source(
            inputs["reference"],
            inputs["display_name"],
            inputs["reason"],
            engine,
        )
    return json.dumps({"error": f"Unknown discovery tool: {name}"})


def _run_query_db(sql: str, engine: Engine) -> str:
    if not sql.strip().lower().startswith("select"):
        return json.dumps({"error": "Only SELECT statements are allowed."})
    try:
        with engine.connect() as conn:
            result = conn.execute(text(sql))
            rows = [dict(zip(result.keys(), row)) for row in result]
        return json.dumps(rows)
    except Exception as exc:
        return json.dumps({"error": str(exc)})


def _run_semantic_search(query: str, n_results: int, vector_store: VectorStore | None) -> str:
    if vector_store is None:
        return json.dumps({"error": "Vector store not available."})
    results = vector_store.search(query, n_results=n_results)
    return json.dumps(results)


def _run_get_study_notes(concept: str | None, source: str | None, engine: Engine) -> str:
    with get_session(engine) as session:
        rows = list_tags(session, concept=concept, source=source)
    return json.dumps(rows)


def _run_tag_dataset(
    source: str,
    source_id: str,
    concept_tag: str,
    section_ref: str | None,
    note_text: str | None,
    engine: Engine,
    vector_store: VectorStore | None,
) -> str:
    with get_session(engine) as session:
        note = _tag_dataset(session, source, source_id, concept_tag, section_ref, note_text)
    if note is None:
        return json.dumps({"error": f"Dataset not found: {source}:{source_id}"})
    if vector_store is not None:
        from neurodb.embed_hooks import embed_note
        embed_note(vector_store, note.id, source, source_id, concept_tag, section_ref, note_text)
    return json.dumps({"success": True, "tag_id": note.id, "concept_tag": concept_tag})


class NeuroDbAgent(BaseAgent):
    """Agent for local DB queries and external dataset discovery."""

    def __init__(
        self,
        client,
        engine: Engine,
        vector_store: VectorStore | None = None,
        model: str = _MODEL,
        prior_context: str = "",
        mode: str = "local_db",
        chapter_context: str = "",
    ) -> None:
        super().__init__(client, engine, vector_store, model, prior_context)
        self.mode = mode
        self.chapter_context = chapter_context

    def _get_active_tools(self) -> list[dict]:
        from neurodb.discovery_tools import DISCOVERY_TOOLS
        active_tools = list(TOOLS)
        if self.mode == "external_db":
            active_tools.extend(DISCOVERY_TOOLS)
        return active_tools

    def _build_system_prompt(self) -> str:
        system = _SYSTEM_PROMPT
        if self.chapter_context:
            system = f"{system}\n\nCurrent reading context:\n{self.chapter_context}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.name in {
            "search_external",
            "suggest_import",
            "suggest_learning_source",
            "suggest_new_source",
        }:
            return _execute_discovery_tool(block.name, block.input, self._engine)
        return execute_tool(
            block.name, block.input, self._engine, self._vector_store
        )
```

- [ ] **Step 4: Run tests to verify they pass**

```
uv run pytest tests/unit/test_agent.py tests/unit/test_agent_model_name.py tests/unit/test_agent_recovery.py tests/integration/test_agent_modes.py -v
```

Expected: all tests PASS.

- [ ] **Step 5: Replace agent.py with a compatibility shim**

Replace `src/neurodb/agent.py` with:

```python
"""Compatibility shim for legacy neurodb.agent imports.

Remove this shim after LT-1 passes manual test.
"""
from neurodb.agents.db_agent import TOOLS, NeuroDbAgent, execute_tool

NeuroAgent = NeuroDbAgent

__all__ = ["NeuroAgent", "NeuroDbAgent", "TOOLS", "execute_tool"]
```

Create `tests/unit/test_agent_compat.py`:

```python
from neurodb.agent import NeuroAgent
from neurodb.agents.db_agent import NeuroDbAgent


def test_legacy_neuro_agent_import_aliases_neuro_db_agent():
    assert NeuroAgent is NeuroDbAgent
```

- [ ] **Step 6: Run compatibility and migration tests**

```bash
uv run pytest tests/unit/test_agent.py tests/unit/test_agent_model_name.py tests/unit/test_agent_recovery.py tests/unit/test_agent_compat.py tests/integration/test_agent_modes.py -v
```

Expected: all tests PASS. First-party runtime code should import `NeuroDbAgent` from `neurodb.agents.db_agent`; only the compatibility test should rely on `neurodb.agent`.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/db_agent.py src/neurodb/agent.py tests/unit/test_agent.py tests/unit/test_agent_model_name.py tests/unit/test_agent_recovery.py tests/unit/test_agent_compat.py tests/integration/test_agent_modes.py
git commit -m "feat(agents): migrate NeuroAgent to NeuroDbAgent in agents package"
```

---

## Task 3: Schema — KnowledgeSource and ChatSession

**Files:**
- Modify: `src/neurodb/schema.py`
- Create: `tests/unit/test_knowledge_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_knowledge_schema.py
import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session
from neurodb.schema import Base, KnowledgeSource, ChatSession


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_knowledge_sources_table_created():
    engine = _engine()
    insp = inspect(engine)
    assert "knowledge_sources" in insp.get_table_names()


def test_chat_sessions_table_created():
    engine = _engine()
    insp = inspect(engine)
    assert "chat_sessions" in insp.get_table_names()


def test_knowledge_source_doi_unique():
    engine = _engine()
    with Session(engine) as session:
        s1 = KnowledgeSource(
            title="Paper A",
            normalized_title="paper a",
            doi="10.1234/test",
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        )
        s2 = KnowledgeSource(
            title="Paper B",
            normalized_title="paper b",
            doi="10.1234/test",  # same DOI
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        )
        session.add(s1)
        session.commit()
        session.add(s2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


def test_knowledge_source_normalized_title_unique():
    engine = _engine()
    with Session(engine) as session:
        s1 = KnowledgeSource(
            title="Paper A",
            normalized_title="paper a",
            source_type="paper",
            topic_context="memory",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        )
        s2 = KnowledgeSource(
            title="paper a",
            normalized_title="paper a",  # same normalized title
            source_type="review",
            topic_context="hippocampus",
            status="pending",
            queued_at="2026-05-05T00:00:01",
        )
        session.add(s1)
        session.commit()
        session.add(s2)
        with pytest.raises(Exception):  # IntegrityError
            session.commit()


def test_chat_session_session_id_unique():
    engine = _engine()
    with Session(engine) as session:
        sid = "abc-123"
        r1 = ChatSession(
            session_id=sid,
            inferred_topic="memory",
            agent_mode="neuro_tutor",
            started_at="2026-05-05T00:00:00",
            message_count=3,
        )
        r2 = ChatSession(
            session_id=sid,  # duplicate
            inferred_topic="LTP",
            agent_mode="neuro_tutor",
            started_at="2026-05-05T00:01:00",
            message_count=4,
        )
        session.add(r1)
        session.commit()
        session.add(r2)
        with pytest.raises(Exception):
            session.commit()


def test_knowledge_source_default_fields():
    engine = _engine()
    with Session(engine) as session:
        ks = KnowledgeSource(
            title="Some Review",
            normalized_title="some review",
            source_type="review",
            topic_context="plasticity",
            status="pending",
            queued_at="2026-05-05T00:00:00",
        )
        session.add(ks)
        session.commit()
        assert ks.id is not None
        assert ks.doi is None
        assert ks.url is None
        assert ks.summary is None
        assert ks.chroma_id is None
        assert ks.reviewed_at is None
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_knowledge_schema.py -v
```

Expected: `ImportError: cannot import name 'KnowledgeSource' from 'neurodb.schema'`

- [ ] **Step 3: Add KnowledgeSource and ChatSession to schema.py**

Append to the end of `src/neurodb/schema.py`:

```python
class KnowledgeSource(Base):
    """Sources surfaced by NeuroTutorAgent, pending user curation."""
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("normalized_title", name="uq_knowledge_source_title"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("knowledge_sources_id_seq"), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(Text, nullable=True, unique=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    topic_context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    queued_at: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_id: Mapped[str | None] = mapped_column(String(64), nullable=True)


class ChatSession(Base):
    """Index of completed chat sessions. Populated by auto-summarize on Clear."""
    __tablename__ = "chat_sessions"

    id: Mapped[int] = mapped_column(Integer, Sequence("chat_sessions_id_seq"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    inferred_topic: Mapped[str] = mapped_column(Text, nullable=False)
    agent_mode: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_knowledge_schema.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full suite**

```
uv run pytest --tb=short -q
```

Expected: all existing tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_knowledge_schema.py
git commit -m "feat(schema): add KnowledgeSource and ChatSession tables"
```

---

## Task 4: KnowledgeLibraryStore

**Files:**
- Create: `src/neurodb/knowledge_store.py`
- Create: `tests/unit/test_knowledge_store.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_knowledge_store.py
import pytest
import chromadb
from neurodb.knowledge_store import KnowledgeLibraryStore


def _make_store() -> KnowledgeLibraryStore:
    client = chromadb.EphemeralClient()
    return KnowledgeLibraryStore(client=client)


def test_empty_store_search_returns_empty():
    store = _make_store()
    results = store.search("hippocampus", n=5)
    assert results == []


def test_add_summary_returns_chroma_id():
    store = _make_store()
    chroma_id = store.add_summary(
        source_id=1,
        title="LTP in CA1",
        doi="10.1234/ltp",
        topic_context="synaptic plasticity",
        summary="Long-term potentiation in hippocampal CA1 region...",
    )
    assert chroma_id is not None
    assert len(chroma_id) > 0


def test_add_and_search_returns_result():
    store = _make_store()
    store.add_summary(
        source_id=1,
        title="LTP in CA1",
        doi="10.1234/ltp",
        topic_context="synaptic plasticity",
        summary="Long-term potentiation in hippocampal CA1 region reinforces memory.",
    )
    results = store.search("hippocampus memory", n=5)
    assert len(results) == 1
    assert "hippocampal" in results[0]["document"]


def test_search_returns_metadata():
    store = _make_store()
    store.add_summary(
        source_id=42,
        title="Grid Cells",
        doi=None,
        topic_context="spatial navigation",
        summary="Grid cells in entorhinal cortex encode spatial position.",
    )
    results = store.search("entorhinal cortex", n=3)
    assert results[0]["metadata"]["source_id"] == 42
    assert results[0]["metadata"]["title"] == "Grid Cells"


def test_add_summary_idempotent_on_same_source_id():
    """Upserting the same source_id replaces the document rather than duplicating."""
    store = _make_store()
    store.add_summary(1, "Title", None, "context", "Summary v1")
    store.add_summary(1, "Title", None, "context", "Summary v2 updated")
    results = store.search("Summary", n=10)
    assert len(results) == 1
    assert "v2" in results[0]["document"]
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_knowledge_store.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.knowledge_store'`

- [ ] **Step 3: Implement KnowledgeLibraryStore**

Create `src/neurodb/knowledge_store.py`:

```python
"""KnowledgeLibraryStore — ChromaDB wrapper for curated knowledge source summaries."""
import chromadb

_COLLECTION_NAME = "knowledge_library"


class KnowledgeLibraryStore:
    """Append/search store for approved knowledge source summaries."""

    def __init__(
        self,
        path: str | None = None,
        client: chromadb.ClientAPI | None = None,
    ) -> None:
        if client is not None:
            self._client = client
        elif path is not None:
            self._client = chromadb.PersistentClient(path=path)
        else:
            raise ValueError("Either path or client must be provided")
        self._col = self._client.get_or_create_collection(
            name=_COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )

    def add_summary(
        self,
        source_id: int,
        title: str,
        doi: str | None,
        topic_context: str,
        summary: str,
    ) -> str:
        """Embed and store a summary. Returns the chroma_id. Upserts on same source_id."""
        chroma_id = f"ks:{source_id}"
        self._col.upsert(
            documents=[summary],
            ids=[chroma_id],
            metadatas=[{
                "source_id": source_id,
                "title": title,
                "doi": doi or "",
                "topic_context": topic_context,
            }],
        )
        return chroma_id

    def search(self, query: str, n: int = 5) -> list[dict]:
        """Semantic search of approved summaries. Returns [] when store is empty."""
        count = self._col.count()
        if count == 0:
            return []
        results = self._col.query(query_texts=[query], n_results=min(n, count))
        if not results["documents"]:
            return []
        return [
            {
                "id": doc_id,
                "document": results["documents"][0][i],
                "metadata": results["metadatas"][0][i],
                "distance": results["distances"][0][i],
            }
            for i, doc_id in enumerate(results["ids"][0])
        ]
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_knowledge_store.py -v
```

Expected: all 5 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/knowledge_store.py tests/unit/test_knowledge_store.py
git commit -m "feat(knowledge_store): add KnowledgeLibraryStore ChromaDB wrapper"
```

---

## Task 5: NeuroTutorAgent

**Files:**
- Create: `src/neurodb/agents/tutor_agent.py`
- Create: `tests/unit/test_tutor_agent.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_tutor_agent.py
import json
import pytest
from unittest.mock import MagicMock
from sqlalchemy import create_engine

import chromadb
from neurodb.schema import Base
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.agents.tutor_agent import NeuroTutorAgent


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def _make_tutor(engine=None):
    if engine is None:
        engine = _engine()
    ks_client = chromadb.EphemeralClient()
    knowledge_store = KnowledgeLibraryStore(client=ks_client)
    return NeuroTutorAgent(
        client=MagicMock(),
        engine=engine,
        vector_store=None,
        knowledge_store=knowledge_store,
    )


def test_tutor_agent_instantiates():
    agent = _make_tutor()
    assert agent is not None


def test_tutor_tool_list_contains_required_tools():
    agent = _make_tutor()
    tools = agent._get_active_tools()
    names = {t["name"] for t in tools}
    assert "search_knowledge_library" in names
    assert "queue_source" in names
    assert "search_literature" in names
    assert "query_db" in names


def test_tutor_tool_list_excludes_discovery_tools():
    agent = _make_tutor()
    tools = agent._get_active_tools()
    names = {t["name"] for t in tools}
    assert "search_external" not in names
    assert "suggest_import" not in names


def test_queue_source_inserts_pending_row():
    engine = _engine()
    agent = _make_tutor(engine)
    result = agent._execute_queue_source({
        "title": "Kandel Principles of Neural Science",
        "source_type": "textbook",
        "topic_context": "synaptic plasticity",
    })
    data = json.loads(result)
    assert data["status"] == "queued"


def test_queue_source_dedup_by_doi():
    engine = _engine()
    agent = _make_tutor(engine)
    params = {
        "title": "LTP Paper",
        "source_type": "paper",
        "topic_context": "LTP",
        "doi": "10.1234/ltp",
    }
    r1 = json.loads(agent._execute_queue_source(params))
    r2 = json.loads(agent._execute_queue_source(params))
    assert r1["status"] == "queued"
    assert r2["status"] == "already_exists"


def test_queue_source_dedup_by_normalized_title():
    engine = _engine()
    agent = _make_tutor(engine)
    r1 = json.loads(agent._execute_queue_source({
        "title": "Principles of Neural Science",
        "source_type": "textbook",
        "topic_context": "general",
    }))
    r2 = json.loads(agent._execute_queue_source({
        "title": "  Principles of Neural Science!  ",  # normalized = same
        "source_type": "textbook",
        "topic_context": "synaptic",
    }))
    assert r1["status"] == "queued"
    assert r2["status"] == "already_exists"


def test_search_knowledge_library_returns_empty_when_store_empty():
    agent = _make_tutor()
    result = agent._execute_search_knowledge_library({"query": "hippocampus"})
    data = json.loads(result)
    assert data == [] or (isinstance(data, dict) and "results" in data)


def test_system_prompt_contains_tutor_instructions():
    agent = _make_tutor()
    prompt = agent._build_system_prompt()
    assert "knowledge library" in prompt.lower() or "curated" in prompt.lower()
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_tutor_agent.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.agents.tutor_agent'`

- [ ] **Step 3: Implement NeuroTutorAgent**

Create `src/neurodb/agents/tutor_agent.py`:

```python
"""NeuroTutorAgent — neuroscience learning partner with knowledge library."""
import json
import os
import re
import unicodedata

from sqlalchemy import Engine

from neurodb.agents.base import BaseAgent, _DEFAULT_MODEL
from neurodb.agents.db_agent import TOOLS as _DB_TOOLS, execute_tool
from neurodb.knowledge_store import KnowledgeLibraryStore

_MODEL = os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)

_TUTOR_SYSTEM_PROMPT = (
    "You are a neuroscience learning partner with access to a curated knowledge library "
    "of approved source summaries, local study notes, and your own training knowledge. "
    "\n\n"
    "Before answering questions about specific topics, call search_knowledge_library to retrieve "
    "curated summaries relevant to the question. Ground factual claims in library results when available. "
    "\n\n"
    "Whenever you reference an external resource (paper, review, textbook, or website), call queue_source "
    "with its title, source type, and the current topic context. This never blocks your response — "
    "it runs silently in the background so the user can review and curate your citations. "
    "\n\n"
    "To discover new sources on a topic, call search_literature. It returns candidate papers and reviews "
    "from your training knowledge — call queue_source for any that are relevant so the user can approve them. "
    "\n\n"
    "Never fabricate paper titles, DOIs, or dataset IDs."
)

_TUTOR_TOOLS = [
    {
        "name": "search_knowledge_library",
        "description": (
            "Search curated knowledge summaries in the Knowledge Library using semantic similarity. "
            "Call this before answering topic questions to ground your response in approved sources."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Natural language search query.",
                },
                "n_results": {
                    "type": "integer",
                    "description": "Maximum results to return (default 5).",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Search for neuroscience papers, reviews, and resources on a topic. "
            "Returns candidate sources from training knowledge. "
            "Call queue_source for any results that are relevant to the current discussion."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Topic or research question to search for.",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "queue_source",
        "description": (
            "Queue a cited external resource for user review in the Knowledge Library. "
            "Call whenever you reference a paper, review, textbook, or website as a knowledge source. "
            "Returns immediately — never blocks your response."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {
                    "type": "string",
                    "description": "Title of the source.",
                },
                "source_type": {
                    "type": "string",
                    "description": "One of: paper, review, textbook, website.",
                },
                "topic_context": {
                    "type": "string",
                    "description": "What was being discussed when this source was cited.",
                },
                "doi": {
                    "type": "string",
                    "description": "DOI if known (optional).",
                },
                "url": {
                    "type": "string",
                    "description": "URL if applicable (optional).",
                },
            },
            "required": ["title", "source_type", "topic_context"],
        },
    },
]


def _normalize_title(title: str) -> str:
    """Lowercase, strip punctuation, collapse whitespace."""
    title = title.strip().lower()
    title = unicodedata.normalize("NFKD", title)
    title = re.sub(r"[^\w\s]", "", title)
    title = re.sub(r"\s+", " ", title).strip()
    return title


class NeuroTutorAgent(BaseAgent):
    """Neuroscience learning agent with knowledge library and source queuing."""

    def __init__(
        self,
        client,
        engine: Engine,
        vector_store=None,
        model: str = _MODEL,
        prior_context: str = "",
        knowledge_store: KnowledgeLibraryStore | None = None,
    ) -> None:
        super().__init__(client, engine, vector_store, model, prior_context)
        self._knowledge_store = knowledge_store

    def _get_active_tools(self) -> list[dict]:
        return list(_TUTOR_TOOLS) + list(_DB_TOOLS)

    def _build_system_prompt(self) -> str:
        system = _TUTOR_SYSTEM_PROMPT
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system

    def _execute_tool_block(self, block) -> str:
        if block.name == "queue_source":
            return self._execute_queue_source(block.input)
        if block.name == "search_knowledge_library":
            return self._execute_search_knowledge_library(block.input)
        if block.name == "search_literature":
            return self._execute_search_literature(block.input)
        return execute_tool(block.name, block.input, self._engine, self._vector_store)

    def _execute_queue_source(self, inputs: dict) -> str:
        from datetime import datetime, timezone
        from neurodb.schema import KnowledgeSource
        from neurodb.db import get_session

        title = inputs["title"]
        doi = inputs.get("doi")
        normalized = _normalize_title(title)

        with get_session(self._engine) as session:
            if doi:
                existing = session.query(KnowledgeSource).filter_by(doi=doi).first()
            else:
                existing = session.query(KnowledgeSource).filter_by(
                    normalized_title=normalized
                ).first()

            if existing:
                return json.dumps({"status": "already_exists", "id": existing.id})

            ks = KnowledgeSource(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=inputs.get("url"),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                status="pending",
                queued_at=datetime.now(timezone.utc).isoformat(),
            )
            session.add(ks)
            session.commit()
            return json.dumps({"status": "queued", "id": ks.id})

    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        query = inputs["query"]
        n = inputs.get("n_results", 5)
        results = self._knowledge_store.search(query, n=n)
        return json.dumps(results)

    def _execute_search_literature(self, inputs: dict) -> str:
        return json.dumps([])
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_tutor_agent.py -v
```

Expected: all 8 tests PASS.

- [ ] **Step 5: Run full suite**

```
uv run pytest --tb=short -q
```

Expected: all tests still pass.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py tests/unit/test_tutor_agent.py
git commit -m "feat(agents): add NeuroTutorAgent with queue_source, search_knowledge_library, search_literature"
```

---

## Task 6: SessionManager — Auto-Session Helpers

Add `get_context_for_topic()` (public wrapper for prior context retrieval without creating a session ID) and modify `end_session()` to return the generated summary string so callers can extract a preview for the `ChatSession` row.

**Files:**
- Modify: `src/neurodb/session_manager.py`
- Create: `tests/unit/test_auto_session.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_auto_session.py
import pytest
from unittest.mock import MagicMock, patch
import chromadb
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as OrmSession

from neurodb.schema import Base, ChatSession
from neurodb.session_manager import AgentContextStore, SessionManager, format_context


def _make_store() -> AgentContextStore:
    client = chromadb.EphemeralClient()
    return AgentContextStore(client=client)


def _make_manager(store=None):
    if store is None:
        store = _make_store()
    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[MagicMock(type="text", text="Topic: memory\nDate: 2026-05-05")]
    )
    return SessionManager(store, client=mock_client)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_get_context_for_topic_returns_empty_when_no_sessions():
    manager = _make_manager()
    context = manager.get_context_for_topic("hippocampus place cells")
    assert context == ""


def test_get_context_for_topic_returns_context_string_after_session():
    store = _make_store()
    store.add_summary("s1", "LTP in CA1\nConcepts covered: LTP", {"session_id": "s1"})
    manager = _make_manager(store)
    context = manager.get_context_for_topic("LTP hippocampus", threshold=1.0)
    assert "LTP" in context


def test_end_session_returns_summary_string():
    manager = _make_manager()
    conversation = [
        {"role": "user", "content": "What is LTP?"},
        {"role": "assistant", "content": [{"type": "text", "text": "LTP is..."}]},
        {"role": "user", "content": "How does it relate to memory?"},
    ]
    result = manager.end_session("session-abc", conversation)
    assert isinstance(result, str)
    assert len(result) > 0


def test_end_session_returns_none_on_empty_conversation():
    manager = _make_manager()
    result = manager.end_session("session-abc", [])
    assert result is None


def test_auto_summarize_threshold_counts_user_turns():
    """Threshold helper: user turns counted correctly."""
    api_messages = [
        {"role": "user", "content": "msg1"},
        {"role": "assistant", "content": "resp1"},
        {"role": "user", "content": "msg2"},
        {"role": "assistant", "content": "resp2"},
        {"role": "user", "content": "msg3"},
    ]
    user_turns = sum(1 for m in api_messages if m["role"] == "user")
    assert user_turns == 3


def test_chat_session_row_written_after_summarize():
    """After end_session, caller can write a ChatSession row using returned summary."""
    store = _make_store()
    manager = _make_manager(store)
    engine = _engine()

    api_messages = [
        {"role": "user", "content": "What is LTP?"},
        {"role": "assistant", "content": "LTP is long-term potentiation..."},
        {"role": "user", "content": "How does calcium help?"},
        {"role": "assistant", "content": "Calcium influx through NMDA receptors..."},
        {"role": "user", "content": "What are the stages of LTP?"},
    ]

    summary = manager.end_session("test-session-id", api_messages)
    assert summary is not None

    with OrmSession(engine) as session:
        row = ChatSession(
            session_id="test-session-id",
            inferred_topic=api_messages[0]["content"][:200],
            agent_mode="neuro_tutor",
            started_at="2026-05-05T10:00:00",
            ended_at="2026-05-05T10:30:00",
            summary_preview=(summary[:200] if summary else None),
            message_count=3,
        )
        session.add(row)
        session.commit()

    with OrmSession(engine) as session:
        rows = session.query(ChatSession).all()
        assert len(rows) == 1
        assert rows[0].session_id == "test-session-id"
        assert rows[0].message_count == 3
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_auto_session.py -v
```

Expected: `AttributeError: 'SessionManager' object has no attribute 'get_context_for_topic'`

- [ ] **Step 3: Update SessionManager**

In `src/neurodb/session_manager.py`, make two changes:

**Change 1:** Add `get_context_for_topic` method to `SessionManager`:

```python
def get_context_for_topic(
    self,
    topic: str,
    n: int = 3,
    threshold: float = _RELEVANCE_THRESHOLD,
) -> str:
    """Return formatted prior context for topic without creating a session ID."""
    if not topic:
        return ""
    summaries = self._store.get_relevant(topic, n=n, threshold=threshold)
    return format_context(summaries)
```

**Change 2:** Modify `end_session` to return the summary string (or None):

```python
def end_session(self, session_id: str, conversation: list[dict]) -> str | None:
    """Generate a session summary via Claude and store it. Returns summary text or None."""
    if not conversation or self._client is None:
        return None
    try:
        summary = self._generate_summary(conversation)
        self._store.add_summary(session_id, summary, {"session_id": session_id})
        return summary
    except Exception:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```
uv run pytest tests/unit/test_auto_session.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 5: Run full suite to confirm no regressions**

```
uv run pytest --tb=short -q
```

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/session_manager.py tests/unit/test_auto_session.py
git commit -m "feat(session): add get_context_for_topic; end_session returns summary for ChatSession row"
```

---

## Task 7: chat.py Overhaul + app.py Agent Wiring

Remove Start/End session buttons. Add 3-option mode toggle. Auto-session: starts silently on first message, summarizes on Clear (≥3 user turns). Re-init agent when mode changes. Update app.py to init `KnowledgeLibraryStore`.

**Files:**
- Modify: `src/neurodb/ui/pages/chat.py`
- Modify: `src/neurodb/ui/app.py`
- Modify: `tests/unit/test_chat_ui.py`

- [ ] **Step 1: Write updated test file**

Replace `tests/unit/test_chat_ui.py` with the following (removes session_active-dependent tests, updates signatures, adds structural tests):

```python
# tests/unit/test_chat_ui.py
import ast
import pathlib
from unittest.mock import MagicMock

from neurodb.ui.pages import chat


class _ContextRecorder:
    def __init__(self, events: list[tuple[str, str]]) -> None:
        self._events = events

    def __call__(self, name: str):
        return _ContextManager(self._events, name)


class _ContextManager:
    def __init__(self, events: list[tuple[str, str]], name: str) -> None:
        self._events = events
        self._name = name

    def __enter__(self):
        self._events.append(("enter", self._name))
        return self

    def __exit__(self, exc_type, exc, tb):
        self._events.append(("exit", self._name))
        return False


def test_render_chat_renders_transcript_container(monkeypatch):
    calls = []
    ctx = _ContextRecorder([])

    monkeypatch.setattr(chat.st, "session_state", {"chat_history": []})
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: calls.append(kwargs) or ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content: None)
    monkeypatch.setattr(chat.st, "divider", lambda: None)

    chat._render_chat(agent=MagicMock())

    assert calls[0] == {}


def test_render_chat_shows_placeholder_when_history_empty(monkeypatch):
    events: list[tuple[str, str]] = []
    ctx = _ContextRecorder(events)

    monkeypatch.setattr(chat.st, "session_state", {"chat_history": [], "api_messages": [], "pending_user_message": None})
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content: events.append(("markdown", content)))
    monkeypatch.setattr(chat.st, "divider", lambda: None)

    chat._render_chat(agent=MagicMock())

    assert ("enter", "chat_message:assistant") in events
    assert any("Ask about" in content or "Chat ready" in content for kind, content in events if kind == "markdown")


def test_render_chat_processes_pending_message_inside_transcript(monkeypatch):
    events: list[tuple[str, str]] = []
    ctx = _ContextRecorder(events)

    class _Placeholder:
        def markdown(self, content):
            events.append(("placeholder_markdown", content))

    class _Agent:
        def chat_stream(self, message, api_messages):
            assert message == "How many datasets?"
            yield {"type": "text_delta", "text": "There are "}
            yield {"type": "done", "text": "There are 5 datasets."}

    rerun_called = {"value": False}

    monkeypatch.setattr(
        chat.st,
        "session_state",
        {
            "chat_history": [{"role": "user", "content": "How many datasets?"}],
            "api_messages": [],
            "pending_user_message": "How many datasets?",
        },
    )
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content: events.append(("markdown", content)))
    monkeypatch.setattr(chat.st, "divider", lambda: None)
    monkeypatch.setattr(chat.st, "empty", lambda: _Placeholder())
    monkeypatch.setattr(chat.st, "rerun", lambda: rerun_called.__setitem__("value", True))

    chat._render_chat(agent=_Agent())

    assert rerun_called["value"] is True
    assert ("enter", "chat_message:user") in events
    assert ("enter", "chat_message:assistant") in events
    assert ("placeholder_markdown", "There are ") in events
    assert chat.st.session_state["chat_history"] == [
        {"role": "user", "content": "How many datasets?"},
        {"role": "assistant", "content": "There are 5 datasets."},
    ]
    assert chat.st.session_state["pending_user_message"] is None


def test_render_chat_enter_submits_send_not_clear(monkeypatch):
    rerun_called = {"value": False}
    submit_labels: list[str] = []
    clear_labels: list[str] = []

    class _Agent:
        def chat_stream(self, message, api_messages):
            assert message == "hi"
            yield {"type": "done", "text": "hello"}

    monkeypatch.setattr(
        chat.st,
        "session_state",
        {"chat_history": [], "api_messages": [], "pending_user_message": None},
    )
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: _ContextManager([], "container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: _ContextManager([], f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: _ContextManager([], f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [_ContextManager([], "column:composer"), _ContextManager([], "column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "hi")
    monkeypatch.setattr(
        chat.st,
        "form_submit_button",
        lambda label, **kwargs: submit_labels.append(label) or True,
    )
    monkeypatch.setattr(
        chat.st,
        "button",
        lambda label, **kwargs: clear_labels.append(label) or False,
    )
    monkeypatch.setattr(chat.st, "markdown", lambda content: None)
    monkeypatch.setattr(chat.st, "divider", lambda: None)
    monkeypatch.setattr(chat.st, "rerun", lambda: rerun_called.__setitem__("value", True))

    chat._render_chat(agent=_Agent())

    assert submit_labels == ["Send"]
    assert clear_labels == ["Clear"]
    assert rerun_called["value"] is True
    assert chat.st.session_state["chat_history"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert chat.st.session_state["pending_user_message"] is None


# --- Structural tests ---

def _chat_source() -> str:
    return pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()


def test_no_learning_or_discovery_mode_strings_in_chat():
    source = _chat_source()
    assert '"learning"' not in source, 'Mode string "learning" still present in chat.py'
    assert '"discovery"' not in source, 'Mode string "discovery" still present in chat.py'


def test_three_mode_options_present_in_chat():
    source = _chat_source()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source


def test_no_start_session_button_in_chat():
    source = _chat_source()
    assert "Start Session" not in source


def test_no_end_session_button_in_chat():
    source = _chat_source()
    assert "End Session" not in source
```

- [ ] **Step 2: Run updated tests to verify they fail**

```
uv run pytest tests/unit/test_chat_ui.py -v
```

Expected: structural tests fail (mode strings and buttons still present).

- [ ] **Step 3: Rewrite chat.py**

Replace `src/neurodb/ui/pages/chat.py` with:

```python
import os
import json
import uuid
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine, *, title: str = "", transcript_height: int = 420) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "api_messages" not in st.session_state:
        st.session_state["api_messages"] = _to_api_history(st.session_state["chat_history"])
    if "pending_user_message" not in st.session_state:
        st.session_state["pending_user_message"] = None

    if title:
        st.subheader(title)

    _init_agent(engine)
    _render_mode_and_chapter()

    agent = st.session_state.get("neuro_agent")
    if agent is None:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable the Research Assistant.")
    else:
        _render_chat(agent, transcript_height=transcript_height)


def _init_agent(engine: Engine) -> None:
    if "neuro_agent" in st.session_state:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    vs = st.session_state.get("vector_store")
    mode = st.session_state.get("agent_mode", "local_db")

    if mode == "neuro_tutor":
        from neurodb.agents.tutor_agent import NeuroTutorAgent
        knowledge_store = st.session_state.get("knowledge_store")
        agent = NeuroTutorAgent(
            client, engine,
            vector_store=vs,
            knowledge_store=knowledge_store,
        )
    else:
        from neurodb.agents.db_agent import NeuroDbAgent
        agent = NeuroDbAgent(
            client, engine,
            vector_store=vs,
            mode=mode,
            chapter_context=st.session_state.get("chapter_context", ""),
        )
    st.session_state["neuro_agent"] = agent


def _render_mode_and_chapter() -> None:
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    st.divider()

    _MODE_LABELS = {
        "local_db": "Local DB",
        "external_db": "External DB",
        "neuro_tutor": "Neuro-Tutor",
    }
    current_mode = st.session_state.get("agent_mode", "local_db")
    mode_options = list(_MODE_LABELS.keys())

    mode = st.radio(
        "Agent mode",
        options=mode_options,
        index=mode_options.index(current_mode) if current_mode in mode_options else 0,
        format_func=lambda m: _MODE_LABELS[m],
        horizontal=True,
    )
    if mode != current_mode:
        st.session_state["agent_mode"] = mode
        st.session_state.pop("neuro_agent", None)
        if mode == "neuro_tutor":
            st.session_state["chapter_context"] = ""
        st.rerun()

    if mode != "neuro_tutor":
        book_options = {key: value["display_name"] for key, value in REGISTRY.items()}
        st.selectbox(
            "Textbook",
            options=list(book_options.keys()),
            format_func=lambda key: book_options[key],
            key="selected_book_key",
        )

        chapter_input = st.text_input(
            "Current chapter (optional)",
            placeholder="e.g. Ch12",
            key="chapter_input_raw",
        )

        if chapter_input.strip():
            raw = chapter_input.strip().lstrip("Cc").lstrip("hH").strip()
            try:
                chapter_num = int(raw)
            except ValueError:
                chapter_num = None

            if chapter_num is not None:
                info = lookup_chapter(st.session_state["selected_book_key"], chapter_num)
                if info:
                    st.success(
                        f"**Ch{chapter_num} — {info['title']}**\nTopics: {', '.join(info['topics'])}"
                    )
                    context_str = f"Ch{chapter_num} — {info['title']}\nTopics: {', '.join(info['topics'])}"
                    if st.button("Set chapter context", key="set_chapter_btn"):
                        st.session_state["chapter_context"] = context_str
                        agent = st.session_state.get("neuro_agent")
                        if agent:
                            agent.chapter_context = context_str
                        st.rerun()
                else:
                    st.warning(f"Ch{chapter_num} not yet in registry for this book — context not set.")
            else:
                st.warning("Could not parse chapter number — context not set.")

        current_context = st.session_state.get("chapter_context", "")
        if current_context:
            st.caption(f"Active: {current_context[:60]}")
            if st.button("Clear chapter context", key="clear_chapter_btn"):
                st.session_state["chapter_context"] = ""
                agent = st.session_state.get("neuro_agent")
                if agent:
                    agent.chapter_context = ""
                st.rerun()

    st.divider()


def _auto_start_session(first_message: str) -> None:
    session_id = str(uuid.uuid4())
    st.session_state["session_id"] = session_id
    st.session_state["session_started_at"] = datetime.now(timezone.utc).isoformat()

    manager = st.session_state.get("session_manager")
    if manager:
        context = manager.get_context_for_topic(first_message)
    else:
        context = ""

    agent = st.session_state.get("neuro_agent")
    if agent and context:
        agent.prior_context = context


def _auto_summarize_if_sufficient() -> None:
    api_messages = st.session_state.get("api_messages", [])
    user_turns = sum(1 for m in api_messages if m["role"] == "user")
    if user_turns < 3:
        return

    session_id = st.session_state.get("session_id")
    if not session_id:
        return

    manager = st.session_state.get("session_manager")
    if not manager:
        return

    with st.spinner("Saving session summary…"):
        summary = manager.end_session(session_id, api_messages)

    engine = st.session_state.get("engine")
    if engine and summary:
        _write_chat_session_row(engine, session_id, api_messages, user_turns, summary)


def _write_chat_session_row(
    engine,
    session_id: str,
    api_messages: list[dict],
    user_turns: int,
    summary: str,
) -> None:
    from neurodb.schema import ChatSession
    from neurodb.db import get_session

    first_user = next(
        (m["content"] for m in api_messages if m["role"] == "user" and isinstance(m["content"], str)),
        "",
    )
    topic = first_user[:200] if first_user else "unknown"

    with get_session(engine) as session:
        row = ChatSession(
            session_id=session_id,
            inferred_topic=topic,
            agent_mode=st.session_state.get("agent_mode", "local_db"),
            started_at=st.session_state.get("session_started_at", datetime.now(timezone.utc).isoformat()),
            ended_at=datetime.now(timezone.utc).isoformat(),
            summary_preview=summary[:200] if summary else None,
            message_count=user_turns,
        )
        session.add(row)
        session.commit()


def _render_chat(agent, transcript_height: int = 420) -> None:
    transcript_container = st.container()
    with transcript_container:
        visible_messages = [
            msg for msg in st.session_state["chat_history"]
            if not msg.get("_system")
        ]
        if not visible_messages:
            with st.chat_message("assistant"):
                st.markdown("Chat ready. Ask about your datasets or a neuroscience topic.")

        for msg in st.session_state["chat_history"]:
            if msg.get("_system"):
                continue
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    composer_col, clear_col = st.columns([4, 1])
    with composer_col:
        with st.form("agent_form", clear_on_submit=True):
            user_input = st.text_input(
                "Message",
                placeholder="Ask about your datasets or a neuroscience topic…",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Send", width="stretch")
    with clear_col:
        clear_clicked = st.button(
            "Clear",
            width="stretch",
            disabled=not st.session_state["chat_history"],
        )

    if clear_clicked:
        _auto_summarize_if_sufficient()
        st.session_state["chat_history"] = []
        st.session_state["api_messages"] = []
        st.session_state["pending_user_message"] = None
        for key in ("session_id", "session_started_at"):
            st.session_state.pop(key, None)
        if agent:
            agent.prior_context = ""
        st.rerun()
    elif submitted and user_input.strip():
        message = user_input.strip()
        if "session_id" not in st.session_state:
            _auto_start_session(message)
        st.session_state["chat_history"].append({"role": "user", "content": message})
        if "api_messages" not in st.session_state:
            st.session_state["api_messages"] = _to_api_history(st.session_state["chat_history"][:-1])
        st.session_state["pending_user_message"] = message
        st.rerun()

    pending_message = st.session_state.get("pending_user_message")
    if pending_message and agent is not None:
        response_chunks: list[str] = []
        response_text = ""
        activity_log: list[str] = []
        with transcript_container:
            with st.chat_message("assistant"):
                text_placeholder = st.empty()
                activity_placeholder = st.empty()
                try:
                    for event in agent.chat_stream(pending_message, st.session_state["api_messages"]):
                        if event["type"] == "text_delta":
                            response_chunks.append(event["text"])
                            response_text = "".join(response_chunks)
                            text_placeholder.markdown(response_text)
                            continue

                        if event["type"] == "tool_start":
                            activity_log.append(_format_tool_start(event["tool_name"], event["tool_input"]))
                            activity_placeholder.markdown(_render_activity_log(activity_log))
                            continue

                        if event["type"] == "tool_result":
                            activity_log.append(_format_tool_result(event["tool_name"], event["result"]))
                            activity_placeholder.markdown(_render_activity_log(activity_log))
                            continue

                        if event["type"] == "done":
                            response_text = event["text"] or response_text
                            if response_text:
                                text_placeholder.markdown(response_text)
                            break

                        if event["type"] == "error":
                            error_note = event["text"]
                            if response_text:
                                response_text = f"{response_text}\n\n---\n*{error_note}*"
                            else:
                                response_text = error_note
                            text_placeholder.markdown(response_text)
                            break
                except Exception as exc:
                    response_text = f"Error during streaming response: {exc}"
                    text_placeholder.markdown(response_text)

                if not response_text:
                    response_text = "[No text response returned]"
                    text_placeholder.markdown(response_text)

        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.session_state["pending_user_message"] = None
        st.rerun()


def _to_api_history(history: list[dict]) -> list[dict]:
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and not msg.get("_system"):
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api


def _format_tool_start(tool_name: str, tool_input: dict) -> str:
    return f"Running `{tool_name}` with `{json.dumps(tool_input, sort_keys=True)}`"


def _format_tool_result(tool_name: str, result: str) -> str:
    preview = " ".join(result.split())
    if len(preview) > 140:
        preview = f"{preview[:137]}..."
    return f"Finished `{tool_name}`: `{preview}`"


def _render_activity_log(activity_log: list[str]) -> str:
    lines = ["**Agent activity**"]
    for line in activity_log[-6:]:
        lines.append(f"- {line}")
    return "\n".join(lines)
```

- [ ] **Step 4: Update app.py**

In `src/neurodb/ui/app.py`, make two changes:

**Change 1:** Add `KnowledgeLibraryStore` initialization (after the `session_manager` block):

```python
if "knowledge_store" not in st.session_state:
    from neurodb.knowledge_store import KnowledgeLibraryStore
    chroma_path = db_path.replace(".duckdb", "_chroma")
    st.session_state["knowledge_store"] = KnowledgeLibraryStore(path=chroma_path)
```

**Change 2:** Update the sidebar to use new mode default and auto-session status:

```python
with st.sidebar:
    st.caption(f"DB: `{db_path}`")
    st.caption("Workspace")
    st.markdown(
        "\n".join([
            f"- Mode: `{st.session_state.get('agent_mode', 'local_db')}`",
            f"- Session: `{'active' if 'session_id' in st.session_state else 'none'}`",
            f"- Chapter: `{st.session_state.get('chapter_context') or 'none'}`",
        ])
    )
```

- [ ] **Step 5: Run updated tests**

```
uv run pytest tests/unit/test_chat_ui.py tests/unit/test_chat_clear_button.py -v
```

Expected: all tests PASS.

- [ ] **Step 6: Run full suite**

```
uv run pytest --tb=short -q
```

Expected: all tests pass. Check especially `test_chat_chapter_context.py` — the chapter context controls are now only shown when mode is not `neuro_tutor`. If any chapter context tests fail because of the mode guard, update them to pass `mode="local_db"` or set `agent_mode` in the mock session_state.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/ui/pages/chat.py src/neurodb/ui/app.py tests/unit/test_chat_ui.py
git commit -m "feat(chat): auto-session, 3-option mode toggle, NeuroTutorAgent wiring; remove Start/End session"
```

---

## Task 8: Knowledge Library Page

**Files:**
- Create: `src/neurodb/ui/pages/knowledge_library.py`
- Modify: `src/neurodb/ui/app.py` (add tab)
- Create: `tests/unit/test_knowledge_library_page.py`

- [ ] **Step 1: Write the failing structural test**

```python
# tests/unit/test_knowledge_library_page.py
import ast
import pathlib
import pytest


def _source() -> str:
    path = pathlib.Path("src/neurodb/ui/pages/knowledge_library.py")
    assert path.exists(), "knowledge_library.py not yet created"
    return path.read_text()


def test_module_defines_render_function():
    source = _source()
    tree = ast.parse(source)
    func_names = [
        node.name for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert "render" in func_names, "knowledge_library.py must define a render(engine) function"


def test_render_references_pending_status():
    source = _source()
    assert "pending" in source


def test_render_references_approved_status():
    source = _source()
    assert "approved" in source


def test_render_references_reject():
    source = _source()
    assert "Reject" in source or "rejected" in source


def test_render_references_approve():
    source = _source()
    assert "Approve" in source


def test_render_imports_knowledge_source():
    source = _source()
    assert "KnowledgeSource" in source


def test_app_has_knowledge_library_tab():
    app_source = pathlib.Path("src/neurodb/ui/app.py").read_text()
    assert "Knowledge Library" in app_source or "knowledge_library" in app_source
```

- [ ] **Step 2: Run test to verify it fails**

```
uv run pytest tests/unit/test_knowledge_library_page.py -v
```

Expected: `AssertionError: knowledge_library.py not yet created`

- [ ] **Step 3: Create the Knowledge Library page**

Create `src/neurodb/ui/pages/knowledge_library.py`:

```python
"""Knowledge Library page — pending queue and approved source browser."""
import os

import streamlit as st
from sqlalchemy import Engine

_SUMMARY_PROMPT = """You are summarizing a neuroscience knowledge source for a curated learning library.

Source type: {source_type}
Title: {title}
Topic context (why it was cited): {topic_context}

Produce a concise structured summary in this format:
Title: {title}
Type: {source_type}
Key concepts: <comma-separated list of 3-6 key concepts>
Neuroscience relevance: <one sentence on what this contributes to neuroscience understanding>
Open questions: <one or two open questions this source raises, or "none">

Keep the entire summary under 300 words."""


def render(engine: Engine) -> None:
    st.subheader("Knowledge Library")

    tab_pending, tab_library = st.tabs(["Pending", "Library"])

    with tab_pending:
        _render_pending(engine)

    with tab_library:
        _render_library(engine)


def _render_pending(engine: Engine) -> None:
    from neurodb.schema import KnowledgeSource
    from neurodb.db import get_session

    with get_session(engine) as session:
        rows = (
            session.query(KnowledgeSource)
            .filter_by(status="pending")
            .order_by(KnowledgeSource.queued_at.desc())
            .all()
        )
        # Detach from session before rendering
        pending = [
            {
                "id": r.id,
                "title": r.title,
                "source_type": r.source_type,
                "topic_context": r.topic_context,
                "doi": r.doi,
                "url": r.url,
                "queued_at": r.queued_at,
            }
            for r in rows
        ]

    if not pending:
        st.caption("No sources pending review.")
        return

    for row in pending:
        with st.expander(f"{row['title']} — *{row['source_type']}*", expanded=False):
            st.markdown(f"**Topic context:** {row['topic_context']}")
            if row["doi"]:
                st.caption(f"DOI: {row['doi']}")
            if row["url"]:
                st.caption(f"URL: {row['url']}")
            st.caption(f"Queued: {row['queued_at'][:10]}")

            col_approve, col_reject = st.columns(2)
            with col_approve:
                if st.button("Approve", key=f"approve_{row['id']}"):
                    _approve_source(engine, row)
                    st.rerun()
            with col_reject:
                if st.button("Reject", key=f"reject_{row['id']}"):
                    _reject_source(engine, row["id"])
                    st.rerun()


def _approve_source(engine: Engine, row: dict) -> None:
    with st.spinner(f"Generating summary for '{row['title']}'…"):
        summary = _generate_summary(row)

    if summary is None:
        st.error("Could not generate summary — check ANTHROPIC_API_KEY.")
        return

    knowledge_store = st.session_state.get("knowledge_store")
    chroma_id = None
    if knowledge_store:
        chroma_id = knowledge_store.add_summary(
            source_id=row["id"],
            title=row["title"],
            doi=row["doi"],
            topic_context=row["topic_context"],
            summary=summary,
        )

    from datetime import datetime, timezone
    from neurodb.schema import KnowledgeSource
    from neurodb.db import get_session

    with get_session(engine) as session:
        ks = session.get(KnowledgeSource, row["id"])
        if ks:
            ks.status = "approved"
            ks.summary = summary
            ks.chroma_id = chroma_id
            ks.reviewed_at = datetime.now(timezone.utc).isoformat()
            session.commit()


def _reject_source(engine: Engine, source_id: int) -> None:
    from datetime import datetime, timezone
    from neurodb.schema import KnowledgeSource
    from neurodb.db import get_session

    with get_session(engine) as session:
        ks = session.get(KnowledgeSource, source_id)
        if ks:
            ks.status = "rejected"
            ks.reviewed_at = datetime.now(timezone.utc).isoformat()
            session.commit()


def _generate_summary(row: dict) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    model = os.environ.get("NEURODB_MODEL", "claude-opus-4-7")

    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        prompt = _SUMMARY_PROMPT.format(
            source_type=row["source_type"],
            title=row["title"],
            topic_context=row["topic_context"],
        )
        response = client.messages.create(
            model=model,
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text.strip()
    except Exception:
        pass
    return None


def _render_library(engine: Engine) -> None:
    from neurodb.schema import KnowledgeSource
    from neurodb.db import get_session

    with get_session(engine) as session:
        rows = (
            session.query(KnowledgeSource)
            .filter_by(status="approved")
            .order_by(KnowledgeSource.reviewed_at.desc())
            .all()
        )
        approved = [
            {
                "id": r.id,
                "title": r.title,
                "source_type": r.source_type,
                "topic_context": r.topic_context,
                "doi": r.doi,
                "reviewed_at": r.reviewed_at,
                "summary": r.summary,
            }
            for r in rows
        ]

    if not approved:
        st.caption("No approved sources yet. Approve sources from the Pending tab.")
        return

    for row in approved:
        with st.expander(f"{row['title']} — *{row['source_type']}*", expanded=False):
            st.markdown(f"**Topic context:** {row['topic_context']}")
            if row["doi"]:
                st.caption(f"DOI: {row['doi']}")
            if row["reviewed_at"]:
                st.caption(f"Approved: {row['reviewed_at'][:10]}")
            if row["summary"]:
                st.markdown(row["summary"])
```

- [ ] **Step 4: Add the Knowledge Library tab to app.py**

In `src/neurodb/ui/app.py`, update the tab line and add the new tab handler:

Change:
```python
tab_suggestions, tab_study, tab_datasets, tab_registry, tab_sql = st.tabs([
    "Suggestions",
    "Study Log",
    "Datasets",
    "Registry",
    "SQL",
])
```

To:
```python
tab_knowledge, tab_suggestions, tab_study, tab_datasets, tab_registry, tab_sql = st.tabs([
    "Knowledge Library",
    "Suggestions",
    "Study Log",
    "Datasets",
    "Registry",
    "SQL",
])
```

And add at the top of the `with col_workspace:` block:
```python
with tab_knowledge:
    from neurodb.ui.pages.knowledge_library import render
    render(engine)
```

- [ ] **Step 5: Run structural tests**

```
uv run pytest tests/unit/test_knowledge_library_page.py -v
```

Expected: all 7 tests PASS.

- [ ] **Step 6: Run full suite**

```
uv run pytest --tb=short -q
```

Expected: all tests pass.

- [ ] **Step 7: Update projectStatus.md**

Update `docs/projectStatus.md`:
- Phase LT-1 status: `In progress` → `Manual test ready`
- Test count: update to reflect new total
- Active focus: LT-1 manual verification and compatibility-shim cleanup
- Add `knowledge_library.py` to key references

- [ ] **Step 8: Final commit**

```bash
git add src/neurodb/ui/pages/knowledge_library.py src/neurodb/ui/app.py tests/unit/test_knowledge_library_page.py docs/projectStatus.md
git commit -m "feat(ui): add Knowledge Library page"
```

---

## Task 9: Post-Manual-Test Compatibility Cleanup Gate

This task starts only after the LT-1 manual test plan passes. The goal is to remove the temporary `neurodb.agent` compatibility shim once the user-visible LT-1 workflow has been verified.

**Files:**
- Delete: `src/neurodb/agent.py`
- Delete: `tests/unit/test_agent_compat.py`
- Modify: `docs/projectStatus.md`

- [x] **Step 1: Confirm LT-1 manual test passed**

Expected: the LT-1 manual test plan is complete and signed off by the user. Do not remove the shim before this gate.

- [x] **Step 2: Verify no first-party runtime imports still depend on the legacy module**

```bash
rg -n "from neurodb\\.agent|import neurodb\\.agent" src scripts tests
```

Expected: only `tests/unit/test_agent_compat.py` matches. If any runtime code matches, update it to import from `neurodb.agents.db_agent` before continuing.

- [x] **Step 3: Delete shim and shim test**

```bash
git rm src/neurodb/agent.py tests/unit/test_agent_compat.py
```

- [x] **Step 4: Run agent migration tests and full suite**

```bash
uv run pytest tests/unit/test_agent.py tests/unit/test_agent_model_name.py tests/unit/test_agent_recovery.py tests/integration/test_agent_modes.py -v
uv run pytest --tb=short -q
```

Expected: all tests PASS.

- [x] **Step 5: Update projectStatus.md**

Update `docs/projectStatus.md`:
- Phase LT-1 status: `Complete`
- Test count: update to reflect the final suite total
- Active focus: LT-2 planning, or none if pausing
- Reference cleanup: remove any reference to the temporary shim if one was added elsewhere

- [ ] **Step 6: Cleanup commit**

```bash
git add docs/projectStatus.md
git commit -m "refactor(agents): remove legacy neurodb.agent compatibility shim"
```

---

## Self-Review Checklist

After writing the plan, checking spec coverage:

**Spec section → Task coverage:**
- §1 BaseAgent, db_agent.py, tutor_agent.py → Tasks 1, 2, 5 ✓
- §2 Mode rename (local_db / external_db / neuro_tutor) → Task 2 (rename), Task 7 (UI) ✓
- §3 knowledge_sources table, knowledge_library ChromaDB, sessions table → Tasks 3, 4 ✓
- §4 queue_source dedup (DOI + normalized title) → Task 5 ✓
- §5 NeuroTutorAgent tools (search_knowledge_library, search_literature stub, queue_source, DB tools) → Task 5 ✓
- §6 Auto-session (start on first message, summarize on Clear ≥3 turns) → Tasks 6, 7 ✓
- §7 Mode toggle 3 options, Knowledge Library page (Pending + Library tabs) → Tasks 7, 8 ✓
- §8 Testing — manual gate in Task 0; automated categories addressed across Tasks 1-8 ✓
- §9 Out of scope — PubMed live API, Previous Topics UI, full-text indexing → not included ✓
- Compatibility-shim risk mitigation → Task 2 keeps shim, Task 9 removes it after LT-1 manual test passes ✓

**Placeholder scan:** None found.

**Type consistency:** `NeuroDbAgent`, `NeuroTutorAgent`, `KnowledgeLibraryStore`, `KnowledgeSource`, `ChatSession` — used consistently throughout.
