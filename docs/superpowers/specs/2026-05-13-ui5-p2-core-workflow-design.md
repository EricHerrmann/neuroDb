# UI-5 P2 Core Workflow Design

**Date:** 2026-05-13
**Status:** Implemented 2026-05-13; manual verification pending
**Epoch:** UI
**Source:** `docs/superpowers/specs/2026-05-12-ui5-parity-completion-design.md`
**Deferred prerequisite:** `docs/testsPlans/deferredTestPlans/manualTestPlan_ui5_p1_data_integrity.md`

---

## Goal

Finish the P2 core workflow gaps that prevent the React workbench from being a
practical replacement for Streamlit during everyday research use. P2 should make
the panels usable and observable; it should not pull in P3 polish, broad layout
work, or Streamlit retirement.

---

## Scope

P2 includes these workflow gaps:

| Area | Capability | User value |
|---|---|---|
| Chat | Tool activity log | User can see what tools the agent used while keeping chat readable |
| Chat | Clear + auto-summarize | Ended sessions persist usable memory instead of disappearing from context |
| Chat | User-readable answer formatting | Agent responses render as readable text/tables instead of raw Markdown artifacts |
| Study Log | Delete tag | Mistakes and duplicate tags can be removed from React |
| Study Log | Concept/source filters | Tag list remains usable as notes accumulate |
| Datasets | Modality filter | Researcher can narrow datasets by acquisition/modality |
| Datasets | Rich result metadata | Dataset list shows enough context to choose records |
| Research | Status filters | Questions and hypotheses remain navigable as lists grow |
| Research | Hypothesis detail expansion | Full scientific content is visible in React |
| Research | Accept revisions / dismiss review | Review output can drive hypothesis lifecycle |
| Knowledge Library | LLM summary generation on approve | Approved sources get useful summaries from React |
| Knowledge Library | Near-duplicate detection before approve | Duplicate knowledge entries are caught before approval |

Out of scope:

- UI-5 P3 polish and enhancements unless explicitly called out as a dependency.
- Streamlit deletion or retirement decision.
- Research question create/update actions tracked by `LOG-037`.
- Full hypothesis slide-over drawer.
- Provider routing/settings UI.
- Generic frontend page frameworks. Reuse narrow hooks/components only when two
  P2 call sites share the same behavior.

---

## Design Principles

1. Keep P2 implementation vertical by workflow, with route, schema, client,
   component, and tests landing together.
2. Preserve UI-5 P1 data-integrity behavior: write paths that update DuckDB must
   also update ChromaDB when that is part of the workflow, and partial failures
   must surface warnings or task errors.
3. Prefer focused shared helpers for repeated task/mutation patterns, aligned
   with TD-5, but avoid creating a generic panel framework.
4. Manual tests should verify browser/server/DB/Chroma behavior; automated tests
   own branch coverage and fault injection.

---

## Chat

### Tool Activity Log

Backend currently emits only text chunks from `/api/chat/turn`. P2 should expose
tool activity as structured stream events without making the transcript noisy.

Design:

- Extend agent streaming so `tool_start` and `tool_result` events are emitted as
  SSE payloads with `turn_id`, `tool_name`, optional `input`, optional `result`,
  and `sequence`.
- Update `frontend/src/hooks/useChat.ts` so assistant messages can hold an
  `activity` array separate from the message text.
- Add an `ActivityLog` component rendered under the related assistant message.
  It is collapsed by default and shows a compact summary such as `3 tool calls`.
- Expanded activity rows show tool name, status, and a compact result preview;
  JSON details use `<details>` so large payloads do not dominate the chat.

Acceptance:

- Tool calls are visible for agent turns that use tools.
- Chat text remains readable with activity collapsed by default.
- Frontend tests cover event accumulation and collapsed/expanded rendering.

### Clear + Auto-Summarize

Streamlit clear persisted useful session memory by summarizing sessions with
enough turns. React needs the same behavior before session memory can be trusted.

Design:

- Add `POST /api/sessions/{session_id}/end`.
- Route delegates to Agent Core/session-management code that ends the session,
  summarizes when the session has enough user turns, and persists `status`,
  `summary`, `inferred_topic`, and message count.
- React adds a clear button in the chat header. On success, it clears local
  messages and invalidates `['sessions']`.
- If there are too few turns, the route still ends or resets the active session
  according to existing session-manager rules, but returns no summary.

Acceptance:

- Clearing a session with sufficient history creates an ended session row with a
  summary and inferred topic.
- Clearing a short session does not create misleading memory.
- Chat UI resets only after the backend succeeds.

### User-Readable Answer Formatting

`LOG-055` records that agent answers can return Markdown that renders poorly in
the chat window. P2 should fix both generation guidance and display behavior.

Design:

- Update DB, tutor, and research agent prompts so user-facing answers prefer
  concise prose plus simple Markdown tables only when tabular comparison helps.
- Add a chat message renderer that supports paragraphs, bullet/numbered lists,
  inline code, fenced code blocks, links, and Markdown tables. Use a small
  dependency only if implementation cost stays lower than maintaining a local
  parser.
- Keep raw tool JSON out of the answer bubble; tool details belong in the
  activity log.
- Add snapshot-style frontend tests for table/list rendering and plain-text
  fallback.

Acceptance:

- Tables render as tables, not raw pipe text.
- Normal prose keeps line breaks and does not overflow the message bubble.
- Agent prompts explicitly separate user answer formatting from tool/debug data.

---

## Study Log

### Delete Tag

Design:

- Add `DELETE /api/study-log/{id}`.
- Route deletes the `StudyNote` row and calls `remove_note(vector_store, id)`.
- If vector deletion fails after DB deletion, return a warning shape consistent
  with P1 partial-success behavior or log the warning if the response is `204`.
- React adds a right-aligned Remove button per tag row and invalidates
  `['study-log']`.

Acceptance:

- Deleted tags disappear from React and CLI list output.
- Matching Chroma note id is removed or a visible warning is produced.

### Concept and Source Filters

Design:

- Add a compact filter row above the tag list: concept text input and source
  select.
- Filter client-side against the loaded list. No backend change is needed.
- Source options are derived from loaded rows plus known dataset sources.

Acceptance:

- Filters compose.
- Empty filtered state is explicit and does not look like a load failure.

---

## Datasets

### Modality Filter

Design:

- Add `modality` query parameter to `GET /api/datasets`.
- Route forwards `keyword` and `modality` to `search_datasets`.
- React adds a modality segmented control or select with `all`, `MRI`, `fMRI`,
  `EEG`, `MEG`, and `ISH`.

Acceptance:

- Requests include `modality` only when a specific modality is selected.
- Backend tests prove keyword and modality filters compose.

### Rich Result Metadata

Design:

- Extend `DatasetItem` response/schema if needed to include `title`, `modality`,
  and `n_subjects`.
- Render title as the primary row text, with `source:source_id`, modality badge,
  and subject count as compact metadata.

Acceptance:

- Dataset rows are scannable without opening another panel.
- Missing metadata renders as quiet placeholders, not `undefined`.

---

## Research

### Status Filters

Design:

- Support multi-status filtering for questions and hypotheses.
- API accepts repeated `status` query params or comma-separated status lists;
  implementation should choose one convention and use it consistently in client
  helpers.
- React renders filter chips for known question and hypothesis statuses.

Acceptance:

- Multiple statuses can be selected.
- No selection means all.
- Query keys include the selected statuses so cache state is correct.

### Hypothesis Detail Expansion

Design:

- Extend API and frontend types to include `evidence_json`, `predictions_json`,
  `datasets_json`, `confounds_json`, and `limitations_json`.
- `HypothesisCard` gets an inline expand toggle.
- Expanded content renders only populated sections, using compact lists and
  preserving readable prose for mechanism.

Acceptance:

- A hypothesis with all JSON fields populated exposes all scientific content.
- Empty/null fields are omitted cleanly.

### Accept Revisions / Dismiss Review

Design:

- Add `POST /api/research/reviews/{id}/accept`.
- Add `POST /api/research/reviews/{id}/dismiss`.
- Accept marks the review accepted and applies the review lifecycle update using
  existing research tooling where available.
- Dismiss marks the review dismissed and leaves the hypothesis unchanged.
- React shows actions only on pending reviews and invalidates review/hypothesis
  queries after success.

Acceptance:

- Pending review cards expose both actions.
- Accepted/dismissed reviews no longer show action buttons.
- Hypothesis/review status updates are visible after refresh.

---

## Knowledge Library

### LLM Summary Generation on Approve

P1 approval indexes the source with the existing summary. P2 should generate or
refresh that summary before final indexing when possible.

Design:

- Convert approve flow to return a task id when summary generation is requested.
- Background task sets status to approved, calls `TaskRouter.route("summary.knowledge_source")`,
  writes the generated summary, then calls `knowledge_store.add_summary`.
- If model summary generation fails, approval should not silently disappear:
  task status becomes failed and the pending/approved state remains auditable.
- React uses `useTask` and invalidates `['knowledge-library']` when the task
  completes.

Acceptance:

- Approving a source starts a visible task.
- Completed task populates `summary` and `chroma_id`.
- Failure is visible in the task status and does not leave the UI spinning.

### Near-Duplicate Detection Before Approve

Design:

- Add `GET /api/knowledge-library/{id}/duplicates`.
- Route embeds the candidate title/topic context and queries approved knowledge
  sources in ChromaDB for nearest neighbors.
- Response includes candidate ids, titles, DOI/url where available, and distance.
- React approve flow calls duplicate check first. If near duplicates exist,
  render an inline warning with Cancel and Approve Anyway.

Acceptance:

- Duplicate candidates block immediate approval until the user confirms.
- Approve Anyway follows the normal summary/indexing flow.
- Duplicate-check failures surface as warnings, not silent approval.

---

## API and Type Changes

| Area | Backend | Frontend |
|---|---|---|
| Chat activity | `/api/chat/turn` SSE emits tool events | `useChat` message activity model, `ActivityLog` component |
| Session end | `POST /api/sessions/{session_id}/end` | `api.endSession`, chat clear button |
| Study delete | `DELETE /api/study-log/{id}` | `api.deleteStudyNote`, Remove button |
| Dataset filters | `GET /api/datasets?keyword=&modality=` | `api.getDatasets(keyword, modality)`, richer `DatasetItem` |
| Research filters/details | `GET /api/research/questions`, `/hypotheses` with status list and detail fields | richer `ResearchQuestion`/`Hypothesis` types, filter chips |
| Review actions | `POST /api/research/reviews/{id}/accept`, `/dismiss` | review action mutations |
| KL summary/duplicates | approve task flow, `GET /api/knowledge-library/{id}/duplicates` | task status and duplicate confirmation UI |

---

## Test Strategy

Automated prerequisites:

- `uv run pytest tests/ -q`
- `cd frontend && npm test`
- `cd frontend && npm run build`

Required automated coverage:

- Backend route tests for every new endpoint and changed response model.
- Frontend tests for each user-visible control: activity log, clear button,
  filters, delete, review actions, duplicate prompt, task status.
- Regression tests for `LOG-055`: Markdown table/list rendering and prompt
  wording that discourages raw debug/tool output in chat answers.
- At least one integration-style API test for the approve-summary-index flow
  with model/vector dependencies mocked.

Manual verification:

- Use `docs/testsPlans/manualTestPlan_ui5_common_parity.md` as the active UI-5
  manual plan. The original P2-only plan is retained under
  `docs/testsPlans/deferredTestPlans/manualTestPlan_ui5_p2_core_workflow.md`.
- Manual steps should use checked-in helper scripts under `tests/manual/` for
  long DB/vector verification commands.
- Manual scope should focus on browser workflow, FastAPI/DuckDB/Chroma wiring,
  task status behavior, and visible formatting. Do not duplicate automated
  branch/fault tests unless the manual check adds production-like value.

---

## Implementation Order

1. Chat observability and formatting: activity log, readable answer rendering,
   prompt updates.
2. Study Log and Datasets: delete/filter/rich metadata workflows with low
   backend risk.
3. Research: filters, detail expansion, review accept/dismiss lifecycle.
4. Knowledge Library: duplicate check, approve summary task, Chroma reindex.
5. Cross-panel cleanup: extract narrow shared hooks/components only where P2
   produced repeated task or mutation patterns.

---

## Open Questions

- Should `POST /api/sessions/{session_id}/end` use the numeric DB id or the
  external `session_id` string? The route should match what the chat/session
  manager already treats as stable.
- Should Knowledge Library approve always generate a summary, or allow "approve
  without summary" for offline/no-provider mode?
- Should research status filtering use repeated query params or a comma-separated
  parameter? Pick one before implementation and test the client helper.
- Should Markdown rendering use a dependency such as `react-markdown`, or a small
  local renderer covering only tables/lists/code/links?
