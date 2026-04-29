# Relevance Slider Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a user-adjustable relevance threshold slider to the session start UI so the user can tune how closely prior sessions must match the current topic before context is injected.

**Architecture:** A new `prefs.py` module reads/writes a gitignored `neurodb_prefs.json` file to persist the last used threshold across server restarts. `session_manager.py` accepts the threshold as a runtime parameter instead of reading a hardcoded constant. The Streamlit start-session UI loads the saved threshold, renders a slider, and saves the chosen value when "Start Session" is clicked.

**Tech Stack:** Python 3.12, Streamlit, ChromaDB (cosine distance), `uv` for test runs.

---

## Starting Context for New Agent

**Repo root:** `/home/oldha/projects/neuroDb`  
**Run tests:** `uv run pytest tests/ -v`  
**Run app:** `uv run streamlit run src/neurodb/ui/app.py`

### What is already built and relevant

**`src/neurodb/session_manager.py`** — contains `AgentContextStore.get_relevant()` which queries ChromaDB for prior session summaries and filters by cosine distance. `SessionManager.start_session(topic)` calls it and returns `(session_id, prior_context_str)`. The hardcoded constant `_RELEVANCE_THRESHOLD = 0.5` (cosine distance) is what the slider will replace. **Bug to fix in this task:** the threshold should be `0.7`, not `0.5` — 0.5 was too strict and filtered out legitimate same-topic matches (verified by manual test: music→music session retrieved nothing).

**`src/neurodb/ui/pages/chat.py`** — Streamlit sidebar panel. `_render_start_session()` shows a topic input and Start Session button. `_render_chat()` shows the compact message history, input, and [Clear][Send] buttons. `_to_api_history()` converts `chat_history` list to Claude API format, currently filtering messages whose content starts with `"**Prior context loaded"`. **Bug to fix in this task:** when no prior context is found, the UI silently does nothing — it should display a "No prior context found for this topic." message.

**`src/neurodb/ui/app.py`** — top-level Streamlit app; mounts the chat panel in the sidebar.

**`tests/unit/test_session_manager.py`** — 20 passing unit tests. Two new tests added in previous session use `MagicMock` on `store._col` to return specific distances. These will need minor updates when the default threshold changes from 0.5 to 0.7 (verify they still pass — mock distances of 0.72 and 0.15 bracket 0.7 correctly).

**ChromaDB distance note:** The collection uses cosine distance (`"hnsw:space": "cosine"`). Distance 0 = identical, 1 = orthogonal, 2 = opposite. The default embedding model (all-MiniLM-L6-v2) produces distances in [0, ~1] for typical text. At 0.7 threshold, only summaries with cosine distance ≤ 0.7 are returned.

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `src/neurodb/prefs.py` | Create | Load/save `neurodb_prefs.json`; owns `{"relevance_threshold": 0.7}` defaults |
| `tests/unit/test_prefs.py` | Create | Unit tests for `load_prefs` / `save_prefs` |
| `src/neurodb/session_manager.py` | Modify | Change threshold constant to 0.7; add `threshold` param to `get_relevant` and `start_session` |
| `tests/unit/test_session_manager.py` | Modify | Add test for parameterized threshold in `start_session`; verify existing tests still pass |
| `src/neurodb/ui/pages/chat.py` | Modify | Slider in start session; load/save prefs; pass threshold; "no context found" message; cleaner `_system` flag in `_to_api_history` |
| `.gitignore` | Modify | Add `neurodb_prefs.json` |

---

## Task 1: `prefs.py` module and tests

**Files:**
- Create: `src/neurodb/prefs.py`
- Create: `tests/unit/test_prefs.py`
- Modify: `.gitignore`

- [ ] **Step 1.1: Write failing tests**

Create `tests/unit/test_prefs.py`:

```python
import json
import pytest
from neurodb.prefs import load_prefs, save_prefs


def test_load_prefs_returns_default_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7


def test_save_and_reload_preserves_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_prefs({"relevance_threshold": 0.4})
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.4


def test_load_prefs_with_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "neurodb_prefs.json").write_text("not valid json{{")
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7


def test_load_prefs_merges_unknown_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "neurodb_prefs.json").write_text(json.dumps({"other": 42}))
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7
    assert prefs["other"] == 42
```

- [ ] **Step 1.2: Run tests to confirm RED**

```bash
uv run pytest tests/unit/test_prefs.py -v
```

Expected: 4 failures — `ModuleNotFoundError: No module named 'neurodb.prefs'`

- [ ] **Step 1.3: Create `src/neurodb/prefs.py`**

```python
import json
from pathlib import Path

_PREFS_FILE = Path("neurodb_prefs.json")
_DEFAULTS: dict = {"relevance_threshold": 0.7}


def load_prefs() -> dict:
    if _PREFS_FILE.exists():
        try:
            data = json.loads(_PREFS_FILE.read_text())
            return {**_DEFAULTS, **data}
        except Exception:
            return _DEFAULTS.copy()
    return _DEFAULTS.copy()


def save_prefs(prefs: dict) -> None:
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))
```

- [ ] **Step 1.4: Run tests to confirm GREEN**

```bash
uv run pytest tests/unit/test_prefs.py -v
```

Expected: 4 passed

- [ ] **Step 1.5: Add `neurodb_prefs.json` to `.gitignore`**

Append to the `# NeuroDb generated artifacts` section at the bottom of `.gitignore`:

```
neurodb_prefs.json
```

- [ ] **Step 1.6: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (previously 121; now 125 with the 4 new prefs tests)

- [ ] **Step 1.7: Commit**

```bash
git add src/neurodb/prefs.py tests/unit/test_prefs.py .gitignore
git commit -m "feat: add prefs module for persisting user settings to neurodb_prefs.json"
```

---

## Task 2: Parameterize threshold in `session_manager.py`

**Files:**
- Modify: `src/neurodb/session_manager.py`
- Modify: `tests/unit/test_session_manager.py`

- [ ] **Step 2.1: Write the failing test**

Add this test to `tests/unit/test_session_manager.py` (after `test_start_session_empty_topic_returns_empty_context`):

```python
def test_start_session_respects_custom_threshold():
    """Custom threshold is passed through to get_relevant."""
    from unittest.mock import MagicMock
    store = _store()
    store._col = MagicMock()
    store._col.count.return_value = 1
    # distance 0.65 — below 0.7 (default) but above 0.6 (strict)
    store._col.query.return_value = {
        "documents": [["Topic: hippocampus\nConcepts: place cells"]],
        "distances": [[0.65]],
    }
    manager = SessionManager(store)

    _, context_default = manager.start_session("hippocampus")
    assert "place cells" in context_default  # 0.65 <= 0.7, included

    _, context_strict = manager.start_session("hippocampus", threshold=0.6)
    assert context_strict == ""  # 0.65 > 0.6, excluded
```

- [ ] **Step 2.2: Run test to confirm RED**

```bash
uv run pytest tests/unit/test_session_manager.py::test_start_session_respects_custom_threshold -v
```

Expected: FAIL — `TypeError: start_session() got an unexpected keyword argument 'threshold'`

- [ ] **Step 2.3: Update `src/neurodb/session_manager.py`**

Make three changes:

**Change 1** — raise the default threshold from 0.5 to 0.7:
```python
_RELEVANCE_THRESHOLD = 0.7  # cosine distance; summaries above this are not injected
```

**Change 2** — add `threshold` parameter to `get_relevant`:
```python
def get_relevant(self, query: str, n: int = 3, threshold: float = _RELEVANCE_THRESHOLD) -> list[str]:
    """Return the n most semantically relevant session summaries for query."""
    if not query:
        return []
    count = self._col.count()
    if count == 0:
        return []
    results = self._col.query(query_texts=[query], n_results=min(n, count))
    if not results["documents"]:
        return []
    docs = results["documents"][0]
    distances = results["distances"][0]
    return [doc for doc, dist in zip(docs, distances) if dist <= threshold]
```

**Change 3** — add `threshold` parameter to `start_session`:
```python
def start_session(self, topic: str, threshold: float = _RELEVANCE_THRESHOLD) -> tuple[str, str]:
    """Return (session_id, prior_context_str). Context is empty on cold start."""
    session_id = str(uuid.uuid4())
    if not topic:
        return session_id, ""
    summaries = self._store.get_relevant(topic, n=3, threshold=threshold)
    return session_id, format_context(summaries)
```

- [ ] **Step 2.4: Run all session_manager tests to confirm GREEN**

```bash
uv run pytest tests/unit/test_session_manager.py -v
```

Expected: 21 passed. Specifically verify:
- `test_context_store_filters_out_high_distance_results` still passes (mock distance 0.72 > 0.7 ✓)
- `test_context_store_returns_low_distance_results` still passes (mock distance 0.15 ≤ 0.7 ✓)
- `test_start_session_respects_custom_threshold` passes (new)

- [ ] **Step 2.5: Run full suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass (125 + 1 new = 126)

- [ ] **Step 2.6: Commit**

```bash
git add src/neurodb/session_manager.py tests/unit/test_session_manager.py
git commit -m "feat: parameterize relevance threshold in session_manager; raise default to 0.7"
```

---

## Task 3: Slider UI, "no context found" message, and wire-up

**Files:**
- Modify: `src/neurodb/ui/pages/chat.py`

No new tests for this task — the UI logic (slider value passed to `start_session`, prefs saved on click) is covered by the session_manager and prefs tests already written. The `_to_api_history` filter change is covered by existing tests `test_agent_injects_prior_context_into_system_prompt` and `test_agent_no_prior_context_omits_block`.

- [ ] **Step 3.1: Replace `src/neurodb/ui/pages/chat.py` with the full updated file**

Write the complete file content below. Key changes from the current file:
- `_render_start_session`: loads saved threshold into `st.session_state` on first render; adds slider (0.1–1.0, step 0.1); passes threshold to `start_session`; saves threshold to prefs on session start; adds "No prior context found" assistant message when context is empty; both system messages use `"_system": True` flag.
- `_render_chat`: unchanged from current state.
- `_to_api_history`: filters on `msg.get("_system")` instead of content prefix string.

```python
import os

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    _init_agent(engine)

    agent = st.session_state.get("neuro_agent")
    if agent is None:
        return

    session_active = "session_id" in st.session_state

    if not session_active:
        _render_start_session()
        return

    _render_end_session_button(engine)
    _render_chat(agent)


def _init_agent(engine: Engine) -> None:
    if "neuro_agent" in st.session_state:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable the Research Assistant.")
        return
    import anthropic
    from neurodb.agent import NeuroAgent
    client = anthropic.Anthropic(api_key=api_key)
    vs = st.session_state.get("vector_store")
    st.session_state["neuro_agent"] = NeuroAgent(client, engine, vector_store=vs)


def _render_start_session() -> None:
    from neurodb.prefs import load_prefs, save_prefs

    if "relevance_threshold" not in st.session_state:
        st.session_state["relevance_threshold"] = load_prefs()["relevance_threshold"]

    topic = st.text_input("Topic (optional)", placeholder="e.g. hippocampus place cells")

    threshold = st.slider(
        "Context relevance",
        min_value=0.1,
        max_value=1.0,
        value=st.session_state["relevance_threshold"],
        step=0.1,
        help="Lower = stricter topic match only; Higher = broader, more loosely related sessions included",
        key="relevance_threshold",
    )

    if st.button("Start Session", use_container_width=True):
        save_prefs({"relevance_threshold": threshold})

        manager = st.session_state.get("session_manager")
        if manager:
            session_id, context = manager.start_session(topic.strip(), threshold=threshold)
        else:
            import uuid
            session_id, context = str(uuid.uuid4()), ""

        st.session_state["session_id"] = session_id
        st.session_state["session_topic"] = topic.strip()

        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.prior_context = context

        if context:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"**Prior context loaded:**\n\n{context}",
                "_system": True,
            })
        else:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": "No prior context found for this topic.",
                "_system": True,
            })

        st.rerun()

    st.caption("The agent will retrieve prior context for your topic.")


def _render_end_session_button(engine: Engine) -> None:
    topic = st.session_state.get("session_topic", "")
    label = f"Session: {topic}" if topic else "Session active"
    st.caption(label)
    if st.button("End Session", use_container_width=True):
        manager = st.session_state.get("session_manager")
        session_id = st.session_state.pop("session_id", None)
        if manager and session_id:
            api_history = _to_api_history(st.session_state["chat_history"])
            with st.spinner("Saving session summary…"):
                manager.end_session(session_id, api_history)
        for key in ("session_topic", "chat_history"):
            st.session_state.pop(key, None)
        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.prior_context = ""
        st.rerun()


def _render_chat(agent) -> None:
    with st.container(height=200):
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.form("agent_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="Ask about your datasets…",
            label_visibility="collapsed",
        )
        col_clear, col_send = st.columns([1, 2])
        with col_clear:
            clear_clicked = st.form_submit_button("Clear", use_container_width=True)
        with col_send:
            submitted = st.form_submit_button("Send", use_container_width=True)

    if clear_clicked:
        st.session_state["chat_history"] = []
        st.rerun()
    elif submitted and user_input.strip():
        message = user_input.strip()
        st.session_state["chat_history"].append({"role": "user", "content": message})
        api_history = _to_api_history(st.session_state["chat_history"][:-1])
        with st.spinner("Thinking…"):
            chunks = list(agent.chat(message, api_history))
        response_text = "".join(chunks)
        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.rerun()

    last_response = next(
        (msg["content"] for msg in reversed(st.session_state["chat_history"])
         if msg["role"] == "assistant" and not msg.get("_system")),
        None,
    )
    if last_response:
        st.divider()
        st.markdown(last_response)


def _to_api_history(history: list[dict]) -> list[dict]:
    """Convert display history to API message format, skipping system-injected messages."""
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and not msg.get("_system"):
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api
```

- [ ] **Step 3.2: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all 126 tests pass. No new tests written for this task — session_manager and prefs tests already cover the logic. If any existing test fails, investigate before proceeding.

- [ ] **Step 3.3: Start Streamlit and manually verify**

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`. In the sidebar, verify:

| Scenario | Expected |
|---|---|
| Before session: slider visible at 0.7 (or last saved value) | ✓ |
| Slider moves in 0.1 steps | ✓ |
| Start session with no prior data → "No prior context found for this topic." appears in compact history | ✓ |
| Start session with matching prior data → "**Prior context loaded:**…" appears | ✓ |
| End session, restart server, open again → slider still shows last used value | ✓ |
| Adjust slider to 0.3, start session → saves 0.3 to `neurodb_prefs.json` | ✓ |

Verify `neurodb_prefs.json` content after a session start:
```bash
cat neurodb_prefs.json
# Expected: {"relevance_threshold": <whatever you set>}
```

- [ ] **Step 3.4: Commit**

```bash
git add src/neurodb/ui/pages/chat.py
git commit -m "feat: add context relevance slider to session start; persist last value; show no-context message"
```

---

## Self-Review

**Spec coverage:**
- ✅ Slider in 0.1 increments — Step 3.1 slider `step=0.1`
- ✅ Default 0.7 — `_DEFAULTS` in prefs.py, `_RELEVANCE_THRESHOLD = 0.7` in session_manager
- ✅ Persist last used value — `save_prefs` on "Start Session" click; `load_prefs` on first render
- ✅ Threshold passed to `start_session` → `get_relevant` — Task 2
- ✅ Bug fix: "No prior context found" message — Step 3.1
- ✅ Bug fix: threshold raised from 0.5 to 0.7 — Step 2.3

**Placeholder scan:** None found. All steps contain complete code.

**Type consistency:**
- `load_prefs() -> dict` / `save_prefs(prefs: dict) -> None` — used consistently in Task 1 and Task 3
- `get_relevant(query, n, threshold)` — defined Task 2, not referenced independently in Task 3 (called via `start_session`)
- `start_session(topic, threshold)` — defined Task 2, called in Task 3 as `manager.start_session(topic.strip(), threshold=threshold)`
- `_system` key in chat_history dicts — introduced Task 3 step 3.1, consumed by `_to_api_history` in same file
