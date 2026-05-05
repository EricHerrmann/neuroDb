# Pre-LT-2: Chat Layout Hardening — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move mode/chapter controls into Streamlit's native sidebar and pin the chat input to the bottom so it stays visible as conversations grow — all without breaking any of the 255 existing tests.

**Architecture:** A new `src/neurodb/ui/sidebar.py` module takes over all sidebar rendering. In `chat.py`, `_render_mode_and_chapter()` is deleted and `st.container(height=N)` is wired to the transcript so it scrolls in place while the input stays pinned below. CSS injected into `_inject_ui_styles()` constrains the right workspace column to scroll independently. A JS snippet appended after each new agent response attempts to auto-scroll the transcript.

**Tech Stack:** Python, Streamlit ≥1.56 (`st.container(height, border)` API), CSS injection via `st.markdown(unsafe_allow_html=True)`

---

## File Map

| Action | File | Responsibility |
|--------|------|----------------|
| Create | `src/neurodb/ui/sidebar.py` | Agent + Context sidebar sections |
| Modify | `src/neurodb/ui/app.py` | CSS additions, sidebar wiring, db_path in session_state |
| Modify | `src/neurodb/ui/pages/chat.py` | Delete `_render_mode_and_chapter`, wire transcript height, add JS auto-scroll |
| Create | `tests/unit/test_sidebar.py` | Structural tests for the new sidebar module |
| Modify | `tests/unit/test_chat_ui.py` | Update `test_three_mode_options_present_in_chat` → sidebar; add `test_chat_has_no_mode_radio` |
| Modify | `tests/unit/test_chat_chapter_context.py` | Update source path to read `sidebar.py` instead of `chat.py` |
| Create | `docs/testsPlans/manualTestPlan_pre_lt2_layout.md` | Manual verification test plan |

**Final test count target:** 262 (255 existing + 6 new in `test_sidebar.py` + 1 new in `test_chat_ui.py`)

---

### Task 1: Create `src/neurodb/ui/sidebar.py` — Sidebar Rendering Module ✅ COMPLETE (cab7ccd)

The mode radio and chapter context controls move from `chat.py` to a dedicated `sidebar.py`. The module exposes one function: `render_sidebar()`. It reads/writes `st.session_state` only — no engine needed. It reads `db_path` from `st.session_state["db_path"]` (set by `app.py` before calling `render_sidebar()`).

**Files:**
- Create: `tests/unit/test_sidebar.py`
- Create: `src/neurodb/ui/sidebar.py`

- [ ] **Step 1: Write failing structural tests**

Create `tests/unit/test_sidebar.py`:

```python
import ast
import pathlib


def _get_source() -> str:
    return pathlib.Path("src/neurodb/ui/sidebar.py").read_text()


def _get_tree() -> ast.AST:
    return ast.parse(_get_source())


def test_sidebar_module_defines_render_sidebar():
    tree = _get_tree()
    fn_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert "render_sidebar" in fn_names


def test_sidebar_contains_mode_radio():
    source = _get_source()
    assert "st.radio" in source


def test_sidebar_contains_all_three_mode_keys():
    source = _get_source()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source


def test_sidebar_contains_chapter_controls():
    source = _get_source()
    assert "st.selectbox" in source
    assert "st.text_input" in source


def test_set_chapter_button_guarded_by_lookup_result():
    source = _get_source()
    lines = source.splitlines()
    btn_line = None
    for i, line in enumerate(lines, start=1):
        if "Set chapter context" in line and "st.button" in line:
            btn_line = i
            break
    assert btn_line is not None, "Could not find 'Set chapter context' button in sidebar.py"
    info_guard_line = None
    for i in range(btn_line - 1, 0, -1):
        stripped = lines[i - 1].strip()
        if stripped.startswith("if info") or stripped == "if info:":
            info_guard_line = i
            break
    assert info_guard_line is not None, (
        f"'Set chapter context' button (line {btn_line}) must be inside an 'if info:' guard"
    )


def test_sidebar_does_not_contain_form_or_chat_state():
    source = _get_source()
    assert "st.form(" not in source
    assert "pending_user_message" not in source
```

- [ ] **Step 2: Run tests — verify they all fail**

```bash
uv run pytest tests/unit/test_sidebar.py -v
```

Expected: 6 errors — `sidebar.py` does not exist yet.

- [ ] **Step 3: Create `src/neurodb/ui/sidebar.py`**

```python
import streamlit as st


def render_sidebar() -> None:
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    with st.sidebar:
        with st.expander("Agent", expanded=True):
            mode_labels = {
                "local_db": "Local DB",
                "external_db": "External DB",
                "neuro_tutor": "Neuro-Tutor",
            }
            mode_options = list(mode_labels)
            current_mode = st.session_state.get("agent_mode", "local_db")
            selected_mode = st.radio(
                "Mode",
                options=mode_options,
                index=mode_options.index(current_mode) if current_mode in mode_options else 0,
                format_func=lambda m: mode_labels[m],
                label_visibility="collapsed",
            )
            if selected_mode != current_mode:
                st.session_state["agent_mode"] = selected_mode
                st.session_state["chapter_context"] = ""
                st.session_state.pop("neuro_agent", None)
                st.rerun()

        if st.session_state.get("agent_mode", "local_db") != "neuro_tutor":
            with st.expander("Context", expanded=True):
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
                        book_key = st.session_state.get("selected_book_key", "")
                        info = lookup_chapter(book_key, chapter_num)
                        if info:
                            st.success(
                                f"**Ch{chapter_num} — {info['title']}**\n"
                                f"Topics: {', '.join(info['topics'])}"
                            )
                            context_str = (
                                f"Ch{chapter_num} — {info['title']}\n"
                                f"Topics: {', '.join(info['topics'])}"
                            )
                            if st.button("Set chapter context", key="set_chapter_btn"):
                                st.session_state["chapter_context"] = context_str
                                agent = st.session_state.get("neuro_agent")
                                if agent:
                                    agent.chapter_context = context_str
                                st.rerun()
                        else:
                            st.warning(
                                f"Ch{chapter_num} not yet in registry — context not set."
                            )
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

        db_path = st.session_state.get("db_path", "neurodb.duckdb")
        st.divider()
        st.caption(f"DB: `{db_path}`")
        st.caption(f"Session: `{'active' if 'session_id' in st.session_state else 'none'}`")
```

- [ ] **Step 4: Run tests — verify they all pass**

```bash
uv run pytest tests/unit/test_sidebar.py -v
```

Expected: 6 PASS.

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: 261 passed.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/ui/sidebar.py tests/unit/test_sidebar.py
git commit -m "feat: add sidebar module with Agent and Context sections"
```

---

### Task 2: Update Existing Tests for the Sidebar Migration ✅ COMPLETE (f5088aa)

`external_db` only appears in `_render_mode_and_chapter()` — once that function is deleted, `test_three_mode_options_present_in_chat` will fail because `external_db` won't be in `chat.py`. `test_set_chapter_button_is_guarded_by_lookup_result` reads `chat.py` for the chapter button that is moving to `sidebar.py`. Update both tests now, before touching the implementation, so the failing tests define the target state.

**Files:**
- Modify: `tests/unit/test_chat_ui.py`
- Modify: `tests/unit/test_chat_chapter_context.py`

- [ ] **Step 1: Update `test_chat_ui.py` — rename mode test, add no-radio test**

In `tests/unit/test_chat_ui.py`, replace:

```python
def test_three_mode_options_present_in_chat():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source
```

With:

```python
def test_three_mode_options_present_in_sidebar():
    source = pathlib.Path("src/neurodb/ui/sidebar.py").read_text()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source


def test_chat_has_no_mode_radio():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert "st.radio" not in source
```

- [ ] **Step 2: Update `test_chat_chapter_context.py` — change source path to sidebar.py**

In `tests/unit/test_chat_chapter_context.py`, replace:

```python
def _get_chat_source() -> str:
    return pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
```

With:

```python
def _get_chat_source() -> str:
    return pathlib.Path("src/neurodb/ui/sidebar.py").read_text()
```

- [ ] **Step 3: Run updated tests — expect exactly 1 failure**

```bash
uv run pytest tests/unit/test_chat_ui.py tests/unit/test_chat_chapter_context.py -v
```

Expected: `test_chat_has_no_mode_radio` FAIL (chat.py still has `st.radio`). All other tests in these files PASS — `test_three_mode_options_present_in_sidebar` passes because `sidebar.py` exists, and `test_set_chapter_button_is_guarded_by_lookup_result` passes because `sidebar.py` has the guarded button.

- [ ] **Step 4: Commit the test updates**

```bash
git add tests/unit/test_chat_ui.py tests/unit/test_chat_chapter_context.py
git commit -m "test: update mode/chapter tests to target sidebar.py after migration"
```

---

### Task 3: Update `chat.py` — Delete Mode/Chapter Controls, Wire Transcript Height, Add Auto-scroll

**Files:**
- Modify: `src/neurodb/ui/pages/chat.py`

- [ ] **Step 1: Delete `_render_mode_and_chapter()` and its call from `render_panel()`**

Open `src/neurodb/ui/pages/chat.py`.

Delete the entire `_render_mode_and_chapter()` function (lines 65–143). The function body contains its own `from neurodb.chapter_registry import ...` import, so no module-level import needs cleanup.

Update `render_panel()` to remove the call and the `st.divider()` that was rendered by the deleted function. The updated function body:

```python
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

    agent = st.session_state.get("neuro_agent")
    if agent is None:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable chat.")
    _render_chat(agent, transcript_height=transcript_height)
```

- [ ] **Step 2: Wire `transcript_height` into `st.container()` in `_render_chat()`**

In `_render_chat()`, replace:

```python
transcript_container = st.container()
```

With:

```python
transcript_container = st.container(height=transcript_height, border=False)
```

`border=False` suppresses the default box border added by Streamlit when `height` is set, preserving the existing visual appearance.

- [ ] **Step 3: Add JS auto-scroll inside the streaming response block**

In `_render_chat()`, inside the `if pending_message and agent is not None:` block, after the line `st.session_state["pending_user_message"] = None` and before `st.rerun()`, add:

```python
        st.markdown(
            """
            <script>
            (function() {
              const el = window.parent.document.querySelector(
                '[data-testid="stVerticalBlockBorderWrapper"]'
              );
              if (el) { el.scrollTop = el.scrollHeight; }
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )
```

The full end of the streaming block (for context — do not duplicate other lines):

```python
        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.session_state["pending_user_message"] = None
        st.markdown(
            """
            <script>
            (function() {
              const el = window.parent.document.querySelector(
                '[data-testid="stVerticalBlockBorderWrapper"]'
              );
              if (el) { el.scrollTop = el.scrollHeight; }
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )
        st.rerun()
```

- [ ] **Step 4: Run the previously failing test — verify it now passes**

```bash
uv run pytest tests/unit/test_chat_ui.py::test_chat_has_no_mode_radio -v
```

Expected: PASS.

- [ ] **Step 5: Run full test suite — confirm all pass**

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: 262 passed, 0 failed.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/ui/pages/chat.py
git commit -m "feat: remove mode/chapter panel from chat, wire transcript height, add auto-scroll"
```

---

### Task 4: Update `app.py` — Add Fixed-Height CSS and Wire Sidebar

**Files:**
- Modify: `src/neurodb/ui/app.py`

- [ ] **Step 1: Store `db_path` in session state**

In `app.py`, after the `sys.argv` loop that sets `db_path` (before `engine = get_engine(...)`), add:

```python
st.session_state["db_path"] = db_path
```

The full block at that location becomes:

```python
db_path = "neurodb.duckdb"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

st.session_state["db_path"] = db_path

engine = get_engine(f"duckdb:///{db_path}")
```

- [ ] **Step 2: Add fixed-height layout CSS to `_inject_ui_styles()`**

Inside `_inject_ui_styles()`, append the following CSS rules inside the existing triple-quoted `<style>` block, right before the closing `</style>` tag:

```css
        /* Pre-LT-2: Suppress page scroll; right workspace column scrolls independently */
        body {
          overflow: hidden;
        }

        section[data-testid="stMain"] {
          overflow: hidden !important;
        }

        section[data-testid="stMain"] .block-container {
          padding-bottom: 0 !important;
          overflow: hidden !important;
          max-height: 100vh;
        }

        div[data-testid="stHorizontalBlock"] > div[data-testid="stColumn"]:last-of-type {
          overflow-y: auto;
          max-height: calc(100vh - 80px);
        }
```

The `80px` offset accounts for the Streamlit toolbar height. If the layout shifts after a Streamlit upgrade, adjust this single value.

- [ ] **Step 3: Replace the inline sidebar block with `render_sidebar()`**

In `app.py`, remove the entire `# --- Sidebar: lightweight workspace status ---` block:

```python
# --- Sidebar: lightweight workspace status ---
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

Replace it with:

```python
from neurodb.ui.sidebar import render_sidebar
render_sidebar()
```

Place this call after the `knowledge_store` initialization block and before the `col_chat, col_workspace = st.columns(...)` line.

- [ ] **Step 4: Run full test suite — confirm all 262 pass**

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: 262 passed, 0 failed.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/ui/app.py
git commit -m "feat: add fixed-height layout CSS and wire sidebar module in app.py"
```

---

### Task 5: Manual Test Plan + Final Regression

**Files:**
- Create: `docs/testsPlans/manualTestPlan_pre_lt2_layout.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Create the manual test plan**

Create `docs/testsPlans/manualTestPlan_pre_lt2_layout.md`:

```markdown
# Pre-LT-2: Chat Layout Hardening — Manual Test Plan

**Feature:** Fixed-pane layout, input pinned to bottom, sidebar migration
**Status:** Pending sign-off
**Spec:** `docs/superpowers/specs/2026-05-05-pre-lt2-chat-layout-hardening.md`

---

## Prerequisites

1. `.env` has `ANTHROPIC_API_KEY` set.
2. Start the app: `uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb`
3. Open `http://localhost:8501` in a browser.

---

## T1 — Input stays visible as conversation grows

1. Send 6+ messages until the transcript is longer than the viewport.
2. **Pass:** The text input and Send/Clear buttons remain visible at the bottom without scrolling the page.
3. **Fail:** The input scrolls off the bottom of the screen.

---

## T2 — Transcript scrolls within its pane

1. With multiple messages in the transcript, scroll up within the transcript area.
2. **Pass:** Only the transcript scrolls; the input area stays pinned below it.
3. **Fail:** Scrolling moves the whole page rather than just the transcript.

---

## T3 — Right workspace pane is always accessible

1. Send several messages until the transcript is long.
2. Without any page scroll, click through Suggestions, Study Log, Datasets, Registry, Knowledge Library, and SQL tabs in the right pane.
3. **Pass:** All tabs are reachable; no page scrolling required.
4. **Fail:** Tabs are cut off or require page scroll to reach.

---

## T4 — Right workspace pane scrolls independently

1. Open the Datasets tab. If the dataset list is long, scroll down within it.
2. **Pass:** Only the Datasets list scrolls; the chat pane and tab bar stay fixed.
3. **Fail:** Scrolling the right pane scrolls the whole page.

---

## T5 — Mode toggle in sidebar

1. Locate the Agent section in the left sidebar (expand if collapsed).
2. Switch between Local DB, External DB, and Neuro-Tutor using the radio.
3. **Pass:** Mode changes take effect (agent reinitializes); the radio is in the sidebar, not in the main chat panel.
4. **Fail:** Radio is absent from the sidebar, or still appears inside the chat panel.

---

## T6 — Chapter context controls in sidebar

1. Switch to Local DB mode. Open the Context section in the sidebar.
2. Select a textbook and type `Ch12`.
3. Click "Set chapter context".
4. **Pass:** Active context caption appears in the sidebar; the chat panel has no chapter controls.
5. **Fail:** Chapter controls are missing from the sidebar, or appear inside the chat panel.

---

## T7 — Sidebar collapse reflows columns

1. Click the Streamlit sidebar collapse arrow (≡ icon at the sidebar edge).
2. **Pass:** Both chat and workspace columns expand proportionally to fill available width.
3. **Fail:** Columns stay narrow or overlap when sidebar is collapsed.

---

## T8 — Auto-scroll after agent response

1. Send a message that produces a multi-paragraph response.
2. Before the response lands, scroll the transcript up.
3. **Pass:** After the response finishes, the transcript scrolls back to the newest message.
4. **Note:** Auto-scroll uses a JavaScript injection and may not fire in all browser security contexts. If it does not scroll automatically, confirm that the input remains visible and note the browser/OS. This test does not block sign-off on its own.

---

## Sign-off

| Test | Result | Notes |
|------|--------|-------|
| T1 | | |
| T2 | | |
| T3 | | |
| T4 | | |
| T5 | | |
| T6 | | |
| T7 | | |
| T8 | | |

**Signed off by:** ___  **Date:** ___
```

- [ ] **Step 2: Add manual test plan reference to `docs/projectStatus.md`**

In the Key References table, add:

```
| `docs/testsPlans/manualTestPlan_pre_lt2_layout.md` | Pre-LT-2 manual test plan — layout, sidebar, input pinning |
```

- [ ] **Step 3: Run final regression — confirm 262 tests pass**

```bash
uv run pytest tests/ -q --tb=no 2>&1 | tail -3
```

Expected: 262 passed, 0 failed.

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_pre_lt2_layout.md docs/projectStatus.md
git commit -m "docs: add Pre-LT-2 manual test plan and update project status references"
```

---

## Self-Review

**Spec coverage:**

| Spec Section | Covered by |
|---|---|
| §1 Fixed-height column layout (CSS injection) | Task 4 Step 2 — body/main/block-container overflow rules + right column `max-height` |
| §2 Input pinned to bottom | Task 3 Step 2 — `st.container(height=N, border=False)` creates scrollable transcript; input naturally sits below |
| §3 Transcript auto-scroll | Task 3 Step 3 — JS injected via `st.markdown` after each response |
| §4 Mode toggle + chapter → sidebar | Task 1 — `sidebar.py`; Task 3 Step 1 — deleted from chat.py |
| §5 Sidebar as extensible config panel | Task 1 — `st.expander("Agent")` + `st.expander("Context")` with named sections; LT-2 slots reserved |
| §6 chat.py cleanup — delete `_render_mode_and_chapter` | Task 3 Step 1 |
| Testing: chat.py no longer has `st.radio` | Task 2 Step 1 — `test_chat_has_no_mode_radio` |
| Testing: sidebar module has mode/chapter widgets | Task 1 — 6 structural tests |
| Testing: all 255 existing tests pass | Task 5 Step 3 — 262 total |
| Manual: layout, auto-scroll, sidebar collapse | Task 5 Step 1 — T1–T8 |

No gaps found.
