# NeuroDb Epoch Architecture — Design Spec

**Date:** 2026-05-07
**Status:** Approved
**Goals source:** `NeuroDbGoals.md`

---

## Goals

**Goal 1 — Accumulate Neuroscience Understanding**
Build compounding neuroscience knowledge through guided exploration — textbook-grounded, connected to real public datasets, and retained across sessions. The tutor grows with the user: each topic explored becomes part of a retrievable knowledge base that makes future learning faster and more connected.

**Goal 2 — Conduct Structured Neuroscience Investigations**
Apply tech and AI capability to conduct real neuroscience investigations using existing public datasets and good scientific method — forming testable hypotheses, gathering evidence from available data, and producing outputs that range from personal learning artifacts to potentially useful contributions to the field. Constrained to secondary and public data (no original collection). Differentiated by the user's software, AI, and product skills.

**The Feedback Loop That Connects Them**
Learning on a topic (Goal 1) naturally surfaces questions worth investigating (Goal 2). An investigation deepens understanding and generates new topics to learn. Neither goal is primary — they are two directions of the same loop. The system should support the user moving fluidly between *I want to understand this* and *I want to investigate this* without losing context.

---

## Epoch Overview

Six epochs. Each owns a distinct capability domain, carries its own backlog and issue register, and advances independently.

| Epoch | Primary role | Goal alignment | Current status |
|---|---|---|---|
| DB | Data substrate | Both | MVP complete (0–6); entity resolution and research storage schema next |
| Agent Core | Shared infrastructure | Both | Stable |
| Tutor | Goal 1 vehicle | Goal 1 | MVP complete (LT-1/2/3); open backlog |
| Research | Goal 2 vehicle | Goal 2 | Scaffolded (LT-3); deeper tooling next |
| UI | Workbench surface | Both | Streamlit MVP; FastAPI + React migration designed, not started |
| Config Control | Cross-cutting infrastructure | Both (cost control) | Architecture designed; not yet implemented |

---

## Epoch Definitions

### DB Epoch

**Owns:** Source connectors (OpenNeuro, Allen Brain Atlas, NeuroVault, DANDI), DuckDB schema, normalization transforms, merged views, query helper functions, provenance metadata, and all structured storage schemas — including `ModelCallLog` (telemetry), `HypothesisReview`, `ResearchHypothesis`, and future research artifact tables.

**Responsibility boundary:** The DB epoch stores; other epochs act. Schema decisions live here. Write logic that modifies data lives in helper functions owned by this epoch. No other epoch executes raw SQL or calls ORM methods directly.

**Interface to other epochs:** SQLAlchemy `engine` (injected into agents and helpers), named query helper functions, DuckDB views. ChromaDB collections are accessed only through named helper functions that own each collection — never by collection name string from outside the owning helper.

---

### Agent Core Epoch

**Owns:** `BaseAgent` abstract class, the conversation loop (`chat`, `chat_stream`), rollback and checkpoint logic, session persistence, streaming protocol, and the configuration injection point for model and provider.

**Four-part interface contract — all subclasses implement:**

| Method | Purpose |
|---|---|
| `_get_active_tools()` | Returns the tool list for this agent |
| `_build_system_prompt()` | Returns the system prompt for this agent |
| `_execute_tool_block(block)` | Dispatches a tool call and returns a result string |
| **Configuration injection** | Model identity (`str` now, `ModelClient` in Phase 4) is always passed in at construction from the call site — never read from env vars inside the class body |

The conversation loop, checkpoint/rollback logic, and streaming protocol are implemented once in `BaseAgent` and never re-implemented in subclasses.

**Session persistence:** Agent Core provides session storage. Subclasses do not manage session records directly.

---

### Tutor Epoch

**Owns:** `NeuroTutorAgent`, knowledge library (curation queue, approval workflow, embedding, retrieval), literature search (PubMed, Semantic Scholar), previous topics panel, session memory, and knowledge growth metrics.

**Write path ownership:** The Tutor epoch owns the write path to the knowledge library. It is the only epoch that writes to the `knowledge_sources` table and the `knowledge_library` ChromaDB collection.

**Interface to Research epoch:** The knowledge library is a queryable read surface for the Research epoch. Research reads via `search_knowledge_library()`. Research cannot call write operations on knowledge library storage. If a research investigation surfaces a source worth adding to the library, it goes through the Tutor curation queue — the same path a user would use.

**Open backlog:** LOG-001 (textbook dropdown ambiguity), LOG-006 (model visibility), LOG-014 (Semantic Scholar API key policy), LOG-030 (LT-3 header/title sizing).

---

### Research Epoch

**Owns:** `NeuroResearchAgent`, hypothesis tools, research questions, evidence tracking, research run management, hypothesis review capability, and research artifact storage.

**Read path on knowledge library:** Research reads from the Tutor epoch's knowledge library but does not write to it.

**DB schema dependency:** The DB epoch owns the storage schemas for research artifacts (`ResearchHypothesis`, `HypothesisReview`). The Research epoch owns the tooling and workflows that populate and query those schemas.

**Backlog:** Hypothesis review (premium critique step), stuck detection, evidence compaction, `ResearchRun` orchestration with progress UI.

**Feedback loop role:** Research findings surface new questions that return the user to the Tutor epoch. The knowledge library grows richer with each investigation cycle.

---

### UI Epoch

**Owns:** UI shell, routing, pane layout, streaming rendering, workbench state. Streamlit is the current implementation. FastAPI + React is the target architecture; migration path is documented in `docs/UI_EpochPlan.md`.

**Responsibility boundary:** The UI epoch does not own agent logic, session logic, or data logic. It calls through defined interfaces — currently direct Python helper calls (acceptable in Streamlit), eventually API routes (required in FastAPI + React).

**Target state:** No agent or DB object instantiated directly in the UI layer. All backend access through API routes.

---

### Configuration Control Epoch

**Owns:** Model and provider selection, provider adapters (`ModelClient` abstract interface, `AnthropicModelClient`, `OpenAIModelClient`), `TaskRouter`, config-driven model table (`neurodb_models.toml`), API key management, cost and capability gating, and telemetry-informed routing.

**Capability tiers:**

| Tier | Role | Task examples |
|---|---|---|
| `premium` | Deep scientific reasoning, synthesis under conflicting evidence | Hypothesis critique, final synthesis review, difficult confound identification |
| `standard` | Multi-step orchestration, domain-grounded judgment | SQL generation, tool-result interpretation, tutor explanation, hypothesis drafting |
| `economy` | Extraction, format adherence, template-fill from provided input | Session summary, knowledge library source summary, narrow search query formulation |

**Interface to Agent Core:** Pre-Phase 4 — env vars read at the call site, passed to agent constructors. Post-Phase 4 — `TaskRouter` returns `(ModelClient, model_id, max_tokens)`, passed to the constructor.

**Goal 2 cost model:** Research orchestration runs at standard tier. Only the bounded hypothesis review step uses the premium tier. The feedback loop does not get more expensive as it matures — it gets more capable at the same cost envelope.

**Telemetry task types:**

All model calls write a row to `model_call_log`. The `task_type` column is the primary filter for manual telemetry queries. The routing key passed to `TaskRouter.route()` and the telemetry `task_type` written to `model_call_log` are always the same string except for hypothesis review, which uses a shorter telemetry key.

| `task_type` (in `model_call_log`) | Tier | `max_tokens` | Produced by | Routing key |
|---|---|---|---|---|
| `agent.loop.local_db` | standard | 2048 | DB agent — local DB mode | same |
| `agent.loop.external_db` | standard | 2048 | DB agent — external DB mode | same |
| `agent.loop.neuro_tutor` | standard | 2048 | Tutor agent | same |
| `agent.loop.neuro_research` | standard | 4096 | Research agent loop | same |
| `agent.loop.unknown` | standard | 2048 | Fallback when `telemetry_mode` is None | same |
| `summary.session` | economy | 512 | `SessionManager.end_session()` | same |
| `summary.knowledge_source` | economy | 700 | Knowledge Library — source approval | same |
| `review.hypothesis` | premium | 4096 | `hypothesis_review.py` — hypothesis review action | `research.hypothesis_review` |

Note: `summary.knowledge` and `agent.loop.research` are defined in `neurodb_models.toml` but are not currently wired to any production code path.

---

## Interface Contracts

The only things that may cross an epoch boundary, and how.

### DB → All
- `engine` (SQLAlchemy, injected at construction) — read access for agents, write access only through helper functions
- Named query helper functions — the only sanctioned write path from non-DB epochs into the database
- No epoch calls `session.execute()` with raw SQL outside a DB-epoch helper function
- No epoch references a ChromaDB collection by its string name from outside the helper that owns that collection

### Agent Core → Tutor / Research
- The four-part contract above (three behavioral methods + configuration injection)
- Session storage provided by Agent Core; subclasses do not manage session records

### Config Control → Agent Core
- Pre-Phase 4: env vars read at call site, passed to agent constructor
- Post-Phase 4: `TaskRouter.route(task_type)` → `(ModelClient, model_id, max_tokens)` → passed to constructor
- **Hard rule:** No `os.environ.get("NEURODB_*")` inside any agent class body

### Tutor → Research (knowledge library)
- Research reads via `search_knowledge_library()` only
- Research contains no calls to ChromaDB `knowledge_library` collection write operations
- Research contains no writes to the `knowledge_sources` table

### Agent Core → DB (telemetry)
- `BaseAgent` writes one `ModelCallLog` row per model call
- This is the only point where Agent Core writes to a DB-epoch-owned schema
- Config Control reads telemetry to inform routing; it does not write it
- Telemetry writes must not raise exceptions or interrupt the agent loop

### UI → All (target state)
- Post-FastAPI: no agent or DB object instantiated directly in the UI layer
- All access through typed API routes
- Current Streamlit direct access is acceptable until UI-Phase UI-1

### Cross-epoch feature rule
When a feature spans two epochs: **the capability epoch owns the backlog story, the spec, the test plan, and the issue log entry. The infrastructure epoch owns the mechanism it depends on.**

Example: hypothesis review is a Research epoch story; the premium model routing is a Config Control mechanism. The research test plan covers the review capability; the Config Control implementation plan covers the routing.

---

## Coupling Protection Rules

Hard constraints, not conventions.

1. **No self-configuring agents.** Agents do not read env vars or config files internally. Configuration enters through the constructor only.
2. **No collection-by-name access.** Code outside an owning helper function does not reference a ChromaDB collection by its string name or call `.add()`, `.query()`, etc. directly.
3. **Research reads, Tutor writes.** Research epoch code contains no writes to `knowledge_sources` or `knowledge_library`. Additions to the library go through the Tutor curation queue.
4. **UI does not own agent state.** Session messages, tool results, and agent context live in the agent or Agent Core's session store — not in Streamlit session state or React component state.
5. **New modules get epoch-scoped directories.**

| Epoch | Directory |
|---|---|
| Agent Core | `src/neurodb/agents/` |
| Config Control | `src/neurodb/config/` and `src/neurodb/providers/` |
| Research | `src/neurodb/research/` |
| Tutor | `src/neurodb/tutor/` |
| DB | `src/neurodb/db/` (connectors, schema, query helpers) |
| UI | `src/neurodb/ui/` |

6. **Existing modules in transition.** Flat-layout modules (`research_tools.py`, `knowledge_library.py`, `session_manager.py`) are migrated to epoch-scoped directories when they are next significantly changed — not as a separate migration sprint. Until migrated, epoch ownership is declared in the module docstring.

---

## Feature and Issue Collection Per Epoch

**Backlog:** Each epoch plan doc (or a dedicated section in `projectStatus.md`) holds an open feature backlog for that epoch. Features do not live in a flat global list.

**Issue log:** `docs/testLog.md` remains the single issue log. Each entry is tagged with its epoch: `[DB]`, `[Agent Core]`, `[Tutor]`, `[Research]`, `[UI]`, `[Config]`. Existing open entries require epoch tags to be added when this framework is adopted.

**Test ownership:** Unit and integration tests are named by epoch concern. A test file that spans two epoch concerns is a signal that feature ownership needs clarification.

| Epoch | Test file naming pattern |
|---|---|
| Agent Core | `test_agent.py`, `test_base_*.py` |
| Tutor | `test_tutor_*.py`, `test_knowledge_library.py` |
| Research | `test_research_*.py`, `test_hypothesis*.py` |
| Config Control | `test_model_routing.py`, `test_task_router.py`, `test_model_client.py` |
| DB | `test_schema.py`, `test_ingest_*.py`, `test_connector_*.py` |
| UI | `test_chat_ui.py`, `test_research_ui.py` |

**Manual test plans:** Scoped to a single epoch's capability surface. A manual test plan that spans two epochs should be split. Manual test plans for completed epochs are archived in `docs/testsPlans/`.

**Maturity status per epoch:**

| Epoch | Status |
|---|---|
| DB | MVP complete |
| Agent Core | Stable |
| Tutor | MVP complete |
| Research | Scaffolded |
| UI | In progress (Streamlit); migration designed |
| Config Control | Designed; not yet implemented |

---

## Goal-to-Epoch Data Flow

```
Goal 1 — Accumulate understanding
    DB (datasets that ground concepts)
        → Agent Core (conversation infrastructure)
            → Tutor (knowledge library, literature, session memory)

Goal 2 — Conduct investigations
    DB (datasets as evidence + research storage schemas)
        → Agent Core (conversation infrastructure)
            → Research (hypothesis formation, evidence gathering)
                ← reads Tutor knowledge library

Feedback loop:
    Tutor accumulates knowledge
        → knowledge library becomes richer substrate
            → Research reads it, queries DB, forms hypotheses
                → findings surface new questions
                    → user returns to Tutor
                        → loop continues
```

Config Control sits across both flows — it determines which capability tier each task type receives and keeps the cost envelope stable as the feedback loop matures.

---

## Downstream Doc Updates Required on Adoption

These are not part of this spec's implementation — they are triggered when the epoch framework is formally adopted:

| Document | Required update |
|---|---|
| `docs/testLog.md` | Add epoch tag to all open issues |
| `docs/testsPlans/` manual test plans | Verify each plan is scoped to one epoch; split any that span two |
| `docs/projectStatus.md` | Restructure Active Work section by epoch |
| `docs/superpowers/plans/claudeTaskArch.md` | Add epoch labels to each phase and component |
| `docs/AgentCore_EpochPlan.md`, `docs/Tutor_EpochPlan.md`, `docs/Research_EpochPlan.md` | Created from extracted Learn epoch content — done |
| `docs/DB_EpochPlan.md` | Add epoch ownership context to DB phases 7–8 |

---

## References

| Document | Purpose |
|---|---|
| `NeuroDbGoals.md` | Restated project goals and feedback loop |
| `docs/AgentCore_EpochPlan.md` | Agent Core epoch — BaseAgent architecture, contract, configuration injection |
| `docs/Tutor_EpochPlan.md` | Tutor epoch — LT-1/2/3 phase history, Knowledge Library decisions, open backlog |
| `docs/Research_EpochPlan.md` | Research epoch — NeuroResearchAgent, hypothesis tools, open backlog |
| `docs/ConfigControl_EpochPlan.md` | Config Control epoch — phases 1–6, provider adapters, telemetry decisions |
| `docs/DB_EpochPlan.md` | DB epoch phase history (0–6) and deferred phases (7–8) |
| `docs/UI_EpochPlan.md` | UI epoch migration architecture |
| `docs/archive/LearnEpoch_historical.md` | Original Learning Epoch design doc (superseded; extracted into AgentCore + Tutor + Research plans) |
| `docs/superpowers/plans/claudeTaskArch.md` | Config Control — model routing design |
| `docs/superpowers/plans/2026-05-07-model-routing-impl.md` | Config Control — model routing implementation plan |
| `src/neurodb/agents/base.py` | Agent Core — current BaseAgent implementation |
