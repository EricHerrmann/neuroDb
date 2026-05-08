# Epoch Framework Adoption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Adopt the epoch architecture framework across docs, issue tracking, source directories, and module ownership declarations — no feature code changes, no module moves.

**Architecture:** Two phases. Phase A updates all documentation to reflect epoch structure (issue log, project status, legacy epoch plans, model routing plan, manual test plans). Phase B creates epoch-scoped directory stubs and adds epoch ownership docstrings to existing flat-layout modules. Module moves happen when each module is next significantly changed, not now.

**Tech Stack:** Python (docstrings only), Markdown, git

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `docs/testLog.md` | Add Epoch column; tag open issues; move pass-record entries to Resolved |
| Modify | `docs/projectStatus.md` | Replace phase-sequence Active Work table with epoch status table |
| Modify | `docs/superpowers/plans/claudeTaskArch.md` | Add epoch owner annotation to each phase and component section |
| Modify | `docs/ClaudeLearnEpochPlan.md` | Add superseded-by header note |
| Modify | `docs/ClaudeDbEpochPlan.md` | Add epoch ownership context note |
| Modify | `docs/testsPlans/manualTestPlan_agent_lt1.md` | Add epoch scope header |
| Modify | `docs/testsPlans/manualTestPlan_pre_lt2_layout.md` | Add epoch scope header |
| Modify | `docs/testsPlans/manualTestPlan_agent_lt2.md` | Add epoch scope header |
| Modify | `docs/testsPlans/manualTestPlan_agent_lt3.md` | Add epoch scope header + two-epoch span note |
| Create | `src/neurodb/db/__init__.py` | DB epoch directory stub |
| Create | `src/neurodb/config/__init__.py` | Config Control epoch directory stub |
| Create | `src/neurodb/research/__init__.py` | Research epoch directory stub |
| Create | `src/neurodb/tutor/__init__.py` | Tutor epoch directory stub |
| Modify | `src/neurodb/schema.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/migrations.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/db.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/provenance.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/query.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/embedder.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/embed_hooks.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/enrichment.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/study.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/vector_store.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/session_manager.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/knowledge_store.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/literature_client.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/chapter_registry.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/research_tools.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/discovery_tools.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/prefs.py` | Add epoch ownership docstring |
| Modify | `src/neurodb/connectors/__init__.py` | Add epoch ownership docstring + migration note |

---

## Phase A — Documentation Updates

---

### Task A1: Clean up testLog.md

**What:** Add an Epoch column to the Summary and Open tables. Tag each open issue with its epoch. Move pass-record entries (not real issues) from Open to Resolved.

**Files:**
- Modify: `docs/testLog.md`

- [ ] **Step 1: Read testLog.md**

Open `docs/testLog.md` and confirm the current Open table has these entries: LOG-001, LOG-006, LOG-013, LOG-014, LOG-029, LOG-030, LOG-031, LOG-032, LOG-033, LOG-037, LOG-038, LOG-039.

- [ ] **Step 2: Update the Open Issues Summary table**

Replace the Summary table with:

```markdown
## Open Issues Summary

| Log ID | Issue ID | Epoch | Description | Priority |
|--------|----------|-------|-------------|----------|
| LOG-001 | P6-selector | Tutor | Textbook dropdown appears pre-selected without explicit user action — agent context state is ambiguous | Deferred post-LT-3 |
| LOG-006 | LT1-model-visibility | Config | User cannot tell which agent/LLM/model is active; no model selection or persistent preference rules | Deferred post-LT-3 |
| LOG-013 | UI-shell-rearchitecture | UI | Streamlit cannot support fixed-pane app-shell behavior; reassess UI stack after LT-3 | Deferred post-LT-3 |
| LOG-014 | semscholar-no-apikey | Tutor | Semantic Scholar does not issue API keys to non-academic accounts; connector setup docs and architecture must reflect source-dependent key requirements | Next arch update |
| LOG-030 | lt3-t2-pass-header-size | UI | LT-3 T2 passed, but titles/headers render too large | UI polish |
| LOG-037 | lt3-t6-research-question-actions | Research | Research pane shows several research questions, but there is no way to delete or use them | Post-LT-3 polish |
```

- [ ] **Step 3: Update the Open detail table**

Replace the Open table header row with:

```markdown
| Log ID | Date | Issue ID | Epoch | Description | Context |
|---|---|---|---|---|---|
```

Add the Epoch column value to each **real issue** row:

```markdown
| LOG-001 | 2026-05-04 | P6-selector | Tutor | Textbook dropdown appears pre-selected without explicit user action — actual agent context is ambiguous | P6 manual test |
| LOG-006 | 2026-05-05 | LT1-model-visibility | Config | User cannot tell which agent/LLM/model is active; later work should add model selection and persistent model/user-preference prompt rules | LT-1 manual/ad hoc review |
| LOG-013 | 2026-05-05 | UI-shell-rearchitecture | UI | Pre-LT-2 fixed-pane layout failed in Streamlit even with a custom-component bridge; evaluate a UI tech-stack rearchitecture after LT-2/LT-3 once core learning capabilities mature to MVP | Pre-LT-2 manual test |
| LOG-014 | 2026-05-06 | semscholar-no-apikey | Tutor | Semantic Scholar does not issue API keys to non-academic (gmail.com) accounts; unauthenticated rate limit appears sufficient for current use, but connector design and architecture docs must reflect that API keys are source-dependent and not universally required | Ad hoc discovery |
| LOG-030 | 2026-05-06 | lt3-t2-pass-header-size | UI | LT-3 T2 passed, agent has correct date and knows context; minor UI fix: reduce titles/headers font, it is too big | LT-3 manual testing |
| LOG-037 | 2026-05-06 | lt3-t6-research-question-actions | Research | T6: Research pane shows several research questions, but there is no way to delete or use them | LT-3 manual testing |
```

- [ ] **Step 4: Move pass-record entries to Resolved**

Remove LOG-029, LOG-031, LOG-032, LOG-033, LOG-038, LOG-039 from the Open table. Add them to the Resolved table with `Resolution: Test pass — not an issue` and the epoch tag `[LT-3]`:

```markdown
| LOG-029 | 2026-05-06 | t1-pass | LT-3 T1 pass record | Test pass — not an issue |
| LOG-031 | 2026-05-06 | lt3-t3-pass | LT-3 T3 pass record | Test pass — not an issue |
| LOG-032 | 2026-05-06 | lt3-t4-pass | LT-3 T4 pass record | Test pass — not an issue |
| LOG-033 | 2026-05-06 | lt3-t5-pass | LT-3 T5 pass record | Test pass — not an issue |
| LOG-038 | 2026-05-06 | lt3-t6-pass | LT-3 T6 pass record | Test pass — not an issue |
| LOG-039 | 2026-05-06 | lt3-t7-pass | LT-3 T7 pass record | Test pass — not an issue |
```

- [ ] **Step 5: Commit**

```bash
git add docs/testLog.md
git commit -m "docs: add epoch tags to issue log; move pass records to resolved"
```

---

### Task A2: Restructure projectStatus.md Active Work section

**What:** Replace the learning-epoch-centric phase table with an epoch status table. Keep Completed, Tech Debt, and Open Issues sections intact.

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Replace the Active Work section header and table**

Replace this block:

```markdown
## Active Work — Learning Epoch

| Phase | Focus | Status |
|-------|-------|--------|
| LT-1 | BaseAgent architecture, NeuroDbAgent rename, mode rename, auto-session, NeuroTutorAgent core, knowledge library storage + UI | Complete — 255 tests — signed off 2026-05-05 |
| Pre-LT-2 | Sidebar migration complete; fixed-pane Streamlit layout failed manual test and is deferred to UI shell architecture | Closed/deferred — 262 tests |
| LT-2 | LiteratureSearchClient (PubMed + Semantic Scholar), Previous Topics panel, sidebar config extensions, semantic dedup, Knowledge Library polish, connector visibility | Complete — 278 tests — signed off 2026-05-06 |
| LT-3 | Research agent scaffolding, knowledge growth metrics, hypothesis tools | Complete — 319 tests — signed off 2026-05-06 |
| UI Shell | UI tech-stack architecture for fixed workbench behavior after LT-2/LT-3 MVP capability maturity | Deferred post-LT-3 |
| CF-1 | Connector framework architecture — plugin system for adding connectors without rework | Planned post-LT-2 |
```

With:

```markdown
## Epoch Status

| Epoch | Maturity | Next |
|---|---|---|
| DB | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | Stable | Config Control Phase 4 — ModelClient interface refactor |
| Tutor | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-014, LOG-030 |
| Research | Scaffolded (LT-3); hypothesis review implemented | Review-output structured JSON hardening (LOG-044), research run management, research question actions (LOG-037) |
| UI | Streamlit MVP; migration designed | UI-0 architecture decision, FastAPI + React vertical slice |
| Config Control | Phase 3 complete — 350 automated tests plus 4 manual evals passed; signed off 2026-05-08 | Phase 4: ModelClient interface refactor |
```

- [ ] **Step 2: Update the "Next" header line**

Change:

```markdown
**Next:** UI Shell architecture and deferred polish triage
```

To:

```markdown
**Next:** Config Control Phase 4 (ModelClient interface refactor) — see `docs/superpowers/plans/2026-05-07-model-routing-impl.md`
```

- [ ] **Step 3: Update Last updated date**

```markdown
**Last updated:** 2026-05-08
```

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: restructure project status Active Work section by epoch"
```

---

### Task A3: Add epoch labels to model routing plan

**What:** Add a one-line `**Epoch owner:**` annotation at the top of each Phase section and each Component section in `docs/superpowers/plans/claudeTaskArch.md`.

**Files:**
- Modify: `docs/superpowers/plans/claudeTaskArch.md`

- [ ] **Step 1: Add epoch owner to Phase 1 section**

Find `### Phase 1 — Per-agent env vars (Anthropic MVP)` and add immediately after the heading:

```markdown
**Epoch owner:** Config Control — changes touch Agent Core (BaseAgent construction), Tutor (NeuroTutorAgent, knowledge_library.py), and Research (NeuroResearchAgent) through their construction interfaces only.
```

- [ ] **Step 2: Add epoch owner to Phase 2 section**

Find `### Phase 2 — Cost telemetry` and add:

```markdown
**Epoch owner:** Config Control (feature), Agent Core (BaseAgent instrumentation), DB (ModelCallLog schema and storage).
```

- [ ] **Step 3: Add epoch owner to Phase 3 section**

Find `### Phase 3 — Research synthesis split` and add:

```markdown
**Epoch owner:** Research (hypothesis review capability — the feature story), Config Control (premium model routing — the mechanism), DB (HypothesisReview schema).
```

- [ ] **Step 4: Add epoch owner to Phase 4 section**

Find `### Phase 4 — Provider abstraction + config-driven model table` and add:

```markdown
**Epoch owner:** Config Control (ModelClient, TaskRouter, neurodb_models.toml, provider adapters), Agent Core (BaseAgent refactor to accept ModelClient at construction).
```

- [ ] **Step 5: Add epoch owner to each Component section**

Find and add after each `### N.` component heading:

After `### 1. Capability Tier Env Vars`:
```markdown
**Epoch:** Config Control
```

After `### 2. Telemetry`:
```markdown
**Epoch:** Config Control (feature + feedback loop), Agent Core (instrumentation in BaseAgent), DB (ModelCallLog table)
```

After `### 3. Research Synthesis Split`:
```markdown
**Epoch:** Research (capability story), Config Control (routing mechanism), DB (HypothesisReview table)
```

After `### 4. ModelClient Abstraction`:
```markdown
**Epoch:** Config Control (interface + provider adapters), Agent Core (BaseAgent accepts ModelClient at construction)
```

After `### 5. Config-Driven Model Table`:
```markdown
**Epoch:** Config Control
```

After `### 6. TaskRouter`:
```markdown
**Epoch:** Config Control
```

- [ ] **Step 6: Commit**

```bash
git add docs/superpowers/plans/claudeTaskArch.md
git commit -m "docs: add epoch owner labels to model routing design plan"
```

---

### Task A4: Add superseded-by notes to legacy epoch plan docs

**What:** `docs/ClaudeLearnEpochPlan.md` and `docs/ClaudeDbEpochPlan.md` were written before the epoch architecture framework. Add a header note to each pointing to the epoch architecture spec for architectural guidance. The phase history in these docs remains valid as a record.

**Files:**
- Modify: `docs/ClaudeLearnEpochPlan.md`
- Modify: `docs/ClaudeDbEpochPlan.md`

- [ ] **Step 1: Add superseded note to ClaudeLearnEpochPlan.md**

Open the file and add immediately after the `# NeuroDb Learning Epoch — Phased Design & Implementation Plan` heading:

```markdown
> **Architecture note:** The agent architecture pattern and epoch definitions in this document are superseded by `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`. This document is retained as the historical record of LT-1/2/3 phase design and decisions.
```

- [ ] **Step 2: Add epoch context note to ClaudeDbEpochPlan.md**

Open the file and add immediately after the `# NeuroDb DB Epoch — Phased Design & Implementation Plan` heading:

```markdown
> **Architecture note:** The DB epoch's role, interface contracts, and directory target (`src/neurodb/db/`) are defined in `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`. This document is retained as the historical record of DB phases 0–6 design and decisions. Phases 7 (entity resolution) and 8 (research storage schema) are the active next steps for the DB epoch.
```

- [ ] **Step 3: Commit**

```bash
git add docs/ClaudeLearnEpochPlan.md docs/ClaudeDbEpochPlan.md
git commit -m "docs: add epoch architecture superseded-by notes to legacy epoch plans"
```

---

### Task A5: Add epoch scope headers to manual test plans

**What:** Add a one-line epoch scope header to each manual test plan so it is clear which epoch the plan tests. The LT-3 plan spans Tutor and Research — note this explicitly.

**Files:**
- Modify: `docs/testsPlans/manualTestPlan_agent_lt1.md`
- Modify: `docs/testsPlans/manualTestPlan_pre_lt2_layout.md`
- Modify: `docs/testsPlans/manualTestPlan_agent_lt2.md`
- Modify: `docs/testsPlans/manualTestPlan_agent_lt3.md`

- [ ] **Step 1: Add epoch scope to LT-1 plan**

Open `docs/testsPlans/manualTestPlan_agent_lt1.md`. Add immediately after the document title:

```markdown
**Epoch scope:** Tutor — tests NeuroTutorAgent, knowledge library storage, auto-session, and Agent Core BaseAgent architecture.
```

- [ ] **Step 2: Add epoch scope to Pre-LT-2 layout plan**

Open `docs/testsPlans/manualTestPlan_pre_lt2_layout.md`. Add:

```markdown
**Epoch scope:** UI — tests sidebar migration and layout behavior.
```

- [ ] **Step 3: Add epoch scope to LT-2 plan**

Open `docs/testsPlans/manualTestPlan_agent_lt2.md`. Add:

```markdown
**Epoch scope:** Tutor — tests live literature search (PubMed/Semantic Scholar), Previous Topics panel, knowledge library polish, and session memory.
```

- [ ] **Step 4: Add epoch scope to LT-3 plan**

Open `docs/testsPlans/manualTestPlan_agent_lt3.md`. Add:

```markdown
**Epoch scope:** Tutor + Research — this plan spans two epochs. Tutor: knowledge growth metrics. Research: NeuroResearchAgent, research questions, hypothesis drafting. Future test plans should be scoped to a single epoch.
```

- [ ] **Step 5: Commit**

```bash
git add docs/testsPlans/
git commit -m "docs: add epoch scope headers to all manual test plans"
```

---

## Phase B — Code Organization

---

### Task B1: Create epoch-scoped directory stubs

**What:** Create `__init__.py` files for the four new epoch directories. These are stubs — no modules are moved now. The docstring in each stub explains what belongs there and what the migration path is.

**Files:**
- Create: `src/neurodb/db/__init__.py`
- Create: `src/neurodb/config/__init__.py`
- Create: `src/neurodb/research/__init__.py`
- Create: `src/neurodb/tutor/__init__.py`

- [ ] **Step 1: Create src/neurodb/db/__init__.py**

```python
"""DB epoch — data substrate for all NeuroDb epochs.

This package is the target home for all DB epoch modules. Current flat-layout
modules migrate here when next significantly changed:

  schema.py       → db/schema.py
  migrations.py   → db/migrations.py
  db.py           → db/connection.py
  provenance.py   → db/provenance.py
  query.py        → db/query.py
  embedder.py     → db/embedder.py
  embed_hooks.py  → db/embed_hooks.py
  enrichment.py   → db/enrichment.py
  study.py        → db/study.py
  vector_store.py → db/vector_store.py
  connectors/     → db/connectors/

Interface to other epochs: SQLAlchemy engine (injected), named query helper
functions, DuckDB views. No other epoch executes raw SQL or calls ORM methods
directly outside a helper in this package.
"""
```

- [ ] **Step 2: Create src/neurodb/config/__init__.py**

```python
"""Config Control epoch — model routing, provider abstraction, capability gating.

This package is the target home for all Config Control epoch modules.
Planned modules (not yet implemented):

  config/model_client.py      — ModelClient ABC and normalized response types
  config/task_router.py       — TaskRouter: task_type → (ModelClient, model_id, max_tokens)
  config/model_config.py      — reads neurodb_models.toml
  config/providers/
    anthropic_client.py       — AnthropicModelClient
    openai_client.py          — OpenAIModelClient (also covers Groq)

Existing flat-layout modules that migrate here when next significantly changed:
  prefs.py → config/prefs.py

Interface to Agent Core: TaskRouter.route(task_type) returns
(ModelClient, model_id, max_tokens) for injection at agent construction.
No agent reads env vars or config files internally.
"""
```

- [ ] **Step 3: Create src/neurodb/research/__init__.py**

```python
"""Research epoch — Goal 2 capability: hypothesis formation, evidence tracking,
research run management.

This package is the target home for all Research epoch modules.
Current flat-layout modules migrate here when next significantly changed:

  research_tools.py  → research/tools.py
  discovery_tools.py → research/discovery.py

Planned modules (not yet implemented):
  research/hypothesis_review.py — premium-tier hypothesis critique

Interface to Tutor epoch: reads knowledge library via search_knowledge_library()
only. Research epoch code contains no writes to knowledge_sources or the
knowledge_library ChromaDB collection.

Interface to DB epoch: reads/writes research artifact tables (ResearchHypothesis,
HypothesisReview) through DB epoch helper functions only.
"""
```

- [ ] **Step 4: Create src/neurodb/tutor/__init__.py**

```python
"""Tutor epoch — Goal 1 capability: knowledge library, literature search,
chapter registry, session memory.

This package is the target home for all Tutor epoch modules.
Current flat-layout modules migrate here when next significantly changed:

  knowledge_store.py   → tutor/knowledge_store.py
  literature_client.py → tutor/literature_client.py
  chapter_registry.py  → tutor/chapter_registry.py

Ownership: the Tutor epoch owns the write path to the knowledge library.
It is the only epoch that writes to the knowledge_sources table and the
knowledge_library ChromaDB collection.
"""
```

- [ ] **Step 5: Run existing tests to confirm nothing broke**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: all 319 tests pass. The stubs add no imports so no regressions are possible, but confirm before committing.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db/__init__.py src/neurodb/config/__init__.py src/neurodb/research/__init__.py src/neurodb/tutor/__init__.py
git commit -m "feat: add epoch-scoped directory stubs (db, config, research, tutor)"
```

---

### Task B2: Add epoch ownership docstrings to flat-layout modules

**What:** Add or update the module-level docstring in each flat-layout module in `src/neurodb/` to declare its epoch owner. This is the lightweight signal for epoch ownership until each module migrates to its epoch directory.

**Files:** All flat-layout modules in `src/neurodb/` root.

- [ ] **Step 1: Update schema.py**

Open `src/neurodb/schema.py`. Replace or prepend the module docstring with:

```python
"""DB epoch — ORM schema definitions for all NeuroDb structured storage.

Owns: all SQLAlchemy ORM models including source tables, DatasetIndex,
StudyNote, ChatSession, KnowledgeSource, ResearchHypothesis, HypothesisReview,
ModelCallLog, and any future research artifact tables.

Migration target: src/neurodb/db/schema.py
"""
```

- [ ] **Step 2: Update migrations.py**

```python
"""DB epoch — schema migration utilities.

Migration target: src/neurodb/db/migrations.py
"""
```

- [ ] **Step 3: Update db.py**

```python
"""DB epoch — database connection and initialization.

Migration target: src/neurodb/db/connection.py
"""
```

- [ ] **Step 4: Update provenance.py**

```python
"""DB epoch — provenance and lineage metadata helpers.

Migration target: src/neurodb/db/provenance.py
"""
```

- [ ] **Step 5: Update query.py**

```python
"""DB epoch — query helper functions over the DuckDB analytical store.

Migration target: src/neurodb/db/query.py
"""
```

- [ ] **Step 6: Update embedder.py**

```python
"""DB epoch — embedding generation and ChromaDB write helpers.

Migration target: src/neurodb/db/embedder.py
"""
```

- [ ] **Step 7: Update embed_hooks.py**

```python
"""DB epoch — embedding trigger hooks called on dataset write paths.

Migration target: src/neurodb/db/embed_hooks.py
"""
```

- [ ] **Step 8: Update enrichment.py**

```python
"""DB epoch — data enrichment transforms applied after initial ingest.

Migration target: src/neurodb/db/enrichment.py
"""
```

- [ ] **Step 9: Update study.py**

```python
"""DB epoch — study tag operations and study note persistence.

Migration target: src/neurodb/db/study.py
"""
```

- [ ] **Step 10: Update vector_store.py**

```python
"""DB epoch — ChromaDB collection management and initialization.

Owns: collection creation, client initialization, and the collection
name registry. All epochs access ChromaDB collections through helpers
in this module — never by collection name string directly.

Migration target: src/neurodb/db/vector_store.py
"""
```

- [ ] **Step 11: Update session_manager.py**

```python
"""Agent Core epoch — session lifecycle management.

Owns: ChatSession row creation, session summary generation, and
cross-session context retrieval. Called by BaseAgent; subclasses
do not manage session records directly.

Migration target: src/neurodb/agents/session_manager.py
"""
```

- [ ] **Step 12: Update knowledge_store.py**

```python
"""Tutor epoch — knowledge library storage and retrieval.

Owns the write path to the knowledge library: curation queue,
approval workflow, embedding, and semantic retrieval. The Research
epoch reads from this store via search_knowledge_library() only —
it does not call write operations here directly.

Migration target: src/neurodb/tutor/knowledge_store.py
"""
```

- [ ] **Step 13: Update literature_client.py**

```python
"""Tutor epoch — live literature search client (PubMed, Semantic Scholar).

Migration target: src/neurodb/tutor/literature_client.py
"""
```

- [ ] **Step 14: Update chapter_registry.py**

```python
"""Tutor epoch — textbook chapter registry and context helpers.

Migration target: src/neurodb/tutor/chapter_registry.py
"""
```

- [ ] **Step 15: Update research_tools.py**

```python
"""Research epoch — hypothesis tools, research question persistence,
and evidence tracking helpers.

Migration target: src/neurodb/research/tools.py
"""
```

- [ ] **Step 16: Update discovery_tools.py**

```python
"""Research epoch — dataset discovery tools for research workflows.

Migration target: src/neurodb/research/discovery.py
"""
```

- [ ] **Step 17: Update prefs.py**

```python
"""Config Control epoch — user preference storage and retrieval.

Stores user-configurable preferences that affect agent behavior
(agent mode, model preferences). Read by the UI layer and agent
construction call sites.

Migration target: src/neurodb/config/prefs.py
"""
```

- [ ] **Step 18: Update connectors/__init__.py**

```python
"""DB epoch — source connector registry.

All connector modules in this package belong to the DB epoch.

Migration target: src/neurodb/db/connectors/
"""
```

- [ ] **Step 19: Run tests to confirm nothing broke**

```bash
uv run pytest tests/ -q --tb=short
```

Expected: all 319 tests pass. Docstring changes do not affect runtime behavior.

- [ ] **Step 20: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/migrations.py src/neurodb/db.py \
        src/neurodb/provenance.py src/neurodb/query.py src/neurodb/embedder.py \
        src/neurodb/embed_hooks.py src/neurodb/enrichment.py src/neurodb/study.py \
        src/neurodb/vector_store.py src/neurodb/session_manager.py \
        src/neurodb/knowledge_store.py src/neurodb/literature_client.py \
        src/neurodb/chapter_registry.py src/neurodb/research_tools.py \
        src/neurodb/discovery_tools.py src/neurodb/prefs.py \
        src/neurodb/connectors/__init__.py
git commit -m "refactor: add epoch ownership docstrings to all flat-layout modules"
```

---

## Execution Order

1. A1 before A2 — testLog cleanup first so project status references the clean issue set
2. A2–A5 are independent of each other — can run in any order after A1
3. B1 before B2 — directories must exist before referencing them in docstrings
4. A and B phases are independent — docs and code organization do not depend on each other

---

## Stop Criteria

- If any test run fails after a docstring change, investigate before proceeding — a broken import or syntax error in the docstring is the most likely cause
- Do not move any module files in this plan — only create stubs and add docstrings
- Do not add `__all__` exports or imports to the new `__init__.py` stubs — they are documentation only at this stage
- Do not rename any existing modules or functions
