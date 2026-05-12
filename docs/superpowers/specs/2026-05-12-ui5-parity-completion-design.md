# UI-5 Parity Completion — Draft Design

**Date:** 2026-05-12
**Status:** Draft — requires design refinement before implementation
**Author:** Eric Herrmann
**Source:** 2026-05-12 Streamlit vs React capability comparison

---

## Goal

Close all remaining gaps between Streamlit and React, fix data-integrity divergences introduced during UI-2/UI-3, and add targeted enhancements that exceed Streamlit capability. At the end of this phase, UI-4 (Streamlit retirement) can proceed without risk of data loss or workflow regression.

---

## Priority Tiers

**P1 — Data Integrity:** Silent bugs where React writes incomplete or inconsistent data vs Streamlit. Must be fixed before Streamlit can be retired.

**P2 — Core Workflow:** Features that make panels useful. Workflows that simply don't work in React.

**P3 — Polish:** Missing detail and convenience features. Streamlit parity but not blocking.

**Enhancement:** New capability that exceeds Streamlit. React architecture makes these natural.

---

## Chat

### P2 — Tool Activity Log

Streamlit renders `tool_start` and `tool_result` events inline between chat messages, with an iteration counter per tool call. This is the primary way to observe agent reasoning during research workflows.

**Design:** Add a collapsible "Activity" pane below each assistant message that received tool calls. The pane is collapsed by default (shows a summary line: "3 tool calls"). Expanded, it renders each tool call sequentially: tool name, inputs (JSON, collapsed by default), result summary. This is strictly better than the Streamlit inline rendering — it keeps the chat transcript readable while preserving full observability.

The SSE stream already emits `tool_start` and `tool_result` events (see `src/neurodb/api/routes/chat.py`). The React `useChat` hook receives them but does not render them. The fix is in `ChatPanel.tsx` only — no backend changes needed.

**Files:** `frontend/src/pages/ChatPanel.tsx`, `frontend/src/hooks/useChat.ts` (verify event types)

### P2 — Clear + Auto-Summarize

Streamlit's Clear button triggers `_auto_summarize_if_sufficient()` — if the session has ≥3 user turns, it calls the summarize agent, saves the `ChatSession` with `status='ended'`, `summary`, and `inferred_topic`. Without this, session memory never persists.

**Design:** Add a Clear button to the right side of the chat header (next to the agent mode select). On click, call `POST /api/sessions/{id}/end` with the active session ID. The backend runs summarization synchronously (it is short, not a background task candidate) and returns the saved session. React clears the message list and resets the active session.

Backend: add `POST /api/sessions/{id}/end` route → calls existing `_auto_summarize_if_sufficient` logic from session_manager.

**Files:** `frontend/src/pages/ChatPanel.tsx`, `src/neurodb/api/routes/sessions.py`

### P3 — Prior Context Banner

When an agent call injects prior context from a past session, the user currently has no way to know which session is active. Streamlit showed a blue pill with the inferred topic.

**Design:** The `GET /api/preferences` response (or a new `GET /api/sessions/active-context`) returns the `active_prior_topic` string. Render it as a small blue pill immediately below the chat header bar, only when a non-null value is present.

---

## Study Log

### P1 — Vector Embedding on Create

`POST /api/study-log` calls `tag_dataset()` to create the DB row but does not call `embed_note()`. Study tags added via React are invisible to semantic search.

**Design:** After the `tag_dataset()` call succeeds, the route calls `embed_note(note_id, concept_tag, note_text, vector_store)`. The vector store dependency is already available in other routes via `Depends(get_vector_store)`.

**Files:** `src/neurodb/api/routes/study_log.py`

### P2 — Delete Tag

Streamlit allows row-click → Delete Tag. React has no delete path.

**Design:** Add `DELETE /api/study-log/{id}` route — deletes the `StudyNote` row and calls `remove_note(id, vector_store)` to deindex. In the React table, add a small Remove button per row (right-aligned, same pattern as RegistryPanel). No confirmation dialog needed — the operation is low-stakes and the list refreshes immediately.

**Files:** `src/neurodb/api/routes/study_log.py`, `frontend/src/pages/StudyLogPanel.tsx`, `frontend/src/api/client.ts`

### P2 — Filter by Concept and Source

The tag table grows unbounded. Without filtering, it is unusable once you have more than ~30 tags.

**Design:** Two filter inputs above the table — a text input for concept (client-side substring filter on `concept_tag`) and a select for source (client-side filter; "all" default). Client-side is sufficient since the full list is already loaded. No API change needed.

**Files:** `frontend/src/pages/StudyLogPanel.tsx`

### P3 — Row-Select Prefill (Edit)

Streamlit allows clicking a row to pre-fill the form for editing. The UI-3 spec explicitly deferred this as "UX enhancement."

**Design:** Clicking a table row populates the Add Tag form fields with that row's data. On Save, the route issues a `PATCH /api/study-log/{id}` (new) to update the existing row rather than creating a new one. The form toggle button label changes to "Edit" when a row is selected; Escape or Cancel deselects.

**Files:** `src/neurodb/api/routes/study_log.py`, `frontend/src/pages/StudyLogPanel.tsx`

### P3 — Source List Alignment

React source select has `openneuro / pubmed / arxiv`. Streamlit has `openneuro / allen_brain / neurovault / dandi`. Neither is a superset.

**Design:** Include all six sources in the React select. Backend `tag_dataset` only checks whether the dataset exists in the DB — source is a free string, so adding more options requires no backend change.

---

## Datasets

### P2 — Modality Filter

Filtering by modality (MRI/fMRI/EEG/MEG/ISH) is fundamental to the neuroscience workflow. Without it, the browser shows an undifferentiated list.

**Design:** Add a modality select below the keyword input (options: All / MRI / fMRI / EEG / MEG / ISH). Pass `modality` as a query param to `GET /api/datasets?keyword=...&modality=...`. The existing `search_datasets(session, keyword, modality)` helper already accepts this param — the API route just needs to forward it.

**Enhancement:** Replace the single select with a row of filter chips (All / MRI / fMRI / EEG / MEG / ISH). Multi-select: click a chip to toggle it on/off. This reflects how researchers actually filter — MRI and fMRI together is a common combination. The chip state is passed as a comma-separated `modality` list to the API.

**Files:** `src/neurodb/api/routes/datasets.py`, `frontend/src/pages/DatasetsPanel.tsx`

### P2 — Rich Metadata in Results

React shows only `source` and `source_id`. Streamlit shows `title`, `modality`, and `n_subjects`. The data is almost certainly already returned by the API — it's just not rendered.

**Design:** Update `DatasetsPanel.tsx` result rows to show `title` (bold), `modality` (pill/badge), and `n_subjects` alongside `source:source_id`. Verify the `DatasetItem` type already includes these fields; if not, update `types.ts` and the API route response model.

**Files:** `frontend/src/pages/DatasetsPanel.tsx`, `frontend/src/api/types.ts`

### P3 — Inline Tag from Results

Streamlit lets you tag a dataset directly from the search result row. React requires switching to Study Log and re-entering the source ID.

**Design:** Add a small "Tag" button per result row. Clicking it opens a mini inline form (concept_tag text input + Save). On submit, calls `POST /api/study-log` with the row's source/source_id pre-filled. On success, shows a brief "Tagged" confirmation inline. No panel switch needed.

---

## Suggestions

### P1 — ImportQueue Status Update on Completion

When an import background task completes, `ImportQueue.status` is not updated. Items remain "pending" indefinitely after successful import.

**Design:** The background thread that runs the import connector should, on success, fetch the `ImportQueue` row for `(source, source_id)` and set `status = 'imported'`, `resolved_at = now`. Wrap in try/except so a DB write failure does not override a successful import result.

**Files:** `src/neurodb/api/routes/datasets.py` (background thread body)

### P1 — Promote Gating by Suggestion Type

React shows Promote on all `SourceSuggestion` rows. Streamlit shows it only when `suggestion_type == "learning_source"`. Promoting a dataset suggestion creates a `LearningSource` row using `suggestion.reference` as `source_key`, which may be a dataset ID rather than a DOI/URL — producing corrupt registry entries.

**Design:** `SourceSuggestionRow` in React should render the Promote button only when `item.suggestion_type === 'learning_source'`. No backend change needed.

**Files:** `frontend/src/pages/SuggestionsPanel.tsx`

### P1 — `added_by` Alignment on Promote

Streamlit hardcodes `added_by = 'user'` when a human promotes a suggestion. The UI-3 API route hardcodes `added_by = 'suggestion'`. This produces inconsistent registry provenance.

**Design:** Change the promote route to set `added_by = 'user'` — the human pressed Promote, so the record is human-initiated.

**Files:** `src/neurodb/api/routes/suggestions.py`

---

## Registry

### P1 — Topics Field in Add Form

The React add form has no topics input. Every entry added via React has `content_json = null`. For books this also means no chapter data. Sources added via React are permanently less detailed than those added via Streamlit.

**Design:** Add a topics textarea to the Add Source form (placeholder: "retinotopy, V1, pRF — comma separated"). On submit, serialize as `{"topics": [...]}` into `content_json`. For `source_type == 'book'`, keep the same field but label it "Topics" — chapter structure requires a separate chapter editor that is out of scope here.

**Files:** `frontend/src/pages/RegistryPanel.tsx`, `frontend/src/api/types.ts`, `src/neurodb/api/routes/registry.py` (accept `content_json` in POST body)

### P1 — `added_by` Hardcoded in Add Form

React exposes `added_by` as a free-text input, producing inconsistent provenance. Streamlit hardcodes "user".

**Design:** Remove `added_by` from the React form. The `POST /api/registry` route should hardcode `added_by = 'user'`. The field remains in the response model for display.

**Files:** `frontend/src/pages/RegistryPanel.tsx`, `src/neurodb/api/routes/registry.py`

### P3 — Content Expansion in Item Cards

Streamlit renders chapter lists for books and topic lists for other types. React shows a flat card.

**Design:** For items with non-null `content_json`, add a `<details>` expander to the item card (same pattern as KnowledgeLibraryPanel's summary expander). Parse `content_json.chapters` for books (render as "Ch1 — Title, Ch2 — Title…") and `content_json.topics` for others (render as comma-separated tags). API needs to return `content_json` in the `LearningSourceItem` response model; currently it may be omitted.

**Files:** `frontend/src/pages/RegistryPanel.tsx`, `src/neurodb/api/routes/registry.py`, `frontend/src/api/types.ts`

---

## Research

### P2 — Status Filters

Hypotheses span five statuses (draft / needs_evidence / ready_for_plan / archived / complete). Research questions span four (open / parked / converted_to_hypothesis / closed). Without filters, the lists grow unusable.

**Design:** Render a horizontal row of filter chips below each section header. Default is "all" (all chips deselected = show everything). Clicking a chip toggles that status on/off. Multi-select is allowed. Pass active status values as a `status` query param array to `GET /api/research/hypotheses` and `GET /api/research/questions`. Filter is server-side.

**Files:** `frontend/src/pages/ResearchPanel.tsx`, `src/neurodb/api/routes/research.py` (add status filter param)

### P2 — Hypothesis Detail Expansion

Mechanism, evidence, predictions, confounds, and limitations are the core content of a hypothesis. Currently invisible in React.

**Design:** Each `HypothesisCard` gets an expand/collapse toggle (chevron icon). When expanded, render:
- `mechanism` (prose text, `<p>`)
- Evidence: `evidence_json` parsed as a list, rendered as a `<ul>` under "Evidence"
- Predictions: `predictions_json` as `<ul>` under "Predictions"
- Datasets: `datasets_json` as `<ul>` under "Relevant Datasets"
- Confounds: `confounds_json` as `<ul>` under "Confounds"
- Limitations: `limitations_json` as `<ul>` under "Limitations"

All JSON fields are nullable — render each section only when non-null and non-empty. The `Hypothesis` type in `types.ts` needs to include these fields; the API response model needs to return them.

**Enhancement:** For a later pass, replace this inline expansion with a slide-over drawer panel. The drawer gives the full right-panel width for detailed reading, and can hold the review history as a scrollable list below the detail.

**Files:** `frontend/src/pages/ResearchPanel.tsx`, `frontend/src/api/types.ts`, `src/neurodb/api/routes/research.py`

### P2 — Accept Revisions / Dismiss Review Actions

These drive the hypothesis lifecycle. A review in "pending" status does nothing until acted on. Currently both actions are missing from React.

**Design:** Each `HypothesisReviewCard` gets two action buttons: "Accept Revisions" and "Dismiss". Both call new API routes:
- `POST /api/research/reviews/{id}/accept` — sets `status = 'accepted'`, calls `update_hypothesis_review_status(review_id, 'accepted', engine)`. Returns the updated review item.
- `POST /api/research/reviews/{id}/dismiss` — sets `status = 'dismissed'`. Returns 204.

On success, invalidate `['hypothesis-reviews', hypothesis.id]`. Buttons are only shown when `review.status === 'pending'`.

**Files:** `frontend/src/pages/ResearchPanel.tsx`, `src/neurodb/api/routes/research.py`, `frontend/src/api/client.ts`

---

## Knowledge Library

### P1 — ChromaDB Indexing on Approve

Sources approved via React are not indexed in ChromaDB. Semantic search only finds items approved through Streamlit.

**Design:** The `POST /api/knowledge-library/{id}/approve` route should, after setting `status = 'approved'`, call `knowledge_store.add_summary(source_id=item.id, title=item.title, summary=item.summary or '', topic_context=item.topic_context)`. The `knowledge_store` dependency is already wired in other routes.

**Files:** `src/neurodb/api/routes/knowledge_library.py`

### P2 — LLM Summary Generation on Approve

Streamlit generates an LLM summary on approve via `TaskRouter.route("summary.knowledge_source")`. React approve just flips the status bit — approved items have no summary.

**Design:** Wire this as a background task (same pattern as import and hypothesis review). On approve click:
1. `POST /api/knowledge-library/{id}/approve` → returns `{"task_id": "..."}` immediately; sets status to 'approved' and starts background thread that generates the summary and writes it to the row.
2. React uses `useTask` with `timeoutMs=120000` and `successMessage="Summary generated"`.
3. On task success, invalidate `['knowledge-library']`.

The background thread calls `router.route("summary.knowledge_source")` → model call → sets `summary` on the `KnowledgeSource` row. After write, calls `knowledge_store.add_summary(...)` (combines with P1).

**Files:** `src/neurodb/api/routes/knowledge_library.py`, `frontend/src/pages/KnowledgeLibraryPanel.tsx`

### P2 — Near-Duplicate Detection

Streamlit warns before approve if ChromaDB distance to an existing approved source is below a threshold. React approves silently, accumulating duplicates.

**Design:** Before approve (client-side), call `GET /api/knowledge-library/{id}/duplicates` which queries ChromaDB for the top-k nearest approved sources by title/topic_context embedding. If any result has distance below threshold (0.12), the API returns those candidates. React renders a warning banner: "Similar sources already approved: [Title A, Title B]. Approve anyway?" — two buttons: Cancel and Approve Anyway. If no duplicates found, approve proceeds directly.

**Files:** `src/neurodb/api/routes/knowledge_library.py`, `frontend/src/pages/KnowledgeLibraryPanel.tsx`

### P3 — DOI as Clickable Link

DOI is rendered as plain text in React.

**Design:** If `item.doi` starts with `10.` (bare DOI), render as `<a href="https://doi.org/{item.doi}" target="_blank">`. If it starts with `http`, render as-is. Otherwise render as plain text. No API change needed.

**Files:** `frontend/src/pages/KnowledgeLibraryPanel.tsx`

---

## SQL

### P3 — Table Catalog Hint

Streamlit shows a caption listing available tables. React does not.

**Design:** Add a small help text below the textarea: "Tables: `v_dataset_summary`, `openneuro_datasets`, `datasets_index`, `subjects`, `ingest_runs`" (styled as a hint, not a header). Update the default query to `SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;` to match Streamlit.

**Files:** `frontend/src/pages/SqlPanel.tsx`

---

## Enhancements Summary

| Enhancement | Capability | Notes |
|---|---|---|
| Tool activity log as collapsible pane per turn | Chat | Keeps transcript readable; requires useChat event accumulation |
| Clear + auto-summarize | Chat | Requires new API route |
| LLM summary as background task | Knowledge Library | Same pattern as import/review |
| Near-duplicate check before approve | Knowledge Library | Requires ChromaDB query route |
| Modality filter chips (multi-select) | Datasets | Exceeds Streamlit single-select |
| Hypothesis detail slide-over (later pass) | Research | Deferred; inline expansion is P2 |
| Study log bulk delete via checkboxes | Study Log | Deferred enhancement; row delete is P2 |

---

## File Map (preliminary)

| Change | File |
|---|---|
| Modify | `src/neurodb/api/routes/study_log.py` |
| Modify | `src/neurodb/api/routes/suggestions.py` |
| Modify | `src/neurodb/api/routes/datasets.py` |
| Modify | `src/neurodb/api/routes/registry.py` |
| Modify | `src/neurodb/api/routes/research.py` |
| Modify | `src/neurodb/api/routes/knowledge_library.py` |
| Modify | `src/neurodb/api/routes/sessions.py` |
| New | `src/neurodb/api/routes/knowledge_library.py` (duplicate check) |
| Modify | `frontend/src/pages/ChatPanel.tsx` |
| Modify | `frontend/src/hooks/useChat.ts` |
| Modify | `frontend/src/pages/StudyLogPanel.tsx` |
| Modify | `frontend/src/pages/DatasetsPanel.tsx` |
| Modify | `frontend/src/pages/SuggestionsPanel.tsx` |
| Modify | `frontend/src/pages/RegistryPanel.tsx` |
| Modify | `frontend/src/pages/ResearchPanel.tsx` |
| Modify | `frontend/src/pages/KnowledgeLibraryPanel.tsx` |
| Modify | `frontend/src/pages/SqlPanel.tsx` |
| Modify | `frontend/src/api/client.ts` |
| Modify | `frontend/src/api/types.ts` |

---

## Out of Scope (UI-5)

- Streamlit code deletion (UI-4)
- Research question create/update actions (LOG-037)
- Hypothesis chapter editor for books (requires structured JSON editor)
- Provider selection UI (Config Control epoch)
- Monaco editor for SQL panel (already deferred in UI-3)
- Full hypothesis slide-over drawer (deferred to later pass within UI-5 or UI-6)
