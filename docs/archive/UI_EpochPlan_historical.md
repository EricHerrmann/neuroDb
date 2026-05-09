# NeuroDb UI Epoch Plan

**Date:** 2026-05-06
**Status:** Draft architecture plan
**Current UI:** Streamlit
**Recommended direction:** Keep Streamlit through LT-3 sign-off, then move toward a FastAPI + React workbench shell. Monaco is not part of the target unless a later code/text-heavy workflow appears.

---

## Goal

Create a UI architecture that can grow with NeuroDb as it moves from local research assistant into a richer neuroscience workbench.

The desired direction is a workbench interface with the parts of VS Code that matter for this project: stable panes, independent scrolling, persistent layout state, keyboard-friendly navigation, visible agent activity, durable tabs, and room for richer artifacts such as research questions, hypotheses, dataset views, logs, and metrics.

This is not intended to become a code editor or text-editing product. The VS Code comparison is about workspace ergonomics and pane behavior, not Monaco/editor-centric workflows.

---

## Current Position

Streamlit is still useful and should not be replaced immediately.

Recent Streamlit changes finally delivered independent scrolling for the current split workspace, which removes the urgent pressure to migrate. Streamlit remains a good fit while LT-3 is being manually tested because it keeps the Python research loop short and avoids introducing frontend infrastructure before the research workflow is validated.

The long-term concern is not whether Streamlit can be made to work today. The concern is whether it remains the right shell as the UI becomes a core product surface rather than a thin Python dashboard. Streamlit's tight coupling between UI rendering and backend execution is useful early, but it becomes a constraint when the app needs independent panes, richer client-side state, streaming interactions, routing, and composable workflow surfaces.

---

## Constraints

- Preserve existing Python backend modules: DuckDB, ChromaDB, agents, session manager, research tools, literature client, and UI-independent helper modules.
- Do not rewrite the data or agent layers just to change the UI.
- Keep manual testing friction low while LT-3 is being validated.
- Avoid reopening unrelated UI issues during LT-3 unless they block testing.
- Any new UI architecture must support local-first development.
- Any migration must be incremental, with Streamlit remaining usable until the replacement has parity.

---

## Options

| Option | Pros | Cons | Fit |
|---|---|---|---|
| Stay Streamlit | Fastest Python-native iteration; simple deployment; direct access to DB/agent objects | Harder to build VS Code-like shell, pane persistence, keyboard workflows, and rich client state | Best through LT-3 sign-off |
| Streamlit + Components v2 | Keeps Streamlit while allowing richer custom UI; newer components avoid old iframe isolation | Still anchored to Streamlit rerun/lifecycle model; may become a bridge rather than final shell | Good short-term prototype path |
| FastAPI + React | Strong long-term workbench architecture; clean API boundary; better layout/state/routing; natural streaming UI; less coupling between UI state and Python execution | More infrastructure, frontend tests/build tooling, API design work; requires explicit handling of auth/config/state even for local use | Best long-term candidate |
| FastAPI + React + Monaco | Closest to code-editor-like artifact editing for SQL, JSON, plans, prompts, and reports | Heavier frontend bundle and more editor-specific state management; likely unnecessary for this product direction | Defer unless code/text editing becomes central |
| Electron or Tauri wrapper | Desktop-app feel; future filesystem and local service integration | Packaging complexity; premature before web shell is proven | Later only |

---

## FastAPI + React Pros and Cons

### Pros

**Cleaner architecture boundary**

FastAPI forces a real API layer between UI and backend behavior. That is more work up front, but it protects the system as it grows. Agent chat, research metrics, Knowledge Library review, dataset search, SQL execution, and preferences become backend capabilities with explicit contracts rather than Streamlit page logic.

**Better workbench layout**

React is a better fit for persistent panes, resizable split views, tab state, independent scroll containers, command surfaces, keyboard shortcuts, and routeable views. These are exactly the areas where Streamlit tends to require CSS/DOM workarounds.

**Better streaming UX**

Agent responses, tool activity, long-running searches, and future background jobs can stream through SSE or WebSockets without depending on Streamlit reruns. This matters as agents become more tool-heavy and workflows last longer than a single chat turn.

**Independent frontend state**

React can keep UI state local where appropriate: selected tab, expanded panes, active artifact, filters, scroll positions, temporary drafts, optimistic updates, and activity timelines. Streamlit pushes much of this through Python session state and reruns, which couples UI behavior to backend execution.

**More scalable interaction model**

As NeuroDb grows, users may need multiple simultaneous surfaces: chat, Research, Knowledge Library, SQL results, dataset detail, logs, source review, and prior sessions. React can compose these without every UI change becoming a Streamlit lifecycle problem.

**Backend remains Python**

The migration does not require rewriting the data layer. DuckDB, ChromaDB, agents, research tools, session manager, and literature client can stay in Python behind FastAPI routes.

**Better test boundaries**

Backend API tests can validate data and agent contracts. Frontend tests can validate layout and workflow behavior. Streamlit tests are possible, but harder to make precise for rich workbench interactions.

### Cons

**More moving parts**

The project gains a frontend build tool, package manager dependencies, API server, frontend test runner, route definitions, and likely generated or hand-maintained API client code.

**Slower simple changes**

Small UI changes that are trivial in Streamlit may require backend route updates, frontend component changes, and tests. This is the tradeoff for a cleaner long-term shell.

**API design burden**

The current Python app can pass objects around directly. FastAPI needs explicit request/response schemas, error handling, serialization, pagination, streaming protocols, and state boundaries.

**Local concurrency and locking**

DuckDB locking has already shown up during manual tests. Running Streamlit and FastAPI simultaneously against the same DB may need clear operating rules, read-only routes, connection lifecycle discipline, or separate dev DBs during transition.

**Agent state complexity**

Streaming chat is more explicit in FastAPI + React. The app must decide how transcripts, pending tool events, retries, partial failures, and session persistence are represented across client and server.

**Frontend maintenance**

React introduces dependency churn and frontend architecture choices. The project will need conventions for components, state management, API clients, styling, and testing.

---

## When to Skip a Long Comparison Phase

The phased comparison is valuable only if there is real uncertainty.

If the decision is already that Streamlit will not scale to the desired workbench, UI-0 should be short. The project can skip a broad bake-off and move directly to a FastAPI + React vertical slice.

Recommended compressed path:

1. Write a short ADR stating that FastAPI + React is the target shell.
2. Keep Streamlit as the current working UI until parity exists.
3. Build the FastAPI backend API first around existing helper modules.
4. Build one React vertical slice: Chat + Research metrics/questions/hypotheses.
5. Decide from that slice whether the migration continues.

This preserves the benefit of a prototype without pretending Streamlit and React are equally likely long-term endpoints.

---

## Recommended Direction

Use a phased UI Shell epoch after LT-3 sign-off.

Do not perform a full rewrite first. Instead, build a small FastAPI + React vertical slice that proves the future shell can handle the project’s hardest interaction patterns better than Streamlit.

Recommended target stack:

- **FastAPI backend**
  - Exposes existing Python workflows through typed API routes.
  - Owns agent streaming endpoints.
  - Serves static frontend assets when packaged.
  - Keeps DuckDB/Chroma access in Python.

- **React frontend**
  - Owns workbench layout, panes, tabs, routing, and persistent UI state.
  - Handles chat transcript rendering, tool-event timelines, Research views, SQL workspace, and dataset browsing.
  - Uses a modern React framework or Vite-style app depending on deployment constraints.

- **WebSockets or SSE**
  - Streams agent text and tool events.
  - Keeps chat activity visible without Streamlit reruns.

- **Monaco Editor**
  - Not part of the initial target.
  - Reconsider only if future SQL, report, prompt, or plan-editing workflows become central enough to justify editor-specific complexity.

---

## Proposed UI Shell Vertical Slice

Build a prototype that includes only enough to compare against Streamlit:

1. Left activity bar or mode rail:
   - Chat
   - Research
   - Knowledge Library
   - SQL
   - Datasets

2. Main editor/workbench area:
   - Persistent tabs
   - Independent pane scrolling
   - Resizable split layout

3. Chat panel:
   - Agent mode selection
   - Streaming assistant response
   - Tool activity timeline
   - Clear/save session

4. Research panel:
   - Knowledge-growth metrics
   - Research questions
   - Draft hypotheses
   - Snapshot action

5. SQL panel:
   - Query input
   - Result grid
   - Read-only execution guard

6. Minimal API backend:
   - `GET /api/status`
   - `GET /api/preferences`
   - `PUT /api/preferences/agent-mode`
   - `GET /api/research/metrics`
   - `POST /api/research/metrics/snapshot`
   - `GET /api/research/questions`
   - `GET /api/research/hypotheses`
   - `POST /api/chat/turn` or streaming equivalent

---

## Migration Strategy

### Phase UI-0 — Architecture Decision

Create a short architecture decision record. If the user's preference remains FastAPI + React, this phase should be brief and should not become a broad bake-off.

Document:

- FastAPI + React as likely target shell
- Streamlit as retained current UI during transition
- Components v2 as bridge only if a narrow component solves an immediate blocker
- Monaco deferred
- Desktop wrapper deferred

Exit criteria:

- Confirm FastAPI + React vertical slice scope.
- Define the first API boundary.
- Confirm Streamlit remains supported during migration.

### Phase UI-1 — Backend API Shell

Add FastAPI without replacing Streamlit.

Scope:

- App factory.
- Shared dependency initialization for DB, vector store, session manager, knowledge store.
- Read-only API routes for status, preferences, metrics, questions, and hypotheses.
- Streaming chat proof of concept.

Exit criteria:

- Existing Streamlit app still runs.
- FastAPI tests pass.
- No duplicate research logic outside existing helpers.

### Phase UI-2 — React Workbench Prototype

Build the first workbench shell.

Scope:

- Activity rail.
- Resizable panes.
- Persistent tab/workspace state.
- Chat streaming panel.
- Research metrics/questions/hypotheses panel.

Exit criteria:

- Prototype can run against local FastAPI.
- Chat and Research vertical slice work end to end.
- User can compare it directly against Streamlit.

### Phase UI-3 — Parity Migration

Move stable Streamlit surfaces into React one at a time.

Suggested order:

1. Research
2. SQL
3. Knowledge Library
4. Suggestions
5. Datasets
6. Study Log / Registry
7. System Warnings panel — display `system_warnings` table rows (logged_at, warning_type, task_type, reason, fallback_step, resolved_value); filterable by date and warning type; surfaces operational anomalies from the Config Control Phase 6 fallback chain for periodic tech debt review. CLI surface exists from Config Control Phase 6; this is the UI counterpart.

Exit criteria:

- Each migrated surface has API tests and frontend smoke tests.
- Streamlit remains available until replacement is accepted.

### Phase UI-4 — Streamlit Retirement Decision

Retire Streamlit only after React shell has real workflow parity.

Exit criteria:

- Manual test plans pass in React shell.
- Streamlit no longer carries unique workflow capability.
- Runbook updated.

---

## Risks

- Frontend complexity can slow research feature work.
- API boundaries can become too granular or too UI-specific if designed before workflows stabilize.
- Agent streaming needs careful state handling to avoid transcript divergence.
- DuckDB locking behavior must be handled deliberately if Streamlit and FastAPI run at the same time.
- Monaco can distract from core workbench needs if added too early.

---

## Guardrails

- Keep backend logic in Python helper modules, not frontend code.
- Keep FastAPI routes thin.
- Do not duplicate Streamlit page logic directly into API handlers.
- Build one vertical slice before committing to migration.
- Add frontend only where it creates measurable workflow value.
- Do not start UI Shell work during LT-3 manual verification unless Streamlit blocks testing.

---

## Deferred Research Runtime Enhancements

LT-3 exposed that research workflows can legitimately require more tool use than tutor or DB chat. The immediate LT-3 fix is to use a larger configurable research-agent budget, save compact partial research progress to valid API history when the budget is reached, roll back invalid tool-use messages, and surface step/budget progress to the user.

Deeper runtime changes are deferred to a later enhancement, likely alongside or after the FastAPI + React shell:

| Enhancement | Purpose | Why deferred |
|---|---|---|
| Stuck detection | Detect repeated same-tool/same-input loops, repeated empty results, and no-new-evidence cycles; pause and ask the user to continue, narrow, or draft from current evidence | Requires run-state observability and heuristics beyond the LT-3 fix |
| Evidence compaction | Periodically summarize raw tool results into compact evidence packets so long research turns do not carry every intermediate result forward | Needs durable artifact design and careful citation/provenance handling |
| Long-running `ResearchRun` orchestration | Support minute/hour-scale research jobs with queued runs, resumability, cancellation, checkpoints, progress UI, and final artifacts | Better suited to FastAPI + React than Streamlit's rerun model |

These are not abandoned. They are intentionally separated from the LT-3 fix so T6/T7 can be unblocked without prematurely building a full deep-research runtime.

---

## Provider Selection UI

Provider selection is currently controlled by editing `neurodb_models.toml` `[routing]` section directly. This is intentional for the CLI/Streamlit phase — no env var overrides exist.

A future UI epoch must expose provider selection as a UI surface. The minimum scope:

- Settings panel or preferences route with three dropdowns: Economy, Standard, Premium provider
- Reads and writes the `[routing]` section in `neurodb_models.toml` (or a user-override config layer)
- Shows current active model for each tier alongside the selector
- Requires confirmation before switching tiers that have in-flight agent calls

This is intentionally deferred until the FastAPI + React workbench shell exists, since a settings route is a natural fit for that architecture and would be awkward as a standalone Streamlit page.

---

## Open Questions

- Should the first React prototype use Vite, React Router framework, or another full-stack React framework?
- Should chat streaming use SSE first for simplicity, or WebSockets for bidirectional control?
- Should Monaco be part of UI-2, or deferred until SQL/research-plan editing needs it?
- Should Streamlit and FastAPI share one process during transition, or run as separate commands?
- What is the minimum “VS Code-like” feature set that makes the migration worthwhile?

---

## Current Recommendation

Finish LT-3 manual verification in Streamlit.

Then run UI-0 and UI-1 as a contained architecture/prototype effort. The key decision should be based on whether a FastAPI + React vertical slice materially improves the workbench experience without slowing research-agent development too much.
