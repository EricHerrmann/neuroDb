# UI-5 P3 Polish Design

**Date:** 2026-05-13
**Status:** Implemented 2026-05-13; common manual verification pending
**Epoch:** UI
**Source:** `docs/superpowers/specs/2026-05-12-ui5-parity-completion-design.md`
**Manual plan:** `docs/testsPlans/manualTestPlan_ui5_common_parity.md`

---

## Goal

Finish the remaining UI-5 polish gaps after P1 data integrity and P2 core
workflow work. P3 should improve day-to-day usability and Streamlit parity
without changing the broader FastAPI/React architecture or starting UI-4
Streamlit retirement.

---

## Scope

| Area | Capability | User value |
|---|---|---|
| Chat | Prior context banner | User can see when an answer is grounded in a previous session topic |
| Study Log | Row-select edit path | Existing notes can be corrected without creating duplicates |
| Study Log | Source list alignment | Tags can be created consistently for OpenNeuro, Allen Brain, NeuroVault, DANDI, PubMed, and arXiv |
| Datasets | Inline tag from result rows | User can tag a dataset without switching panels and retyping source IDs |
| Registry | Content expansion in cards | Topics and book chapters are visible in the React registry |
| Knowledge Library | DOI clickable link | Papers can be opened directly from approved sources |
| SQL | Table catalog hint and default query | Query panel starts from a useful local catalog view |

Out of scope:

- Streamlit deletion or retirement decision.
- Research question create/update actions tracked by `LOG-037`.
- Knowledge Library duplicate removal tracked by `LOG-056`.
- Broad component framework work or a generic panel abstraction pass.
- Enhancements that exceed the P3 parity list, such as SQL Monaco editor,
  hypothesis slide-over drawer, or multi-select modality chips.

---

## Design Principles

1. Keep P3 changes small and vertical. Each feature should land with its route,
   API type, UI behavior, and focused tests where applicable.
2. Prefer shared constants for source lists and status labels when the same
   values appear in multiple UI panels, but avoid a broad abstraction layer.
3. Manual testing uses one consolidated UI-5 plan so P1, P2, and P3 are verified
   together in the same running app and database.
4. P3 must not weaken P1 data-integrity guarantees: edit/tag workflows that
   update DuckDB must update ChromaDB or surface a warning.

---

## Chat

### Prior Context Banner

Design:

- Expose active prior context through either `GET /api/preferences` or a narrow
  `GET /api/sessions/active-context` route. The response shape should be
  explicit: `{"active_prior_topic": string | null}`.
- Render a compact pill below the chat header when a topic is present.
- Do not render an empty placeholder when no context is active.
- Keep the banner informational only; changing active context is not part of P3.

Acceptance:

- A mocked active context renders the topic in Chat.
- No topic produces no banner and no layout gap.

---

## Study Log

### Row-Select Edit Path

Design:

- Add `PATCH /api/study-log/{id}` with a request body containing editable fields:
  `source`, `source_id`, `concept_tag`, `section_ref`, and `note_text`.
- Route updates the `StudyNote` row and refreshes the vector note embedding.
- If embedding refresh fails after the DB update, return the updated row with a
  warning, matching the P1 warning pattern.
- In React, clicking a row selects it and pre-fills the form.
- The form switches from add mode to edit mode with Save and Cancel controls.
- Escape or Cancel clears the selected row and restores add mode.

Acceptance:

- Editing a note changes the visible row and survives reload.
- Edited note content is searchable through the manual vector helper or the
  existing semantic search surface.
- Vector refresh failure is visible to the user instead of silent.

### Source List Alignment

Design:

- Use one source option list for Study Log and dataset-tagging entry points:
  `openneuro`, `allen_brain`, `neurovault`, `dandi`, `pubmed`, `arxiv`.
- Prefer a local frontend constant first. If backend validation later needs the
  same list, move it to a shared API response or schema enum then.

Acceptance:

- Study Log source select includes all six sources.
- Dataset inline tag flow uses the source from the row and does not require
  manual source selection.

---

## Datasets

### Inline Tag From Result Rows

Design:

- Add a compact Tag action to each dataset result row.
- Clicking Tag opens an inline form prefilled with `source` and `source_id`.
- Form asks only for `concept_tag`, with optional `section_ref` and `note_text`
  if the existing Study Log form already exposes them compactly.
- Submit calls `POST /api/study-log`.
- Success shows a short row-local confirmation and invalidates Study Log data.
- Warnings from study-log embedding are displayed row-locally.

Acceptance:

- A dataset can be tagged without switching to Study Log.
- The new tag appears in Study Log after refresh.
- Embedding warnings are not lost.

---

## Registry

### Content Expansion in Item Cards

Design:

- Ensure registry API responses include `content_json`.
- Update frontend types to represent `content_json` as nullable structured data.
- Render a `<details>` section on cards only when content exists.
- For books, render `chapters` as a compact chapter list.
- For other source types, render `topics` as tags or a compact comma-separated
  list.
- Invalid or unexpected content should degrade to a small raw summary instead of
  crashing the panel.

Acceptance:

- A registry item with `{"topics": [...]}` shows topics in React.
- A book with chapter data shows chapter labels/titles.
- Items without content keep the current compact card.

---

## Knowledge Library

### DOI Clickable Link

Design:

- If `doi` starts with `10.`, link to `https://doi.org/{doi}`.
- If `doi` starts with `http://` or `https://`, link directly.
- Otherwise render plain text.
- Links open in a new tab and include `rel="noreferrer"`.

Acceptance:

- Bare DOI values open the DOI resolver.
- Existing URL values remain valid links.
- Non-DOI identifiers are not turned into broken links.

---

## SQL

### Table Catalog Hint and Default Query

Design:

- Add a small hint near the SQL textarea listing common local tables/views:
  `v_dataset_summary`, `openneuro_datasets`, `datasets_index`, `subjects`, and
  `ingest_runs`.
- Change the default query to:

```sql
SELECT * FROM v_dataset_summary ORDER BY n_datasets DESC;
```

Acceptance:

- Opening SQL shows the useful default query.
- The table hint is visible without dominating the panel.

---

## Test Strategy

Automated tests:

- Backend route tests for `PATCH /api/study-log/{id}` and registry
  `content_json` response coverage.
- Frontend tests for selected-row edit mode, inline dataset tagging, DOI link
  rendering, registry content expansion, prior-context banner, and SQL default
  query text.
- Existing P1/P2 tests remain the regression base.

Manual tests:

- Use `docs/testsPlans/manualTestPlan_ui5_common_parity.md` as the single UI-5
  manual plan across P1, P2, and P3.

---

## Implementation Order

1. SQL hint/default query and Knowledge Library DOI link.
2. Registry `content_json` response and content expansion.
3. Study Log `PATCH` route, selected-row edit mode, and shared source options.
4. Dataset inline tag workflow.
5. Chat prior-context route/field and banner.
6. Consolidated automated and manual verification.

---

## Open Questions

| Question | Working assumption |
|---|---|
| Should prior context live on preferences or sessions? | Prefer sessions if the value is session-derived; preferences only if the app already computes it there. |
| Should source options be backend-driven? | Use a frontend constant for P3, then move backend-driven if validation appears in more than one API. |
| Should inline dataset tagging expose full Study Log fields? | Start compact: concept required, section/note optional only if layout stays clean. |
| Should `LOG-056` duplicate removal be included? | No. P3 keeps duplicate warning parity; deletion/removal is a separate Knowledge Library backlog item. |
