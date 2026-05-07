# NeuroDb Learning Epoch — Phased Design & Implementation Plan

> **Architecture note:** The agent architecture pattern and epoch definitions in this document are superseded by `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`. This document is retained as the historical record of LT-1/2/3 phase design and decisions.

---

## Executive Summary

**Last updated:** 2026-05-05

**Epoch goal:** Give the user a capable neuroscience learning partner — one that remembers what has been explored and builds on it, so learning compounds over time.

**What this epoch is:** The Learning Epoch adds a `NeuroTutorAgent` alongside the existing database query agent, both unified under a `BaseAgent` abstract class. The Neuro-Tutor surfaces candidate knowledge sources during conversations, accumulates curated summaries into a persistent retrieval library, and maintains cross-session memory automatically. As the user's understanding deepens, the agent's retrievable knowledge base grows with it. This epoch also establishes the agent architecture pattern — `BaseAgent` → specialized subclasses — that will support future research and hypothesis-generation agents.

**Relationship to DB Epoch:** The DB Epoch built the data platform (ingest, normalize, store, query). The Learning Epoch builds the learning layer on top of it. The two epochs are complementary: the Neuro-Tutor can draw on the local database as one of its knowledge sources, and future research agents will use both layers.

### Learning Epoch Phases

| Phase | Focus | Status | Tests |
|-------|-------|--------|-------|
| LT-1 | BaseAgent architecture, NeuroDbAgent rename, mode rename, auto-session, NeuroTutorAgent (core), knowledge library storage, source queuing, Knowledge Library UI | Not started | — |
| LT-2 | PubMed + Semantic Scholar live search, Previous Topics panel, semantic dedup at review, summary generation improvements | Not started | — |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | Not started | — |

### DB Epoch Phases (for reference)

| Phase | Status | Notes |
|-------|--------|-------|
| 0–6 | ✅ Complete | Data platform: ingest, normalize, DuckDB, NeuroVault/DANDI connectors |
| 7 — Entity resolution | ⏳ Decision pending | Re-run field-coverage audit post-Phase 6 merge |
| 8 — Hypothesis layer | ⏳ Not started | Pre-analysis plans, structured reports |

**Active data sources:** OpenNeuro, Allen Brain Atlas, NeuroVault, DANDI

---

## Agent Architecture Pattern

Every agent in this project inherits `BaseAgent` and implements three methods. This is the contract for all current and future agents.

```
src/neurodb/agents/
    base.py          ← BaseAgent: chat(), chat_stream(), rollback logic
    db_agent.py      ← NeuroDbAgent (Local DB / External DB modes)
    tutor_agent.py   ← NeuroTutorAgent (Neuro-Tutor mode)
    # future:
    # research_agent.py   ← NeuroResearchAgent
    # hypothesis_agent.py ← HypothesisAgent
```

**The three-method contract:**

| Method | Purpose |
|--------|---------|
| `_get_active_tools()` | Returns the tool list for this agent's mode |
| `_build_system_prompt()` | Returns the system prompt appropriate for this agent |
| `_execute_tool_block(block)` | Dispatches a tool call and returns a result string |

The conversation loop (`chat()`, `chat_stream()`), checkpoint/rollback logic, and streaming protocol are implemented once in `BaseAgent` and never re-implemented. Adding a new specialized agent means implementing these three methods and nothing else.

**Mode → Agent mapping (UI):**

| UI Label | Mode value | Agent class |
|----------|-----------|-------------|
| Local DB | `local_db` | `NeuroDbAgent(mode="local_db")` |
| External DB | `external_db` | `NeuroDbAgent(mode="external_db")` |
| Neuro-Tutor | `neuro_tutor` | `NeuroTutorAgent(...)` |

---

## Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | **Separate NeuroTutorAgent class, not a third mode on NeuroAgent** | The Tutor's retrieval strategy (RAG-first, per-query library search) is fundamentally different from the DB agent's (tool-first, dataset query). A shared class would require too many conditionals and a system prompt serving two masters. Separate classes enforce the architectural boundary and allow independent evolution. |
| 2026-05-05 | **BaseAgent abstract class from day one** | Establishes the pattern for future agents (Research, Hypothesis). The three-method contract is small to define now and expensive to retrofit later. |
| 2026-05-05 | **Remove explicit Start/End Session ceremony** | The session buttons were MVP scaffolding. Auto-start on first message and auto-summarize on Clear retain all the cross-session memory value while eliminating the friction. Topic inference from the first user message replaces user-typed topic entry. |
| 2026-05-05 | **Knowledge library: SQLite table + ChromaDB collection** | SQLite (`knowledge_sources`) handles structured metadata, status tracking, and dedup. ChromaDB (`knowledge_library`) handles semantic indexing and retrieval. Two stores, right job for each. Separating them avoids forcing ChromaDB into a structured-query role it isn't designed for. |
| 2026-05-05 | **Sessions SQLite table built in phase 1, Previous Topics UI deferred to phase 2** | The data needs to accumulate before the browsing UI is useful. Building the table now means the user enters phase 2 with real session history already stored. |
| 2026-05-05 | **search_literature distinct from search_external** | `search_external` (NeuroDbAgent) searches neuroscience dataset repositories (NeuroVault, DANDI). `search_literature` (NeuroTutorAgent) searches knowledge sources (papers, reviews, textbooks). Clean boundary — neither agent uses the other's external search tool. |
| 2026-05-05 | **Phase 1 search_literature uses training knowledge; phase 2 adds live APIs** | PubMed and Semantic Scholar API integration adds significant complexity. Phase 1 validates the full queue → curate → embed → retrieve loop using sources the agent already knows about. Phase 2 replaces the stub with live API calls once the pipeline is proven. |
| 2026-05-05 | **Minimum 3 user turns to store a session** | Short or accidental conversations produce low-quality summaries that pollute the Previous Topics list and the ChromaDB context store. The threshold filters noise without requiring user action. |

---

## Phase LT-1: Core Architecture + Neuro-Tutor Foundation

**Spec:** `docs/superpowers/specs/2026-05-05-neuro-tutor-epoch-design.md`

**Goal:** Stand up the BaseAgent architecture, migrate NeuroDbAgent, introduce NeuroTutorAgent with core knowledge library tools, replace session ceremony with auto-session, and deliver the Knowledge Library UI page.

### What ships in LT-1

**Agent layer:**
- `BaseAgent` abstract class (`agents/base.py`) — `chat()`, `chat_stream()`, rollback logic migrated from `agent.py`
- `NeuroDbAgent` (`agents/db_agent.py`) — direct migration of `NeuroAgent`; mode values renamed `local_db` / `external_db`
- `NeuroTutorAgent` (`agents/tutor_agent.py`) — new; tools: `search_knowledge_library`, `search_literature` (training-knowledge stub), `queue_source`, plus existing DB tools

**Storage:**
- `knowledge_sources` SQLite table — pending queue, approval status, summaries, chroma IDs
- `knowledge_library` ChromaDB collection — approved summaries, semantically indexed
- `sessions` SQLite table — session index (populated; UI deferred to LT-2)

**Session management:**
- Remove Start/End Session buttons from chat UI
- Auto-start on first message; auto-summarize on Clear (≥ 3 user turns)
- `sessions` row written on each completed session

**UI:**
- Mode toggle: Local DB / External DB / Neuro-Tutor (three options, renamed labels)
- Knowledge Library page: Pending queue (approve/reject, dedup warnings) + Library browser (approved sources)

**Tests:**
- BaseAgent contract tests
- NeuroDbAgent and NeuroTutorAgent instantiation and tool-list tests
- queue_source dedup logic (exact match by DOI and normalized title)
- Auto-session trigger conditions (message count threshold)
- Full queue → approve → embed → retrieve integration test
- Structural tests: mode rename, tool list membership
- All 210 existing tests continue to pass

### What does NOT ship in LT-1

- Live PubMed / Semantic Scholar API calls
- Previous Topics sidebar panel
- Semantic dedup at review time
- User-editable session topic labels

---

## Phase LT-2: Literature Search + Previous Topics

**Goal:** Replace the `search_literature` training-knowledge stub with live PubMed and Semantic Scholar API calls. Add the Previous Topics sidebar panel. Add semantic near-duplicate detection at review time.

### What ships in LT-2

- `search_literature` tool backed by PubMed API (abstracts, DOIs, authors) and Semantic Scholar (citation counts, open-access PDFs where available)
- Semantic near-duplicate detection: ChromaDB similarity query at Knowledge Library review time; near-duplicates flagged inline
- Previous Topics sidebar panel: collapsible list of past sessions from `sessions` table (date, inferred topic, mode badge, summary preview); selecting a session seeds ChromaDB retrieval and injects prior context; available only when conversation is empty
- User-editable session topic labels (correct inference errors)

---

## Phase LT-3: Research Agent Scaffolding

**Goal:** Introduce `NeuroResearchAgent` as the first demonstration that the `BaseAgent` pattern scales. Define the research agent's tool set and system prompt. Establish the bridge from the learning layer (Neuro-Tutor) to the research layer.

### Scope (to be designed)

- `NeuroResearchAgent` class inheriting `BaseAgent`
- Research-oriented tool set (hypothesis tools, structured literature review, dataset cross-reference)
- Integration with both the knowledge library (curated sources) and the local DB (dataset queries)
- Research mode UI surface

---

## Key Technical Facts

- **Backend:** DuckDB (`neurodb.duckdb`), SQLAlchemy 2.x ORM, Sequence-based PKs
- **Vector store:** ChromaDB persistent client; collections: `dataset_embeddings` (study notes), `agent_context` (session summaries), `knowledge_library` (curated source summaries — new in LT-1)
- **Agent model:** Configurable via `NEURODB_MODEL` env var; defaults to `claude-opus-4-7`
- **Session summaries:** ChromaDB `agent_context` collection; auto-generated by Claude on Clear; minimum 3 user turns
- **Knowledge library dedup:** Exact match (DOI or normalized title) at queue time; semantic similarity (cosine ≤ 0.15) at review time (LT-2)
- **agent.py migration:** `src/neurodb/agent.py` → `src/neurodb/agents/db_agent.py`; all import sites updated; original file removed
