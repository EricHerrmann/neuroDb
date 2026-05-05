# Neuro-Tutor Epoch — Design Spec

**Date:** 2026-05-05
**Epoch plan:** `docs/ClaudeLearnEpochPlan.md`
**Status:** Draft — pending user review

---

## Goal

Give the user a capable neuroscience learning partner — one that remembers what has been explored and builds on it, so learning compounds over time.

---

## Overview

This epoch introduces the `NeuroTutorAgent` alongside a refactored `NeuroDbAgent`, both inheriting from a new `BaseAgent` abstract class. The Neuro-Tutor surfaces candidate knowledge sources during conversations, queues them for user curation, and retrieves approved summaries via semantic search. A persistent knowledge library grows over time. Cross-session memory is automatic — no Start/End Session ceremony.

This spec covers Phase 1 of the epoch. Later phases (external literature API integration, Previous Topics panel, research agent scaffolding) are noted but not designed here.

---

## 1. Agent Architecture

### 1.1 Module layout

```
src/neurodb/agents/
    base.py          ← BaseAgent (abstract)
    db_agent.py      ← NeuroDbAgent (renamed from agent.py)
    tutor_agent.py   ← NeuroTutorAgent (new)
```

The existing `src/neurodb/agent.py` is migrated into `src/neurodb/agents/db_agent.py`. All import sites are updated. `agent.py` is removed.

### 1.2 BaseAgent

`BaseAgent` is an abstract class defining the interface all agents share. Subclasses implement three methods; the conversation loop is inherited.

```python
class BaseAgent(ABC):
    def __init__(self, client, engine, vector_store, model, prior_context):
        ...

    @abstractmethod
    def _get_active_tools(self) -> list[dict]: ...

    @abstractmethod
    def _build_system_prompt(self) -> str: ...

    @abstractmethod
    def _execute_tool_block(self, block) -> str: ...

    def chat(self, user_message: str, messages: list[dict]) -> Generator[str, None, None]:
        # checkpoint/rollback + _chat_inner (migrated from agent.py)

    def chat_stream(self, user_message: str, messages: list[dict]) -> Iterable[dict]:
        # streaming loop (migrated from agent.py)
```

### 1.3 NeuroDbAgent

Direct migration of the current `NeuroAgent`. Accepts `mode: str = "local_db"` (values: `"local_db"`, `"external_db"`). Internal tool selection and system prompt vary by mode, as today with `"learning"` / `"discovery"`. Rename only — no behavior changes.

### 1.4 NeuroTutorAgent

New agent class. Receives `engine`, `vector_store`, `client`, `model`, `prior_context`, and a `knowledge_store` (the `KnowledgeLibraryStore` instance). System prompt is learning-focused and instructs the agent to call `queue_source` whenever it cites an external resource, and to call `search_knowledge_library` to ground answers in curated material before drawing on training knowledge alone.

### 1.5 Pattern contract

Every future agent class (`NeuroResearchAgent`, `HypothesisAgent`, etc.) inherits `BaseAgent` and implements the same three abstract methods. The chat page selects the agent class based on mode; the conversation loop, rollback logic, and streaming protocol are never re-implemented.

---

## 2. Mode Rename and UI Wiring

### 2.1 Mode values

| Old value | New value | Display label |
|-----------|-----------|---------------|
| `"learning"` | `"local_db"` | Local DB |
| `"discovery"` | `"external_db"` | External DB |
| *(new)* | `"neuro_tutor"` | Neuro-Tutor |

### 2.2 Agent selection

The chat page maps mode to agent class at render time:

- `"local_db"` → `NeuroDbAgent(mode="local_db")`
- `"external_db"` → `NeuroDbAgent(mode="external_db")`
- `"neuro_tutor"` → `NeuroTutorAgent(...)`

On mode change: the new agent is instantiated with the same `engine`, `vector_store`, and `client`. `api_messages` carries over — conversation history persists across mode switches within a session. `chapter_context` resets on mode switch (it is Local DB-specific).

The active agent is stored in `st.session_state["neuro_agent"]` regardless of which class it is — the chat rendering code calls `.chat_stream()` on whichever agent is present.

---

## 3. Knowledge Library Storage

### 3.1 `knowledge_sources` table (SQLite via SQLAlchemy)

Tracks every source the Neuro-Tutor has ever surfaced — pending, approved, or rejected.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `title` | Text | Dedup key (normalized) |
| `doi` | Text, nullable | Dedup key (exact) |
| `url` | Text, nullable | |
| `source_type` | String(32) | `paper`, `review`, `textbook`, `website` |
| `topic_context` | Text | What was being discussed when surfaced |
| `status` | String(16) | `pending`, `approved`, `rejected` |
| `queued_at` | String(32) | ISO timestamp |
| `reviewed_at` | String(32), nullable | |
| `summary` | Text, nullable | Claude-generated; written at approval time |
| `chroma_id` | String(64), nullable | Set after embedding into `knowledge_library` |

### 3.2 `knowledge_library` ChromaDB collection

Approved summaries, semantically indexed. Each document stores the summary text with metadata: `source_id` (FK to `knowledge_sources.id`), `title`, `doi`, `topic_context`. The `NeuroTutorAgent` queries this collection via `search_knowledge_library`.

A `KnowledgeLibraryStore` class (new, in `src/neurodb/knowledge_store.py`) wraps this collection, analogous to how `AgentContextStore` wraps `agent_context`. It exposes `add_summary(source_id, title, doi, topic_context, summary)` and `search(query, n)` methods. The store is constructed once in `app.py` and passed to `NeuroTutorAgent` at instantiation.

### 3.3 `sessions` table (SQLite via SQLAlchemy)

Index of completed sessions for the Previous Topics panel (phase 2). Built in phase 1 so the data accumulates before the UI surface is added.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `session_id` | String(64) | UUID |
| `inferred_topic` | Text | Derived from first user message |
| `agent_mode` | String(16) | `local_db`, `external_db`, `neuro_tutor` |
| `started_at` | String(32) | ISO timestamp |
| `ended_at` | String(32), nullable | Set when summary stored |
| `summary_preview` | String(200), nullable | First 200 chars of Claude summary |
| `message_count` | Integer | User turns only |

Sessions with fewer than 3 user turns are not stored (avoids noise from accidental or trivial conversations).

---

## 4. Source Surfacing and Queuing

### 4.1 `queue_source` tool

A side-effect tool available only to `NeuroTutorAgent`. The system prompt instructs the agent to call it whenever it references an external resource (paper, review, textbook chapter, website). The tool never blocks or branches the response — it returns `"queued"` or `"already pending"` and the agent continues.

**Inputs**: `title` (required), `source_type` (required), `topic_context` (required), `doi` (optional), `url` (optional).

**Dedup at queue time (exact match)**:
1. If `doi` is provided: check for existing row with same DOI (any status). Skip insert if found.
2. Otherwise: normalize `title` (lowercase, strip punctuation) and check for exact match. Skip if found.

Exact-match dedup catches the common case: the same paper cited in multiple conversations.

### 4.2 Approval flow

User opens the Knowledge Library page → reviews pending sources → clicks Approve. On approval:
1. Claude generates a structured summary (title, source type, key concepts, relevance to neuroscience, open questions).
2. Summary stored in `knowledge_sources.summary`.
3. Summary embedded and added to the `knowledge_library` ChromaDB collection.
4. `knowledge_sources.chroma_id` set; `status` → `"approved"`.

**Semantic dedup at review time**: before showing the Approve button, the Knowledge Library page runs a ChromaDB similarity query against approved entries. If a near-duplicate is found (cosine distance ≤ 0.15), a warning is shown inline: *"Similar to approved source: [title]"*. The user can still approve — the warning is informational.

---

## 5. NeuroTutorAgent Tools

| Tool | Source | Purpose |
|------|--------|---------|
| `search_knowledge_library` | New | Semantic search of approved ChromaDB summaries |
| `search_literature` | New (phase 1: stub; phase 2: PubMed + Semantic Scholar API) | Broad external discovery of uncurated sources |
| `queue_source` | New | Side-effect: log a cited source to the pending queue |
| `query_db` | Existing | Local DB SQL queries |
| `semantic_search` | Existing | Study note semantic search |
| `get_study_notes` | Existing | Study notes retrieval |

Discovery tools (`search_external`, `suggest_import`, `suggest_learning_source`, `suggest_new_source`) remain in `NeuroDbAgent` External DB mode only. They search neuroscience *dataset* repositories. `search_literature` searches knowledge *sources* (papers, reviews). Clean boundary.

**Retrieval strategy**: `search_knowledge_library` is called per-query, not at session start. As the library grows it becomes the primary factual grounding mechanism. Session summaries (from auto-session) provide conversational continuity via `prior_context` at agent construction — distinct from factual retrieval.

**Phase 1 `search_literature`**: the tool takes a `query` string and returns a JSON list of candidate sources the agent knows about from training — each entry has `title`, `source_type`, `doi` (if known), and a one-sentence description. No external API call is made. The agent calls `queue_source` for each entry it considers relevant. Phase 2 replaces this implementation with live PubMed and Semantic Scholar API calls returning the same JSON structure, so the downstream queue flow is unchanged.

---

## 6. Auto-Session (replaces Start/End Session)

### 6.1 Removed UI

The "Start Session" and "End Session" buttons are removed. The topic text input and relevance threshold slider are removed from the sidebar. The `_render_start_session` and `_render_end_session_button` functions are deleted.

### 6.2 Auto-start

A session begins on the first user message of a conversation. `session_id` is generated (UUID). The first user message is used as the topic query for `AgentContextStore.get_relevant()`. Retrieved summaries are injected as `prior_context` into the agent before the first API call — silently, with no "Prior context loaded" system message in the transcript.

### 6.3 Auto-summarize

Triggered when the user clicks "Clear". If `message_count >= 3` (user turns):
1. `SessionManager.end_session()` generates a Claude summary of the conversation.
2. Summary stored in `AgentContextStore` (ChromaDB `agent_context` collection).
3. A row is inserted into the `sessions` SQLite table with `inferred_topic`, `agent_mode`, timestamps, `summary_preview`, and `message_count`.
4. History is then cleared.

If fewer than 3 user turns, the conversation is cleared without summarizing.

---

## 7. UI Surfaces

### 7.1 Mode toggle (sidebar)

Three-option radio: **Local DB / External DB / Neuro-Tutor**. Replaces the current two-option toggle. No other sidebar changes in phase 1.

### 7.2 Knowledge Library page (new Streamlit page)

Two sections:

**Pending**: List of `knowledge_sources` rows with `status="pending"`, sorted by `queued_at` descending. Each row shows title, source type, topic context, queued date, and any semantic near-duplicate warning. Approve and Reject buttons per row. Approve triggers summary generation and ChromaDB embedding (with a spinner). Reject sets `status="rejected"`.

**Library**: List of `knowledge_sources` rows with `status="approved"`, sorted by `reviewed_at` descending. Each row shows title, source type, topic context, and summary preview. Full summary expandable inline.

### 7.3 Previous Topics panel (phase 2 — infrastructure only in phase 1)

The `sessions` table is populated in phase 1. The sidebar panel that displays it and allows topic selection is built in phase 2. This prevents a rushed UI from shipping before enough session data exists to make it useful.

---

## 8. Testing

- **Unit tests**: `BaseAgent` abstract method contract; `NeuroDbAgent` and `NeuroTutorAgent` instantiation; `queue_source` dedup logic (exact match by DOI and normalized title); `KnowledgeLibraryStore` add/search; auto-session trigger conditions (message count threshold).
- **Structural tests**: mode rename — no reference to `"learning"` or `"discovery"` strings in `chat.py`; `NeuroTutorAgent` tool list contains `search_knowledge_library`, `queue_source`, `search_literature`.
- **Integration tests**: full queue → approve → embed → retrieve cycle against SQLite + in-memory ChromaDB; auto-summarize triggered on Clear with ≥ 3 turns; not triggered with < 3 turns.
- **Existing tests**: all 210 current tests must continue to pass after the `agent.py` → `agents/db_agent.py` migration.

---

## 9. Out of Scope for Phase 1

- PubMed and Semantic Scholar live API calls (phase 2)
- Previous Topics sidebar panel UI (phase 2)
- Full-text source indexing / deep index (later phase)
- Research agent (`NeuroResearchAgent`) scaffolding (later phase)
- Hypothesis agent (later phase)
- User-editable topic labels for inferred session topics
