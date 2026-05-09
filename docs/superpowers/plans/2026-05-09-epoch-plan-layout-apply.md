# Epoch Plan Doc Layout — Apply to All Six Epoch Docs

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Apply the approved BLUF two-zone template (`docs/superpowers/specs/2026-05-09-epoch-plan-layout-design.md`) to all six epoch plan docs.

**Architecture:** Doc-only changes. AgentCore, Tutor, Research, and Config Control need targeted updates (active work line, phases table columns, open backlog section). DB and UI are large historical docs that need archiving first, then replacement with concise BLUF docs.

**Tech Stack:** Markdown, git

---

### Task 1: Update AgentCore_EpochPlan.md

**Files:**
- Modify: `docs/AgentCore_EpochPlan.md`

- [ ] **Step 1: Overwrite with new content**

Replace the full file with:

```markdown
# NeuroDb — Agent Core Epoch Plan

**Status:** Stable — BaseAgent and ModelClient abstraction complete through Config Control Phase 4
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/agents/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Provide the shared conversation loop, tool dispatch, rollback, streaming, session persistence, and configuration injection that all specialized agents inherit. Adding a new agent means implementing three methods and nothing else.

**Active work:** None — stable. Config Control Phase 6 may add constructor fallback chain logic here.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-1 | BaseAgent abstract class, NeuroDbAgent migration, auto-session, streaming | Complete | — | 2026-05-05 | — |
| Config P4 | ModelClient abstraction — BaseAgent decoupled from Anthropic SDK; provider-neutral via `ModelClient` interface | Complete — manual evals pending | 389 (suite-wide) | — | `docs/testsPlans/manualTestPlan_config_phase4.md` |

Active test plan: `docs/testsPlans/manualTestPlan_config_phase4.md` (T1–T7 pending sign-off)

---

## Open Backlog

No open LOG entries currently assigned to Agent Core epoch.

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | BaseAgent abstract class from day one | The three-method contract is small to define early and expensive to retrofit later |
| 2026-05-05 | Auto-start and auto-summarize replace explicit session ceremony | Retains cross-session memory value while eliminating user friction |
| 2026-05-08 | ModelClient interface replaces direct Anthropic SDK calls in BaseAgent | BaseAgent calls `self._model_client.create_message()` — provider-neutral; clients injected at construction; no `os.environ` inside agent class bodies. See `docs/superpowers/plans/2026-05-07-model-routing-impl.md`. |

---

## Agent Classes + BaseAgent Contract

### Concrete agent classes

| Module | Class | Mode |
|--------|-------|------|
| `src/neurodb/agents/base.py` | `BaseAgent` | Abstract base |
| `src/neurodb/agents/db_agent.py` | `NeuroDbAgent` | `local_db`, `external_db` |
| `src/neurodb/agents/tutor_agent.py` | `NeuroTutorAgent` | `neuro_tutor` |
| `src/neurodb/agents/research_agent.py` | `NeuroResearchAgent` | `neuro_research` |

### Three-method contract (all subclasses implement)

| Method | Purpose |
|--------|---------|
| `_get_active_tools()` | Returns the tool list for this agent |
| `_build_system_prompt()` | Returns the system prompt for this agent |
| `_execute_tool_block(block)` | Dispatches a tool call and returns a result string |

The conversation loop (`chat()`, `chat_stream()`), checkpoint/rollback logic, and streaming protocol are implemented once in `BaseAgent` — never in subclasses.

### Configuration injection rule

No agent reads env vars or config files internally. Configuration enters through the constructor only. Pre-Phase 4: env vars read at the call site, passed in. Post-Phase 4: `TaskRouter.route(task_type)` returns `(ModelClient, model_id, max_tokens)`, passed to the constructor.
```

- [ ] **Step 2: Verify against template**

Check: status block present, active work line, phases table has all 6 columns, Open Backlog section, Key Decisions, epoch-specific section.

- [ ] **Step 3: Commit**

```bash
git add docs/AgentCore_EpochPlan.md
git commit -m "docs: apply BLUF layout to AgentCore epoch plan"
```

---

### Task 2: Update Tutor_EpochPlan.md

**Files:**
- Modify: `docs/Tutor_EpochPlan.md`

- [ ] **Step 1: Overwrite with new content**

Replace the full file with:

```markdown
# NeuroDb — Tutor Epoch Plan

**Status:** MVP complete (LT-1/2/3 signed off)
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/tutor/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Give the user a capable neuroscience learning partner that remembers what has been explored and builds on it, so learning compounds over time.

**Active work:** None — MVP complete. Open backlog items are deferred until a dedicated Tutor backlog sprint.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-1 | NeuroTutorAgent, Knowledge Library storage + UI, auto-session | Complete | — | 2026-05-05 | — |
| LT-2 | Live PubMed + Semantic Scholar search, Previous Topics panel, semantic dedup | Complete | — | 2026-05-06 | — |
| LT-3 | Research agent scaffolding (Tutor as foundation) | Complete | — | 2026-05-06 | — |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-001 | Textbook dropdown appears pre-selected without explicit user action |
| LOG-006 | User cannot tell which agent/LLM/model is active — deferred post-LT-3 |
| LOG-030 | LT-3 T2 passed but titles/headers render too large |
| LOG-041 | No UI path to view generated session summary |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | Separate NeuroTutorAgent class, not a third mode on NeuroDbAgent | RAG-first retrieval strategy is fundamentally different from tool-first DB agent; separate classes enforce the boundary and allow independent evolution |
| 2026-05-05 | Knowledge library: DuckDB table + ChromaDB collection | `knowledge_sources` handles structured metadata, status, and dedup; `knowledge_library` ChromaDB handles semantic indexing and retrieval |
| 2026-05-05 | Sessions table built in LT-1, Previous Topics UI deferred to LT-2 | Data needs to accumulate before the browsing UI is useful |
| 2026-05-05 | Minimum 3 user turns to store a session | Short conversations produce low-quality summaries that pollute the Previous Topics list |

---

## Owned Storage

| Store | Name | Purpose |
|-------|------|---------|
| DuckDB | `knowledge_sources` | Pending queue, approval status, summaries, chroma IDs |
| ChromaDB | `knowledge_library` | Approved summaries, semantically indexed |
| ChromaDB | `agent_context` | Session summaries for cross-session memory |
```

- [ ] **Step 2: Verify against template**

Check: status block, active work line, phases table 6 columns, Open Backlog, Key Decisions, epoch-specific section (Owned Storage).

- [ ] **Step 3: Commit**

```bash
git add docs/Tutor_EpochPlan.md
git commit -m "docs: apply BLUF layout to Tutor epoch plan"
```

---

### Task 3: Update Research_EpochPlan.md

**Files:**
- Modify: `docs/Research_EpochPlan.md`

- [ ] **Step 1: Overwrite with new content**

Replace the full file with:

```markdown
# NeuroDb — Research Epoch Plan

**Status:** Scaffolded (LT-3); hypothesis review with structured tool-use output
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/research/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Apply AI capability to conduct real neuroscience investigations using existing public datasets and good scientific method — forming testable hypotheses, gathering evidence from available data, and producing structured outputs.

**Active work:** None in active development. LOG-037, LOG-045, LOG-048 are open backlog. Research run management and research question actions are the next planned work.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-3 | NeuroResearchAgent scaffolding, knowledge growth metrics, hypothesis tools (`record_research_question`, `draft_hypothesis`) | Complete | — | 2026-05-06 | — |
| Config P3 | Research Synthesis Split — standard-tier research loop + premium hypothesis review via `submit_critique` tool-use | Complete | 350 (suite-wide) | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase3.md` |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-037 | No way to delete or act on existing research questions in the UI |
| LOG-045 | Research agent cannot nominate papers for Knowledge Library import — no bridge to Tutor curation queue |
| LOG-048 | No way to dismiss a draft hypothesis from the UI |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-06 | Research reads Knowledge Library; Tutor writes it | Clean epoch boundary; Research uses `search_knowledge_library()` only — nominations flow through the Tutor curation queue (LOG-045) |
| 2026-05-08 | Hypothesis review uses `submit_critique` tool-use to force structured output | LOG-044: premium model returned prose instead of JSON; tool-use with a defined schema forces structure regardless of model verbosity |
| 2026-05-09 | `evidence` and `datasets` tool schema items are typed objects with defined properties | Groq's strict validator rejects bare `{"type": "object"}` items; defined `{source, summary}` and `{dataset_id, relevance}` shapes give all providers unambiguous guidance and produce consistently queryable data |

---

## Owned Storage

| Store | Name | Purpose |
|-------|------|---------|
| DuckDB | `research_questions` | Questions, status, topic context |
| DuckDB | `research_hypotheses` | Title, mechanism, evidence, predictions, datasets, confounds, limitations, status |
| DuckDB | `hypothesis_reviews` | Critique, unsupported claims, missing confounds, suggested revisions, status |
```

- [ ] **Step 2: Verify against template**

Check: status block, active work line, phases table 6 columns, Open Backlog, Key Decisions, epoch-specific section (Owned Storage).

- [ ] **Step 3: Commit**

```bash
git add docs/Research_EpochPlan.md
git commit -m "docs: apply BLUF layout to Research epoch plan"
```

---

### Task 4: Update ConfigControl_EpochPlan.md

**Files:**
- Modify: `docs/ConfigControl_EpochPlan.md`

- [ ] **Step 1: Overwrite with new content**

Replace the full file with:

```markdown
# NeuroDb — Config Control Epoch Plan

**Status:** Phase 5B complete — 398 automated tests; Phase 4 manual evals pending (T1–T7)
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/config/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Own model and provider selection, capability tier routing, provider adapters, API key management, cost and capability gating, and telemetry-informed routing. Keep the cost envelope stable as the feedback loop matures — more capable, not more expensive.

**Active work:** Phase 4 manual evals (T1–T7) pending sign-off. Phase 6 (constructor fallback chain, SystemWarning table, CLI telemetry surface) planned after sign-off.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Phase 1 | Per-agent model env vars; summary model routing | Complete | 332 | 2026-05-07 | `docs/testsPlans/manualTestPlan_config_phase1.md` |
| Phase 2 | `model_call_log` telemetry for agent loops and summary calls | Complete | 344 | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase2.md` |
| Phase 3 | Research Synthesis Split — standard-tier loop + premium hypothesis review | Complete | 350 | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase3.md` |
| Phase 4 | `ModelClient` abstraction, `AnthropicModelClient`, `OpenAIModelClient`, `TaskRouter`, config-driven provider selection, `BaseAgent` refactor | Complete — manual evals pending | 389 | — | `docs/testsPlans/manualTestPlan_config_phase4.md` |
| Phase 5A | TOML corrected; 4-provider × 3-tier model table; Gemini wired; tool schemas fixed for OpenAI strict validation | Complete | 397 | 2026-05-08 | — |
| Phase 5B | TOML routing refactor — single `[routing]` section replaces env-var tier overrides | Complete | 398 | 2026-05-08 | — |
| Phase 6 | Constructor fallback chain, `SystemWarning` table, CLI telemetry surface | Planned — after Phase 4 sign-off | — | — | — |

Active test plan: `docs/testsPlans/manualTestPlan_config_phase4.md` (T1–T7 pending sign-off)

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-050 | Gemini premium model testing deferred — API account set up; further Gemini premium testing deferred |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-07 | Env vars for model selection (Phase 1); TOML for provider routing (Phase 4+) | Env vars sufficient for model name overrides; TOML gives tier × provider × model IDs, version tracking, and eval status in one file |
| 2026-05-08 | `ModelClient` abstract interface wraps all providers | BaseAgent becomes provider-neutral; adding a provider means implementing `ModelClient`, not modifying BaseAgent |
| 2026-05-08 | `GOOGLE_API_KEY` is the env var for Gemini | Google issues a single API key for Gemini; `GEMINI_API_KEY` was an internal naming error |
| 2026-05-09 | `stream_options={"include_usage": True}` required for OpenAI/Gemini streaming token counts | Without it the OpenAI streaming API does not emit a usage chunk; token counts are null in telemetry |

---

## Key Design Docs

| Document | Purpose |
|----------|---------|
| `docs/superpowers/plans/claudeTaskArch.md` | Capability tiers, per-agent env vars, provider abstraction design |
| `docs/superpowers/plans/2026-05-07-model-routing-impl.md` | Phased implementation plan — task checklists for Phases 1–4 |
| `docs/superpowers/plans/2026-05-08-config-phase5-provider-model-table.md` | Phase 5 design — 4-provider model table, Gemini wiring |
| `neurodb_models.toml` | Live config — tier/provider/task routing table and model IDs |

---

## Routing and Telemetry

### Capability Tiers

| Tier | Role | Task examples |
|------|------|---------------|
| `premium` | Deep scientific reasoning, synthesis under conflicting evidence | Hypothesis critique, final synthesis review |
| `standard` | Multi-step orchestration, domain-grounded judgment | SQL generation, tutor explanation, hypothesis drafting |
| `economy` | Extraction, format adherence, template-fill from provided input | Session summary, knowledge source summary, narrow search query |

### Telemetry Task Types

See the Telemetry task types table in `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` → Configuration Control Epoch section.
```

- [ ] **Step 2: Verify against template**

Check: status block, active work line, phases table has all 6 columns (including Sign-off and Test plan), "Active Manual Test Plan" section removed, Open Backlog with LOG-050, Key Decisions, epoch-specific section (Routing and Telemetry).

- [ ] **Step 3: Commit**

```bash
git add docs/ConfigControl_EpochPlan.md
git commit -m "docs: apply BLUF layout to Config Control epoch plan"
```

---

### Task 5: Archive DB historical content + write new DB_EpochPlan.md

`docs/DB_EpochPlan.md` is a large historical implementation plan (32K+ tokens) with per-phase task checklists. It is not useful as an epoch status doc. Archive the historical content and replace with a concise BLUF doc.

**Files:**
- Create: `docs/archive/DB_EpochPlan_historical.md` (git mv from current `docs/DB_EpochPlan.md`)
- Create: `docs/DB_EpochPlan.md` (new concise BLUF doc)

- [ ] **Step 1: Archive the current file**

```bash
git mv docs/DB_EpochPlan.md docs/archive/DB_EpochPlan_historical.md
```

- [ ] **Step 2: Write the new DB_EpochPlan.md**

Create `docs/DB_EpochPlan.md` with:

```markdown
# NeuroDb — DB Epoch Plan

**Status:** MVP complete (Phases 0–6); Phases 7–8 decision pending
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/db/`, `src/neurodb/connectors/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Build and maintain the local neuroscience data platform — source connectors, DuckDB schema, normalization transforms, merged views, and all structured storage schemas — that all other epochs depend on as their data substrate.

**Active work:** Phases 7 (entity resolution) and 8 (research storage schema) are next; both pending a scope decision based on Phase 6 field-coverage audit.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Phase 0 | Schema scaffolding, provenance, test harness | Complete | — | 2026-04-11 | — |
| Phase 1 | OpenNeuro connector — GraphQL, idempotent ingest | Complete | — | 2026-04-12 | — |
| Phase 2 | MVP Streamlit browser + search UI | Complete | — | 2026-04-12 | — |
| Phase 3 | Allen Brain Atlas connector + view-based merge | Complete | — | 2026-04-13 | — |
| Phase 4 | Query and analysis layer — CLI + SQL mode | Complete | — | 2026-04-13 | — |
| Phase 5 | DuckDB migration from SQLite | Complete | 35 | 2026-04-13 | — |
| Phase 6 | NeuroVault + DANDI connectors | Complete | 74 | 2026-04-13 | — |
| Phase 7 | Entity resolution — dedup across sources | Decision pending | — | — | — |
| Phase 8 | Research storage schema — hypothesis layer tables | Not started | — | — | — |

Active test plan: none

---

## Open Backlog

No open LOG entries currently assigned to DB epoch.

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-04-11 | SQLite for Phases 0–2 | Zero-install, portable, sufficient for MVP scale |
| 2026-04-11 | DuckDB for Phase 3+ | Columnar performance needed for analytical queries over multi-source merged datasets |
| 2026-04-11 | PostgreSQL excluded | No multi-user or server requirements in scope |
| 2026-04-13 | DANDI two-stage ingest | NWB files are large; separate REST ingest (stage 1) from NWB parse (stage 2); `enriched_at` column tracks enrichment state per record |
| 2026-04-13 | `DatasetIndex.run_id` immutable after insert | DuckDB FK limitation: cannot UPDATE any column on a FK-referenced row after child rows exist — source-specific table `run_id` tracks subsequent runs instead |

Historical phase detail and task checklists: `docs/archive/DB_EpochPlan_historical.md`

---

## Connectors + Owned Tables

### Source Connectors

| Connector | Source | Module |
|-----------|--------|--------|
| OpenNeuro | OpenNeuro GraphQL API | `src/neurodb/connectors/openneuro.py` |
| Allen Brain Atlas | Allen Institute REST API | `src/neurodb/connectors/allen_brain.py` |
| NeuroVault | NeuroVault REST API | `src/neurodb/connectors/neurovault.py` |
| DANDI | DANDI REST API + pynwb (two-stage) | `src/neurodb/connectors/dandi.py` |

### Schema Ownership

The DB epoch owns the schema for all DuckDB tables. Write paths belong to the epoch that owns the domain (noted below). No other epoch executes raw SQL or calls ORM methods directly outside a DB-epoch helper function.

| Table | Purpose | Write path |
|-------|---------|------------|
| `openneuro_datasets` | OpenNeuro study records | DB connectors |
| `allen_brain_studies` | Allen Brain Atlas study records | DB connectors |
| `neurovault_collections` | NeuroVault collection records | DB connectors |
| `dandi_dandisets` | DANDI dandiset records | DB connectors |
| `dataset_index` | Cross-source unified index | DB connectors |
| `provenance_events` | Ingest and transform audit log | DB helpers |
| `quality_events` | QA events per dataset record | DB helpers |
| `study_notes` | User-attached study annotations | DB helpers |
| `sessions` | Agent session records | Agent Core session helper |
| `knowledge_sources` | Tutor knowledge library metadata | Tutor epoch helpers |
| `model_call_log` | Telemetry — one row per model call | Agent Core `BaseAgent` |
| `research_questions` | Research question records | Research epoch tools |
| `research_hypotheses` | Hypothesis records | Research epoch tools |
| `hypothesis_reviews` | Hypothesis review records | Research epoch tools |

### Views

| View | Purpose |
|------|---------|
| `v_all_datasets` | UNION of all 4 source tables |
| `v_dataset_summary` | Aggregated count by source + modality |
```

- [ ] **Step 3: Verify against template**

Check: status block, active work line, phases table 6 columns, Open Backlog, Key Decisions with archive pointer, epoch-specific section (Connectors + Owned Tables).

- [ ] **Step 4: Commit**

```bash
git add docs/DB_EpochPlan.md docs/archive/DB_EpochPlan_historical.md
git commit -m "docs: apply BLUF layout to DB epoch plan; archive historical content"
```

---

### Task 6: Archive UI historical content + write new UI_EpochPlan.md

`docs/UI_EpochPlan.md` is a 358-line architecture analysis doc with options comparison, pros/cons, and open questions. The key decisions are now captured in the UI-0 ADR and the UI-1 implementation plan. Archive the historical content and replace with a concise BLUF doc.

**Files:**
- Create: `docs/archive/UI_EpochPlan_historical.md` (git mv from current `docs/UI_EpochPlan.md`)
- Create: `docs/UI_EpochPlan.md` (new concise BLUF doc)

- [ ] **Step 1: Archive the current file**

```bash
git mv docs/UI_EpochPlan.md docs/archive/UI_EpochPlan_historical.md
```

- [ ] **Step 2: Write the new UI_EpochPlan.md**

Create `docs/UI_EpochPlan.md` with:

```markdown
# NeuroDb — UI Epoch Plan

**Status:** Streamlit MVP; UI-0 ADR complete; UI-1 (FastAPI backend shell) planned, not started
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/ui/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Own the UI shell, routing, pane layout, streaming rendering, and workbench state. Current implementation is Streamlit. Target is a FastAPI + React workbench shell — migration is incremental with Streamlit retained until parity.

**Active work:** UI-1 implementation plan written and ready; not yet started. Manual test plan (`docs/testsPlans/manualTestPlan_ui1_api_shell.md`) ready for 8 API route evals.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Streamlit MVP | Streamlit shell — chat, research, knowledge library, sidebar | Complete | — | 2026-05-06 | — |
| UI-0 | Architecture decision record — FastAPI + React target confirmed; Streamlit retained during migration | Complete (ADR) | — | 2026-05-08 | — |
| UI-1 | FastAPI backend shell — app factory, 8 API routes, SSE chat PoC | Not started | — | — | `docs/testsPlans/manualTestPlan_ui1_api_shell.md` |
| UI-2 | React workbench prototype — activity rail, resizable panes, chat streaming, research panel | Planned | — | — | — |
| UI-3 | Parity migration — Streamlit surfaces moved to React one at a time | Planned | — | — | — |
| UI-4 | Streamlit retirement decision | Planned | — | — | — |

Active test plan: `docs/testsPlans/manualTestPlan_ui1_api_shell.md` (8 curl-based evals for UI-1 API routes — pending UI-1 implementation)

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-013 | UI shell rearchitecture — deferred post-LT-3; addressed by UI-0 ADR and UI-1 plan |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-08 | FastAPI + React as target shell; Streamlit retained until parity | Workbench ergonomics (persistent panes, independent scroll, routing, streaming) require React; rewrite is incremental — Streamlit is not retired until replacement has parity. See `docs/superpowers/plans/2026-05-08-ui1-backend-api-shell.md`. |
| 2026-05-08 | UI does not own agent or session state | Session messages, tool results, and agent context live in the agent or Agent Core's session store — not in Streamlit session state or React component state |
| (deferred) | Provider selection UI for tier routing | Settings panel with three provider dropdowns (Economy, Standard, Premium) — deferred until FastAPI + React shell exists; current control is editing `neurodb_models.toml` `[routing]` section directly |

Historical options analysis and pros/cons: `docs/archive/UI_EpochPlan_historical.md`

---

## Technology Stack

| Layer | Current | Target | Phase |
|-------|---------|--------|-------|
| UI shell | Streamlit | React (Vite or framework) | UI-2 |
| Backend API | None (direct Python calls) | FastAPI | UI-1 |
| Agent streaming | Streamlit rerun | SSE or WebSocket | UI-1 |
| State management | `st.session_state` | React component + server state | UI-2 |
| SQL workspace | Streamlit textarea | React panel (Monaco deferred) | UI-3 |
```

- [ ] **Step 3: Verify against template**

Check: status block, active work line, phases table 6 columns, Open Backlog, Key Decisions with archive pointer, epoch-specific section (Technology Stack).

- [ ] **Step 4: Commit**

```bash
git add docs/UI_EpochPlan.md docs/archive/UI_EpochPlan_historical.md
git commit -m "docs: apply BLUF layout to UI epoch plan; archive historical content"
```

---

### Task 7: Update projectStatus.md reference table

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Verify references still accurate**

Check that the Key References table in `docs/projectStatus.md` points to the correct file paths for all six epoch plans. If any paths changed (DB or UI moved to archive + replaced), update those rows.

Expected entries — verify each file exists:
- `docs/AgentCore_EpochPlan.md`
- `docs/Tutor_EpochPlan.md`
- `docs/Research_EpochPlan.md`
- `docs/ConfigControl_EpochPlan.md`
- `docs/DB_EpochPlan.md`
- `docs/UI_EpochPlan.md`

Also verify `docs/projectStatus.md` "Last updated" date and "Active focus" line are current.

- [ ] **Step 2: Commit any changes**

```bash
git add docs/projectStatus.md
git commit -m "docs: update projectStatus references after epoch plan layout apply"
```

If no changes were needed, skip this commit.
