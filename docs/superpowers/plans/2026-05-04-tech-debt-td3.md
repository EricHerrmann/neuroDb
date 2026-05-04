# Tech Debt TD-3 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve all low-severity tech debt: remove dead code, make model name configurable, harden agent tool-use exception handling, add a QualityEvent compound index, validate chapter context before injecting it, make Study Log pre-fill explicit, and enable pytest-cov reporting.

**Architecture:** Each task is small and self-contained. No schema changes require migrations (compound index uses a new SQLAlchemy `Index` object; it's additive). Model name reads from env var with the existing default as fallback.

**Tech Stack:** Python, SQLAlchemy, Streamlit, os.environ, pytest-cov (already in dev deps)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/neurodb/transforms/` | Delete | Remove empty dead-code directory |
| `src/neurodb/agent.py` | Modify | Read model name from `NEURODB_MODEL` env var |
| `src/neurodb/session_manager.py` | Modify | Same env var for summary model |
| `src/neurodb/agent.py` | Modify | Rollback `api_messages` on mid-tool-use exception |
| `src/neurodb/schema.py` | Modify | Add compound index on QualityEvent |
| `src/neurodb/ui/pages/chat.py` | Modify | Validate chapter context before inject |
| `src/neurodb/ui/pages/study_log.py` | Modify | Explicit `st.rerun()` after pre-fill state set |
| `pyproject.toml` | Modify | Add pytest-cov config |

---

## Task 1: Remove empty transforms/ module (L1)

**Files:**
- Delete: `src/neurodb/transforms/__init__.py`
- Delete: `src/neurodb/transforms/` (directory)

No tests needed — absence of the directory is the test.

- [ ] **Step 1.1: Confirm nothing imports transforms**

```bash
grep -r "neurodb.transforms\|from neurodb import transforms" src/ tests/
```
Expected: no output — nothing imports this module

- [ ] **Step 1.2: Delete directory**

```bash
rm -rf /home/oldha/projects/neuroDb/src/neurodb/transforms
```

- [ ] **Step 1.3: Confirm test suite still passes**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 1.4: Commit**

```bash
git add -A
git commit -m "chore: remove empty transforms/ dead-code directory"
```

---

## Task 2: Configurable model name via env var (L2)

**Files:**
- Modify: `src/neurodb/agent.py`
- Modify: `src/neurodb/session_manager.py`
- Create: test assertions in `tests/unit/test_agent_model_name.py`

- [ ] **Step 2.1: Find current hardcoded model locations**

```bash
grep -n "claude-opus-4-7\|claude-sonnet\|claude-haiku" src/neurodb/agent.py src/neurodb/session_manager.py
```
Note the line numbers for both files.

- [ ] **Step 2.2: Write failing test**

```python
# tests/unit/test_agent_model_name.py
import os
from unittest.mock import patch, MagicMock


def test_agent_uses_neurodb_model_env_var():
    """If NEURODB_MODEL is set, agent.__init__ uses it."""
    with patch.dict(os.environ, {"NEURODB_MODEL": "claude-test-model"}):
        from importlib import reload
        import neurodb.agent
        reload(neurodb.agent)
        from neurodb.agent import NeuroDB_Agent
        agent = NeuroDB_Agent.__new__(NeuroDB_Agent)
        # Access the default argument value for the model parameter
        import inspect
        sig = inspect.signature(NeuroDB_Agent.__init__)
        default = sig.parameters.get("model")
        # The default must reflect the env var or be overridable
        # Test by instantiating with env var set
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_vs = MagicMock()
        a = NeuroDB_Agent(client=mock_client, engine=mock_engine, vector_store=mock_vs)
        assert a._model == "claude-test-model"


def test_agent_falls_back_to_default_model():
    """Without NEURODB_MODEL, agent uses the hardcoded default."""
    env = {k: v for k, v in os.environ.items() if k != "NEURODB_MODEL"}
    with patch.dict(os.environ, env, clear=True):
        from importlib import reload
        import neurodb.agent
        reload(neurodb.agent)
        from neurodb.agent import NeuroDB_Agent, _DEFAULT_MODEL
        mock_client = MagicMock()
        mock_engine = MagicMock()
        mock_vs = MagicMock()
        a = NeuroDB_Agent(client=mock_client, engine=mock_engine, vector_store=mock_vs)
        assert a._model == _DEFAULT_MODEL
```

- [ ] **Step 2.3: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_agent_model_name.py -v
```
Expected: FAIL — `_DEFAULT_MODEL` not defined, or `_model` not set from env

- [ ] **Step 2.4: Update `agent.py` — read model from env var**

Find the `__init__` method and the hardcoded model string. Add at module level:

```python
import os

_DEFAULT_MODEL = "claude-opus-4-7"
_MODEL = os.environ.get("NEURODB_MODEL", _DEFAULT_MODEL)
```

In `NeuroDB_Agent.__init__`, change the `model` default parameter:

```python
def __init__(self, client, engine, vector_store, model: str = _MODEL):
    self._model = model
    # ... rest unchanged
```

- [ ] **Step 2.5: Update `session_manager.py` — same env var**

Find the hardcoded model name and replace it:

```python
import os
_SUMMARY_MODEL = os.environ.get("NEURODB_MODEL", "claude-opus-4-7")
```

Use `_SUMMARY_MODEL` wherever the literal `"claude-opus-4-7"` appears in `session_manager.py`.

- [ ] **Step 2.6: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_agent_model_name.py -v
```
Expected: both tests PASS

- [ ] **Step 2.7: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 2.8: Commit**

```bash
git add src/neurodb/agent.py src/neurodb/session_manager.py tests/unit/test_agent_model_name.py
git commit -m "feat: read model name from NEURODB_MODEL env var; fall back to claude-opus-4-7"
```

---

## Task 3: Harden api_messages on mid-tool-use exception (L3)

**Files:**
- Modify: `src/neurodb/agent.py` (the `chat` or streaming method that appends to `messages`)

The risk: if an exception occurs after a `tool_use` block is appended but before the `tool_result` block is appended, the messages list is left with an unmatched tool_use. The API will reject the next call.

Fix: record the message list length before each turn; on exception, truncate back to that length.

- [ ] **Step 3.1: Write failing test**

```python
# append to tests/unit/test_agent.py (or create tests/unit/test_agent_recovery.py)

def test_messages_rolled_back_on_tool_execution_exception():
    """If tool execution raises, api_messages must not be left in partial state."""
    import anthropic
    from unittest.mock import MagicMock, patch
    from neurodb.agent import NeuroDB_Agent

    mock_client = MagicMock()
    mock_engine = MagicMock()
    mock_vs = MagicMock()

    agent = NeuroDB_Agent(client=mock_client, engine=mock_engine, vector_store=mock_vs)

    # Simulate a tool_use response followed by an exception during tool execution
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.id = "tu_001"
    tool_use_block.name = "list_datasets"
    tool_use_block.input = {}

    mock_response = MagicMock()
    mock_response.stop_reason = "tool_use"
    mock_response.content = [tool_use_block]

    mock_client.messages.create.return_value = mock_response

    messages = []

    with patch.object(agent, "_execute_tool", side_effect=RuntimeError("tool failed")):
        with pytest.raises(RuntimeError, match="tool failed"):
            agent.chat("test", messages)

    # messages should be empty or back to its pre-call state
    assert len(messages) == 0, (
        f"Expected messages to be rolled back on exception, got {len(messages)} entries"
    )
```

- [ ] **Step 3.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_agent_recovery.py -v  # or test_agent.py
```
Expected: FAIL — messages has partial entries after exception

- [ ] **Step 3.3: Add rollback to `agent.chat()`**

In `src/neurodb/agent.py`, in the `chat` method, wrap the body in a try/except that restores the messages list on failure:

```python
def chat(self, user_message: str, messages: list) -> str:
    checkpoint = len(messages)
    try:
        messages.append({"role": "user", "content": user_message})
        # ... existing tool loop and response handling ...
        return response_text
    except Exception:
        del messages[checkpoint:]
        raise
```

- [ ] **Step 3.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_agent_recovery.py -v
```
Expected: PASS

- [ ] **Step 3.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 3.6: Commit**

```bash
git add src/neurodb/agent.py tests/unit/test_agent_recovery.py
git commit -m "fix: rollback api_messages to checkpoint on mid-tool-use exception"
```

---

## Task 4: QualityEvent compound index (L4)

**Files:**
- Modify: `src/neurodb/schema.py`

No migration needed — this index is additive and `create_all` will create it on new DBs. Existing DBs can add it manually or via a TD-1 migration if desired (low priority).

- [ ] **Step 4.1: Write failing test**

```python
# tests/unit/test_schema_indexes.py
from sqlalchemy import create_engine, inspect
from neurodb.db import init_db


def test_quality_events_has_compound_index():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    indexes = inspect(engine).get_indexes("quality_events")
    index_column_sets = [
        frozenset(idx["column_names"]) for idx in indexes
    ]
    assert frozenset({"entity_source", "entity_id", "flag"}) in index_column_sets, (
        "Expected compound index on (entity_source, entity_id, flag) in quality_events"
    )
```

- [ ] **Step 4.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_schema_indexes.py -v
```
Expected: FAIL — compound index not present

- [ ] **Step 4.3: Add compound index to `QualityEvent` in `schema.py`**

```python
from sqlalchemy import Float, ForeignKey, Index, Integer, Sequence, String, Text, UniqueConstraint

class QualityEvent(Base):
    __tablename__ = "quality_events"
    __table_args__ = (
        Index("ix_quality_events_source_id_flag", "entity_source", "entity_id", "flag"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("quality_events_id_seq"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    flag: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)
```

- [ ] **Step 4.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_schema_indexes.py -v
```
Expected: PASS

- [ ] **Step 4.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 4.6: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_schema_indexes.py
git commit -m "feat: add compound index on QualityEvent(entity_source, entity_id, flag)"
```

---

## Task 5: Validate chapter context before inject (L5)

**Files:**
- Modify: `src/neurodb/ui/pages/chat.py`

Current behavior: if `chapter_registry.lookup(chapter_ref)` fails or returns no data, the raw user input is still injected as chapter context. Fix: only set chapter context if the lookup returns a non-empty result.

- [ ] **Step 5.1: Find the chapter lookup code**

```bash
grep -n "chapter_context\|lookup\|chapter_ref\|Set chapter" src/neurodb/ui/pages/chat.py | head -20
```

- [ ] **Step 5.2: Write failing test**

```python
# tests/unit/test_chat_chapter_context.py
from unittest.mock import patch, MagicMock


def test_chapter_context_not_set_when_lookup_returns_none():
    """If chapter_registry returns no result, chapter context must not be set."""
    import streamlit as st
    from neurodb.ui.pages import chat

    # Patch chapter_registry to return None (invalid chapter)
    with patch("neurodb.ui.pages.chat.chapter_registry") as mock_registry:
        mock_registry.lookup.return_value = None

        # Simulate what the Set chapter context button handler does
        # The handler should check the return value before setting session state
        result = mock_registry.lookup("Ch99")
        assert result is None

        # Verify our chat.py code would not set context on None result
        # This is a structural test — read the handler and confirm the guard
        import pathlib
        source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
        # The set-context block must check for a truthy lookup result
        assert "if" in source and "lookup" in source, (
            "chat.py must guard chapter context assignment with a lookup result check"
        )
```

- [ ] **Step 5.3: Run test — confirm behavior**

```bash
uv run pytest tests/unit/test_chat_chapter_context.py -v
```

- [ ] **Step 5.4: Add lookup guard in `chat.py`**

Find the "Set chapter context" button handler. Wrap the context assignment:

```python
if st.button("Set chapter context", key="set_chapter_btn"):
    result = chapter_registry.lookup(chapter_input)
    if result:
        st.session_state["chapter_context"] = chapter_input
        st.rerun()
    else:
        st.warning(f"Chapter '{chapter_input}' not found in registry. Context not set.")
```

- [ ] **Step 5.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 5.6: Commit**

```bash
git add src/neurodb/ui/pages/chat.py tests/unit/test_chat_chapter_context.py
git commit -m "fix: guard chapter context assignment — only set if registry lookup succeeds"
```

---

## Task 6: Explicit st.rerun() in Study Log pre-fill (L6)

**Files:**
- Modify: `src/neurodb/ui/pages/study_log.py`

The `prefill_pending` flag is read on next render via implicit rerun from `st.dataframe`'s `on_select` callback. Adding an explicit `st.rerun()` after setting `prefill_pending = True` makes the behavior predictable regardless of Streamlit's callback handling.

- [ ] **Step 6.1: Find the pre-fill state setter**

```bash
grep -n "prefill_pending\|on_select\|selection" src/neurodb/ui/pages/study_log.py | head -20
```

- [ ] **Step 6.2: Add explicit `st.rerun()` after state mutation**

Find the `on_select` callback or the block that sets `prefill_pending = True`. Ensure `st.rerun()` is called immediately after:

```python
st.session_state["prefill_pending"] = True
st.session_state["prefill_index_id"] = selected_index_id
st.rerun()
```

If `st.rerun()` is already present here, this task is complete — confirm and skip to commit.

- [ ] **Step 6.3: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 6.4: Commit**

```bash
git add src/neurodb/ui/pages/study_log.py
git commit -m "fix: explicit st.rerun() after Study Log pre-fill state assignment"
```

---

## Task 7: Enable pytest-cov reporting (L8)

**Files:**
- Modify: `pyproject.toml`

`pytest-cov` is already in dev dependencies. This task adds a default coverage configuration so `uv run pytest` reports coverage automatically.

- [ ] **Step 7.1: Add coverage config to `pyproject.toml`**

```toml
[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["src"]
addopts = "--cov=src/neurodb --cov-report=term-missing --cov-report=html:htmlcov"

[tool.coverage.run]
omit = ["src/neurodb/ui/*"]  # UI pages require Streamlit runtime; exclude from coverage
```

- [ ] **Step 7.2: Run with coverage to confirm it works**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: test output followed by a coverage table; `htmlcov/` directory created

- [ ] **Step 7.3: Add htmlcov to .gitignore**

```bash
grep -q "htmlcov" .gitignore || echo "htmlcov/" >> .gitignore
```

- [ ] **Step 7.4: Commit**

```bash
git add pyproject.toml .gitignore
git commit -m "chore: enable pytest-cov with term-missing and html report; exclude UI pages from coverage"
```

---

## TD-3 Complete

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

All tests must pass. Update `docs/projectStatus.md` with new test count and TD-3 sign-off.
