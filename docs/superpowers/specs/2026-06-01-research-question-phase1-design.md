# Research Question Phase 1 — Capture & Categorize

**Date:** 2026-06-01
**Lifecycle stages served:** Capture (1), Categorize (2)
**Source design:** `docs/researchQuestionDesignClaude.md` Phase 1
**Status:** Spec — ready for implementation plan

---

## Goals

1. A research question can be created directly in the UI without going through the agent chat.
2. When a question is created, the Research agent suggests relevant topics and concepts drawn from the existing DB taxonomy; the user confirms or dismisses each suggestion.
3. Pending suggestions survive page refresh — they are persisted in the DB until resolved.
4. Confirmed topics are visible as badges on each question row.
5. Questions can be filtered by topic or status, and the question list is collapsible.
6. Questions can be deleted with cascade cleanup of all join rows.

---

## Section 1 — Schema

### `question_topics` join table

```
question_topics(
  id            INTEGER PRIMARY KEY,
  question_id   FK → research_questions  NOT NULL,
  topic_id      FK → topics              NOT NULL,
  status        TEXT    NOT NULL DEFAULT 'pending',   -- 'pending' | 'confirmed'
  created_at    TIMESTAMP NOT NULL DEFAULT now()
)
UNIQUE(question_id, topic_id)
```

`status='pending'` rows are agent suggestions awaiting user action. `status='confirmed'` rows are accepted associations. Dismissing a suggestion deletes the row. Mirrors the `papers.source_status` candidate→approved lifecycle.

### `question_concepts` join table

```
question_concepts(
  id            INTEGER PRIMARY KEY,
  question_id   FK → research_questions  NOT NULL,
  concept_id    FK → concepts            NOT NULL,
  status        TEXT    NOT NULL DEFAULT 'pending',
  created_at    TIMESTAMP NOT NULL DEFAULT now()
)
UNIQUE(question_id, concept_id)
```

Same pending/confirmed semantics as `question_topics`.

### `research_questions.origin_session_id`

New nullable column: `origin_session_id FK → chat_sessions` — records the session that first surfaced the question, providing provenance.

### Migration

The existing `research_questions.topic_id` nullable FK stays in place. The migration populates `question_topics` (status=`confirmed`) from any non-null `topic_id` rows so no existing data is lost. The old FK is not removed in this phase; it remains backward-compatible for `get_question_bundle()` until Phase 2 updates that function.

---

## Section 2 — API

All routes are added to the existing research router.

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/research/questions` | Create question — body: `{question, topic_context?, origin_session_id?}` |
| PUT | `/api/research/questions/{id}` | Edit question text and `topic_context` |
| DELETE | `/api/research/questions/{id}` | Delete question and cascade all join rows |
| GET | `/api/research/questions/{id}` | Single question detail — returns question + confirmed topics + confirmed concepts + status |
| POST | `/api/research/questions/{id}/topics` | Add a topic link — body: `{topic_id}`; always creates as `confirmed` |
| PATCH | `/api/research/questions/{id}/topics/{topic_id}` | Update status on an existing link — body: `{status}`; used to confirm a pending suggestion |
| DELETE | `/api/research/questions/{id}/topics/{topic_id}` | Remove a topic link (any status) |
| POST | `/api/research/questions/{id}/concepts` | Add a concept link — body: `{concept_id}`; always creates as `confirmed` |
| PATCH | `/api/research/questions/{id}/concepts/{concept_id}` | Update status on an existing concept link |
| DELETE | `/api/research/questions/{id}/concepts/{concept_id}` | Remove a concept link |
| GET | `/api/research/questions?topic_id={id}&status={status}` | Extend existing list route — add `topic_id` filter (over confirmed links only) |

**Confirm/dismiss flow:** confirming a pending chip calls `PATCH /api/research/questions/{id}/topics/{topic_id}` with `{status: "confirmed"}`; dismissing calls `DELETE /api/research/questions/{id}/topics/{topic_id}`. Same pattern applies to concept chips.

**Delete cascade:** `DELETE /api/research/questions/{id}` removes the question row and cascades to `question_topics` and `question_concepts`. It does not remove referenced topics, concepts, hypotheses, or gaps — only the join rows and the question itself.

---

## Section 3 — Agent

### `extract_question_topics` tool (Research agent)

Called automatically within the same `record_research_question` turn — not a separate agent invocation or background job from the agent side.

Behavior:
- Runs a lightweight analysis of the question text against existing topics and concepts in the DB.
- Persists matches as `status='pending'` rows in `question_topics` and `question_concepts` before returning.
- Returns a summary so the turn response includes the suggestion count.
- If no existing topics or concepts match well, returns empty arrays — does not create new topics or concepts.

Response shape:
```json
{
  "question_id": 42,
  "suggested_topics": ["memory and retrieval", "LLM architecture analogies"],
  "suggested_concepts": ["semantic memory", "vector embeddings", "pattern completion"]
}
```

**UI-created questions:** when a question is created via the API (not via agent chat), the POST handler triggers an async agent call to `extract_question_topics` in the background. Pending rows appear when the user next views the question list; no spinner or wait is required on the creation form.

---

## Section 4 — UI

### ResearchPanel — question creation form (new)

- Text area for question text; optional `topic_context` field; Submit button.
- Submit calls `POST /api/research/questions`, returns immediately, triggers background agent extraction.
- No spinner required — pending chips appear on next list render once the agent call completes.

### ResearchPanel — question list

- **Collapsible:** section header has an expand/collapse toggle; collapsed state persists in local component state.
- **Question rows:** each row shows confirmed topic badges and any unresolved pending suggestion chips inline.
  - Confirm chip → `PATCH /api/research/questions/{id}/topics/{topic_id}` with `{status: "confirmed"}`.
  - Dismiss chip → `DELETE /api/research/questions/{id}/topics/{topic_id}`.
  - Same pattern for concept chips.
- **Delete action:** each row has a Delete control. Clicking shows a confirmation prompt before calling `DELETE /api/research/questions/{id}`. On success the row is removed from the list.
- **Filter bar:** filter by topic (drives `?topic_id=X`; applies over confirmed links only) or by status. Filters stack.

No question detail view in this phase — suggestion review and topic management are handled inline on the list row.

---

## Section 5 — Test Plan

All tests must be written before implementation begins per CLAUDE.md.

### Prerequisites

Run `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.

### Automated tests

| # | Type | Description |
|---|---|---|
| T1 | Unit | `question_topics` CRUD: insert, confirm, dismiss (delete), unique constraint rejects duplicate |
| T2 | Unit | `question_concepts` CRUD: same as T1 |
| T3 | Unit | Migration populates `question_topics` (status=`confirmed`) from existing non-null `topic_id` rows; existing `topic_id` FK remains intact |
| T4 | Unit | `extract_question_topics` returns plausible suggestions for a sample question text; persists pending rows; empty arrays when no matches |
| T5 | Unit | `DELETE /api/research/questions/{id}` removes question and cascades join rows; does not touch topics, concepts, hypotheses, or gaps |
| T6 | Integration | Create question via API → agent suggests topic → confirm suggestion → `GET /api/research/questions?topic_id=X` returns the question |
| T7 | Idempotency | Adding the same topic link twice does not create a duplicate row (unique constraint + upsert behavior verified) |

### Manual tests

| # | Description | Pass criterion |
|---|---|---|
| M1 | Create question from UI form | Question appears in list; pending chips appear after agent background call completes |
| M2 | Confirm a suggested topic | Chip becomes a badge; `GET /api/research/questions/{id}` shows topic as confirmed |
| M3 | Dismiss a suggested topic | Chip disappears; topic no longer in question's topic list |
| M4 | Filter question list by topic | Only questions with that confirmed topic appear |
| M5 | Collapse and expand question list | State persists within session |
| M6 | Delete a question | Confirmation prompt fires; question removed from list; `GET /api/research/questions/{id}` returns 404 |

---

## Open Design Questions (deferred, not blocking Phase 1)

1. **Four-axis categorization taxonomy** (type, maturity, evidence posture, learning state): deferred until Phase 1 topic/concept tagging is in use and the need is observed in practice.
2. **Inquiry as explicit context mode on topics**: if the user wants inquiry mode without an active question focus, a fourth context mode selector becomes necessary. Revisit after Phase 3.

---

_Update `docs/researchQuestionDesignClaude.md` when Phase 1 implementation begins. Manual test plan must be created in `docs/testsPlans/` before implementation starts._
