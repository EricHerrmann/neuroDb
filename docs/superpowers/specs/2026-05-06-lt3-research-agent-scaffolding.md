# LT-3: Research Agent Scaffolding — Design Spec

**Date:** 2026-05-06
**Epoch plan:** `docs/ClaudeLearnEpochPlan.md`
**Status:** Draft — ready for review before implementation planning
**Dependency:** LT-2 is signed off. LT-3 proceeds in the existing Streamlit shell; UI Shell rearchitecture remains deferred post-LT-3.

---

## Goal

Introduce `NeuroResearchAgent` as the first research-layer agent on top of the LT-1/LT-2 learning substrate. The agent should turn accumulated learning context into structured, auditable research questions and draft hypotheses while staying grounded in the Knowledge Library, literature-search history, study notes, and local dataset DB.

LT-3 is scaffolding, not a full hypothesis-testing epoch. It should create the durable contracts and minimal UI needed to evaluate research workflows without expanding into unrelated UI fixes, connector framework work, or full statistical analysis.

---

## Scope Boundary

LT-3 includes:

- `NeuroResearchAgent` inheriting `BaseAgent`
- A fourth agent mode: `neuro_research` / **Neuro-Research**
- Research tools for structured review, dataset cross-reference, knowledge growth metrics, and draft hypothesis capture
- Minimal Research workspace tab for metrics, research questions, and draft hypotheses
- Schema needed to persist research questions, hypothesis drafts, and knowledge-growth snapshots
- LT-3-specific hardening for current date injection and persistent agent mode

LT-3 does not include:

- UI Shell rearchitecture or fixed-pane layout work
- Model selection or broad model-identity UX
- Connector framework architecture
- New external literature sources beyond LT-2 PubMed and Semantic Scholar
- Full-text PDF indexing
- Formal statistical testing, causal inference, or pre-analysis-plan execution
- Broad cleanup of unrelated open test-log items

---

## 1. Research Agent

### 1.1 Module

New file: `src/neurodb/agents/research_agent.py`

`NeuroResearchAgent` inherits `BaseAgent` and implements the existing three-method contract:

| Method | Purpose |
|--------|---------|
| `_get_active_tools()` | Return research-agent tool definitions |
| `_build_system_prompt()` | Build a research-oriented system prompt with prior context and current date |
| `_execute_tool_block(block)` | Dispatch research, knowledge, literature, and read-only DB tools |

### 1.2 System Prompt Contract

The research agent is more conservative than the Tutor:

- It must distinguish evidence, inference, speculation, and missing data.
- It must call tools before making claims about local datasets, curated sources, or prior project knowledge.
- It may propose hypotheses, but must label them as drafts.
- It must include confounds and limitations in every hypothesis draft.
- It must never claim a hypothesis is tested unless local DB evidence and a testing plan support that claim.
- It receives the actual current date from application code and must use that date in saved artifacts.

### 1.3 Tool Set

`NeuroResearchAgent` gets read-first tools plus explicit write tools for research artifacts.

| Tool | Source | Behavior |
|------|--------|----------|
| `search_knowledge_library` | Existing Knowledge Library | Search approved curated source summaries |
| `search_literature` | Existing `LiteratureSearchClient` | Search PubMed and Semantic Scholar using LT-2 client |
| `query_db` | Existing DB tool | Read-only SQL SELECT against local DB |
| `semantic_search` | Existing DB tool | Search dataset embeddings and study notes |
| `get_study_notes` | Existing DB tool | Retrieve local concept tags |
| `cross_reference_datasets` | New research helper | Return dataset candidates related to a research topic |
| `get_knowledge_growth_metrics` | New research helper | Compute and optionally snapshot learning/research growth metrics |
| `record_research_question` | New write helper | Persist a candidate research question |
| `draft_hypothesis` | New write helper | Persist a structured draft hypothesis |

`tag_dataset` is not included by default. The research agent should not mutate study notes while drafting hypotheses; tagging remains Local DB / Tutor workflow.

### 1.4 Dataset Cross-Reference Behavior

`cross_reference_datasets(query, concept_tags=None, sources=None, n_results=5)` combines:

- `semantic_search(query)` results
- `study_notes` filtered by concept tags when provided
- `v_all_datasets` metadata for dataset title, source, source ID, modality, task, and description where available

The return payload is JSON:

```python
{
    "query": str,
    "candidates": [
        {
            "source": str,
            "source_id": str,
            "title": str | None,
            "modality": str | None,
            "matched_notes": list[dict],
            "semantic_distance": float | None,
            "reason": str,
        }
    ],
    "limitations": list[str],
}
```

The helper is allowed to return an empty candidate list. Empty results are signal, not failure.

### 1.5 Structured Literature Review Behavior

The agent does not need a separate `structured_literature_review` persistence table in LT-3. It composes reviews from:

- `search_knowledge_library`
- `search_literature`
- recent `literature_searches` rows when auditing what was previously searched

The response should include:

- Included evidence
- Excluded or missing evidence
- Whether each item is curated, live-search-only, or local-DB-derived
- Citation/source identifiers when available
- Open questions for follow-up search

---

## 2. Research Persistence

### 2.1 `research_questions`

Stores candidate research questions raised by the agent or user.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `question` | Text | Required |
| `topic_context` | Text | Required |
| `status` | String(32) | `open`, `parked`, `converted_to_hypothesis` |
| `created_at` | String(32) | ISO timestamp from application code |
| `updated_at` | String(32) | ISO timestamp from application code |

### 2.2 `research_hypotheses`

Stores draft, untested hypotheses.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `question_id` | Integer nullable FK | Optional link to `research_questions.id` |
| `title` | Text | Required |
| `mechanism` | Text | Proposed mechanism |
| `evidence_json` | Text | Evidence objects with source labels |
| `predictions_json` | Text | Testable predictions |
| `datasets_json` | Text | Candidate local datasets |
| `confounds_json` | Text | Required; may be empty list only if explicitly justified |
| `limitations` | Text | Required |
| `status` | String(32) | `draft`, `needs_evidence`, `ready_for_plan`, `archived` |
| `created_at` | String(32) | ISO timestamp from application code |
| `updated_at` | String(32) | ISO timestamp from application code |

### 2.3 `knowledge_growth_snapshots`

Stores metric snapshots so growth can be compared over time.

| Column | Type | Notes |
|--------|------|-------|
| `id` | Integer PK | |
| `snapshot_at` | String(32) | ISO timestamp from application code |
| `approved_sources_count` | Integer | `knowledge_sources.status = approved` |
| `pending_sources_count` | Integer | `knowledge_sources.status = pending` |
| `chat_sessions_count` | Integer | `chat_sessions` rows |
| `literature_searches_count` | Integer | `literature_searches` rows |
| `study_notes_count` | Integer | `study_notes` rows |
| `research_questions_count` | Integer | `research_questions` rows |
| `research_hypotheses_count` | Integer | `research_hypotheses` rows |
| `metrics_json` | Text | Extra computed metrics and caveats |

Metric snapshots are append-only. Recomputing metrics should create a new row only when called with `persist=True`.

---

## 3. Knowledge Growth Metrics

`get_knowledge_growth_metrics(persist=False)` returns current counts and lightweight derived measures:

- Approved Knowledge Library sources
- Pending sources awaiting review
- Completed/draft chat sessions
- Literature searches run
- Study notes and distinct concept tags
- Research questions and draft hypotheses
- Coverage by source type and topic where available
- Chroma collection counts for `knowledge_library` and `agent_context`

The metric payload must include caveats. Example caveats:

- Chroma collection count can diverge from DuckDB rows if an approval failed mid-write.
- `literature_searches` counts searches, not quality-reviewed papers.
- Study-note count is not a measure of evidence strength.

The Research workspace tab displays this payload, but all logic lives in a helper module so tests do not depend on Streamlit.

---

## 4. UI Surface

### 4.1 Agent Mode

The sidebar Agent section gains:

```
Local DB | External DB | Neuro-Tutor | Neuro-Research
```

Selecting **Neuro-Research** instantiates `NeuroResearchAgent`.

### 4.2 Research Workspace Tab

Add a right-workspace tab labeled **Research**. It contains:

- Knowledge growth metrics summary
- Button to create a persisted metric snapshot
- Open research questions list
- Draft hypothesis list
- Status filters for questions and hypotheses

This tab is a management surface for persisted research artifacts. The chat panel remains the primary interface for creating questions and hypotheses.

### 4.3 Existing Shell Constraint

LT-3 must use the existing Streamlit layout. No attempt should be made to fix page scroll, fixed input pinning, or broader app-shell issues during LT-3.

---

## 5. LT-3 Hardening From Test Log

Only test-log items that directly affect LT-3 research correctness are in scope.

### 5.1 LOG-015 — Current Date

Research and session summaries must use the actual current date supplied by code, not model knowledge. Implementation should:

- Add a small date/time provider helper or pass `date.today().isoformat()` directly at prompt build time.
- Include `Current date: YYYY-MM-DD` in summary and research-agent prompts.
- Require saved summaries, research questions, hypotheses, and metric snapshots to use application timestamps.
- Test with a frozen or injected date.

### 5.2 LOG-021 — Agent Mode Persistence

Adding a fourth agent mode increases the cost of non-persistent mode selection. LT-3 should persist only the selected mode, not introduce broad user preferences.

Recommended implementation:

- Add an `app_preferences` key/value table.
- Store `agent_mode`.
- Load it during app startup before rendering the sidebar.
- Update it when the sidebar mode changes.

### 5.3 Deferred — LOG-001 Context Ambiguity

LOG-001 is explicitly deferred post-LT-3 by user direction on 2026-05-06. LT-3 implementation must not alter textbook dropdown behavior or chapter-context UX unless the user directs it during a Q&A in this session.

Research mode does not consume chapter context by default, so LOG-001 is not a blocker for LT-3.

---

## 6. Testing

### Unit Tests

- `NeuroResearchAgent` inherits `BaseAgent` and exposes the expected tool names.
- Research prompt includes prior context and the injected current date.
- `cross_reference_datasets` returns deterministic candidates from fixture DB rows and handles no-match queries.
- `get_knowledge_growth_metrics` computes counts from fixture tables without Streamlit.
- Metric snapshot persists only when `persist=True`.
- `record_research_question` writes required fields and timestamps.
- `draft_hypothesis` rejects missing confounds/limitations and persists valid JSON fields.
- `app_preferences` stores and reloads `agent_mode`.
- Session summary prompt uses injected current date.

### Integration Tests

- Research mode instantiates `NeuroResearchAgent` from the UI agent factory path.
- Research chat can search curated knowledge, cross-reference local datasets, and save a draft hypothesis.
- Research workspace lists saved questions, hypotheses, and metric snapshots.
- Existing Local DB, External DB, and Neuro-Tutor modes continue to instantiate correctly.

### Structural Tests

- `src/neurodb/agents/research_agent.py` exists.
- Sidebar mode labels include **Neuro-Research**.
- Research workspace tab exists.
- New schema tables are registered in `Base.metadata`.

### Manual Tests

Manual verification is defined in `docs/testsPlans/manualTestPlan_agent_lt3.md` and must be updated before implementation if the workflow changes.

---

## 7. Decisions Log

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-06 | LT-3 is scaffolding, not DB Epoch 8 hypothesis testing | The project needs research-agent contracts before formal analysis workflows |
| 2026-05-06 | Research agent is a separate `BaseAgent` subclass | Research behavior has stricter evidence and artifact persistence rules than Tutor behavior |
| 2026-05-06 | Research agent excludes `tag_dataset` by default | Drafting hypotheses should not mutate study-note state implicitly |
| 2026-05-06 | Knowledge growth metrics are computed from existing stores and snapshotted on demand | Avoids background jobs while still making growth auditable |
| 2026-05-06 | Persist only `agent_mode` in LT-3 | Resolves the direct fourth-mode friction without starting a broad preferences system |
| 2026-05-06 | Current date comes from code, not the model | Fixes LOG-015 and prevents research artifacts from carrying fabricated dates |
| 2026-05-06 | LOG-001 deferred post-LT-3 | Keeps LT-3 focused on research-agent scaffolding and avoids sidebar scope creep |
