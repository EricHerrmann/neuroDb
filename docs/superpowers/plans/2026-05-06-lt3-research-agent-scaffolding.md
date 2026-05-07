# LT-3: Research Agent Scaffolding — Implementation Plan

**Goal:** Implement LT-3 in the existing Streamlit UI: `NeuroResearchAgent`, Neuro-Research mode, research questions, draft hypotheses, knowledge growth metrics, current-date hardening, and persistent agent mode.

**Spec:** `docs/superpowers/specs/2026-05-06-lt3-research-agent-scaffolding.md`

**Manual test plan:** `docs/testsPlans/manualTestPlan_agent_lt3.md`

**Scope decision:** Proceed in Streamlit. Do not work LOG-001, unrelated UI issues, UI Shell rearchitecture, model selection, connector framework architecture, or Semantic Scholar API-key architecture docs during LT-3 unless the user explicitly redirects scope in-session.

**Current test count:** 319 after LT-3 sign-off.

---

## File Map

| Action | File | Responsibility |
|---|---|---|
| Modify | `src/neurodb/schema.py` | Add `ResearchQuestion`, `ResearchHypothesis`, `KnowledgeGrowthSnapshot`, and `AppPreference` tables |
| Create | `src/neurodb/research_tools.py` | Persistence helpers, dataset cross-reference, knowledge-growth metrics |
| Create | `src/neurodb/agents/research_agent.py` | `NeuroResearchAgent` tool definitions, prompt, and dispatch |
| Modify | `src/neurodb/session_manager.py` | Inject actual current date into summary prompt |
| Modify | `src/neurodb/ui/app.py` | Load persisted agent mode, instantiate Research tab |
| Modify | `src/neurodb/ui/sidebar.py` | Add Neuro-Research mode and persist mode changes |
| Modify | `src/neurodb/ui/pages/chat.py` | Instantiate `NeuroResearchAgent` when selected |
| Create | `src/neurodb/ui/pages/research.py` | Research workspace tab for metrics, questions, hypotheses |
| Create/Modify | `tests/unit/*`, `tests/integration/*` | Focused TDD coverage for research tools, agent, UI wiring, preferences |
| Modify | `docs/projectStatus.md` | Keep phase status, test count, and references synchronized |
| Modify | `docs/testLog.md` | Move LOG-015 / LOG-021 only when actually resolved |

---

## Task Checklist

### Task 1 — Schema + Preferences ✅ COMPLETE

- [x] Add `ResearchQuestion` ORM model.
- [x] Add `ResearchHypothesis` ORM model.
- [x] Add `KnowledgeGrowthSnapshot` ORM model.
- [x] Add `AppPreference` ORM model for narrow key/value preferences.
- [x] Add schema tests proving all new tables are created by `init_db`.
- [x] Add preference helper tests for saving/loading `agent_mode`.

### Task 2 — Current-Date Hardening ✅ COMPLETE

- [x] Update session-summary prompt construction to include actual current date from code.
- [x] Ensure summary fallback date also comes from code.
- [x] Add tests with an injected/frozen date.
- [x] Keep this limited to date correctness; do not broaden into model identity or preference prompts.

### Task 3 — Research Tools ✅ COMPLETE

- [x] Add `record_research_question` helper.
- [x] Add `draft_hypothesis` helper with required confounds and limitations.
- [x] Add `get_knowledge_growth_metrics(persist=False)` helper.
- [x] Add metric snapshot persistence when `persist=True`.
- [x] Add `cross_reference_datasets` helper using local DB metadata, study notes, and semantic search results.
- [x] Add deterministic unit tests for no-match and matched-dataset cases.

### Task 4 — NeuroResearchAgent ✅ COMPLETE

- [x] Add `src/neurodb/agents/research_agent.py`.
- [x] Implement the `BaseAgent` three-method contract.
- [x] Reuse existing read-only DB, semantic search, Knowledge Library, and literature-search paths.
- [x] Exclude `tag_dataset` from the Research tool list.
- [x] Include current date and prior context in the research system prompt.
- [x] Add agent tests for tool list, prompt contract, and tool dispatch.

### Task 5 — UI Mode Wiring ✅ COMPLETE

- [x] Add `neuro_research` / **Neuro-Research** to sidebar mode options.
- [x] Persist mode changes through `AppPreference`.
- [x] Load persisted mode before sidebar render.
- [x] Instantiate `NeuroResearchAgent` from chat initialization.
- [x] Add tests proving all four modes still instantiate correctly.

### Task 6 — Research Workspace ✅ COMPLETE

- [x] Create `src/neurodb/ui/pages/research.py`.
- [x] Add Research workspace tab.
- [x] Render current knowledge-growth metrics.
- [x] Add snapshot action.
- [x] List research questions with status filters.
- [x] List draft hypotheses with status filters.
- [x] Add structural tests for Research tab and page module.

### Task 7 — Regression + Manual Readiness ✅ COMPLETE

- [x] Run focused unit tests after each task.
- [x] Run full `uv run pytest tests/ -q --tb=no`.
- [x] Update `docs/projectStatus.md` with final automated test count.
- [x] Start Streamlit for LT-3 manual testing.
- [x] Execute `docs/testsPlans/manualTestPlan_agent_lt3.md`.
- [x] Move LOG-015 and LOG-021 to Resolved after LT-3 T1/T2 pass evidence.
- [x] Keep LOG-001 open/deferred.

### Task 8 — T6/T7/T8 Max-Turn Remediation ✅ COMPLETE

- [x] Roll over-budget turns back out of API message history.
- [x] Give `NeuroResearchAgent` a larger default tool budget than DB/Tutor.
- [x] Add `.env` override through `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS`.
- [x] Save compact partial research progress to valid API history when Research mode reaches its tool budget.
- [x] Surface tool step and budget in visible agent activity.
- [x] Record stuck detection, evidence compaction, and long-running `ResearchRun` orchestration as deferred UI/research-runtime enhancements.
- [x] Run full `uv run pytest tests/ -q --tb=no`.
- [x] Re-run LT-3 T6/T7/T8 manual tests.

---

## Execution Order

1. Schema + preferences first, because agent tools and UI need stable persistence contracts.
2. Current-date hardening second, because research artifacts and session summaries both depend on it.
3. Research tools third, with unit tests independent of Streamlit.
4. `NeuroResearchAgent` fourth, reusing the tested helpers.
5. UI mode wiring fifth, after the agent exists.
6. Research workspace sixth, after persistence and metrics are stable.
7. Regression and manual readiness last.

---

## Stop Criteria

- If a task requires changing unrelated sidebar/context behavior, stop and ask the user.
- If Research mode tempts `tag_dataset` or other study-note mutations, stop and keep the research agent read-first.
- If formal hypothesis testing, statistics, or pre-analysis-plan execution appears necessary, defer it to DB Epoch 8 or a later research phase.
- If UI Shell limitations create friction, ship the simplest Streamlit surface that supports LT-3 manual tests.
