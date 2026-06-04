# Phase 5b — Evidence Lens, Dataset Honesty, and Retract Lifecycle

**Date:** 2026-05-21
**Status:** Complete — implemented and signed off 2026-05-23
**Epoch:** UI (frontend-heavy) + DB migrations + API endpoints
**Parent spec:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md`

---

## Goal

Surface evidence provenance in chat responses, display dataset readiness honestly in the Datasets panel, and give users control over the lifecycle of research objects (claims, evidence links, questions, gaps) through status transitions.

P5b is the second half of Phase 5 from the parent spec. P5a (Focus Controls) shipped the context mode selector and agent in-progress feedback. P5b closes the remaining Phase 5 deliverables: per-answer evidence lens, dataset honesty display, and retract lifecycle for four research object types.

---

## Non-Goals

- Approved paper retract lifecycle (Knowledge Library — deferred; not in LOG-061 confirmed scope)
- Hypothesis archive/dismiss (LOG-048 — separate issue)
- Active focus selector / research question workspace tabs (deferred to P5c or later)
- Per-answer source ID drill-down with specific paper IDs, DOIs, claim IDs (requires Agent Core structured metadata — deferred)
- Dataset Honesty in surfaces other than the Datasets panel

---

## Architecture

### 1. DB Migrations

Two new migrations following migration 7.

**Migration 8 — EvidenceLink status**

```sql
ALTER TABLE evidence_links ADD COLUMN status VARCHAR DEFAULT 'active'
```

Values: `'active'` | `'retracted'`. All existing rows default to `'active'`. Migration is wrapped in a try/except to be idempotent.

**Migration 9 — ResearchQuestion status**

```sql
ALTER TABLE research_questions ADD COLUMN status VARCHAR DEFAULT 'open'
```

If the column already exists the `ALTER TABLE` is caught and skipped. Adds support for `'archived'` as a valid value. A supporting index is created:

```sql
CREATE INDEX IF NOT EXISTS ix_research_questions_status ON research_questions (status)
```

---

### 2. API Endpoints

All new endpoints in `src/neurodb/api/routes/research.py`.

| Method | Route | Action |
|---|---|---|
| `POST` | `/api/research/evidence-links/{id}/retract` | Sets `status = 'retracted'` |
| `POST` | `/api/research/questions/{id}/archive` | Sets `status = 'archived'` |
| `POST` | `/api/research/claims/{id}/approve` | Sets `status = 'approved'` |
| `POST` | `/api/research/claims/{id}/reject` | Sets `status = 'rejected'` |
| `POST` | `/api/research/gaps/{id}/resolve` | Sets `status = 'resolved'` |
| `POST` | `/api/research/gaps/{id}/archive` | Sets `status = 'archived'` |

All endpoints return the updated object. All use existing SQLAlchemy session patterns. No hard deletes.

**Dataset API update (`src/neurodb/api/routes/datasets.py`):**

`GET /api/datasets` LEFT JOINs with `dataset_research_packets` to include `usefulness_state` and `missing_context` in each result. Both fields are nullable — datasets without a research packet return `null` for both.

---

### 3. Frontend: Evidence Lens

**Data source:** The `context_summary` SSE event emitted by Phase 4 Agent Core already contains all required fields: `context_mode`, `papers_count`, `notes_count`, `claims_count`, `datasets_count`, `gaps_count`. No backend changes required for this feature.

**`Message` interface extension (`frontend/src/hooks/useChat.ts`):**

```ts
evidenceSummary?: {
  mode: string
  papers: number
  notes: number
  claims: number
  datasets: number
  gaps: number
} | null
```

When the `context_summary` event arrives in the SSE loop, it is attached to the current assistant message using the same pattern as `activity` on `tool_start`.

**`MessageBubble.tsx` rendering:**

When `message.evidenceSummary` is present, a second `<details>` element is rendered below the message content alongside the existing tool-trace `<details>`.

Collapsed label:
```
▸ Evidence: {mode} · {papers}p · {notes}n · {claims}c · {datasets}d
```
If `gaps > 0`, a gap warning is appended: `· ⚠ {gaps} gap`.

Expanded body: same counts in a readable list, gaps count rendered in amber.

The evidence lens only appears when a `context_summary` event was received for the message. It does not appear for `local_db` or `external_db` turns.

---

### 4. Frontend: Dataset Honesty

**`DatasetItem` type extension (`frontend/src/api/types.ts`):**

```ts
usefulness_state?: 'sparse' | 'partial' | 'research_context_ready' | 'analysis_ready' | null
missing_context?: string | null
```

**Datasets panel card rendering:**

Each result card renders a left-border color and an inline state label + gap note in the subtitle row when `usefulness_state` is non-null.

| State | Left border | Inline label |
|---|---|---|
| `sparse` | `#ef4444` (red) | `sparse — {missing_context}` |
| `partial` | `#f59e0b` (amber) | `partial — {missing_context}` |
| `research_context_ready` | `#22c55e` (green) | `research context ready` |
| `analysis_ready` | `#22c55e` (green) | `analysis ready` |
| `null` | none | none |

Datasets without a research packet (null state) render as today — no border treatment, no label. Backward compatible.

---

### 5. Frontend: Retract Lifecycle UI

#### StatusChip Component (`frontend/src/components/StatusChip.tsx` — new)

A small reusable component used by all four retract surfaces.

Props:
```ts
interface StatusChipProps {
  status: string
  transitions: { label: string; onSelect: () => void }[]
  isPending?: boolean
}
```

Behavior:
- Renders the current status as a colored pill
- Clicking opens an inline dropdown below the chip listing available transitions
- Clicking a transition fires `onSelect`, closes the dropdown, and shows a pending state until the mutation resolves
- Color mapping: `open` / `active` / `candidate` → blue-grey; `approved` / `resolved` → green; `rejected` / `retracted` / `archived` → red/muted

#### Research Questions (existing cards, new chip)

Each research question card gains a `StatusChip` in the top-right. Valid transitions:

| Current status | Available transitions |
|---|---|
| `open` | Archive |
| `active` | Archive |
| `archived` | — (no further transitions) |

Archive calls `POST /api/research/questions/{id}/archive`.

#### Claims (new accordion section in Research panel)

A collapsible "Claims" section is added to the Research panel below the existing research questions list. Each claim card shows the claim text, source reference, and a `StatusChip`.

Valid transitions:

| Current status | Available transitions |
|---|---|
| `candidate` | Approve, Reject, Archive |
| `approved` | Reject, Archive |
| `rejected` | Archive |
| `archived` | — |

#### Research Gaps (new accordion section in Research panel)

A collapsible "Gaps" section is added to the Research panel. Each gap card shows the gap description and a `StatusChip`.

Valid transitions:

| Current status | Available transitions |
|---|---|
| `open` | Resolve, Archive |
| `resolved` | Archive |
| `archived` | — |

#### Evidence Links (within hypothesis detail expansion)

Evidence links are embedded in the expanded hypothesis card view. Each link item gains a `StatusChip`.

Valid transitions:

| Current status | Available transitions |
|---|---|
| `active` | Retract |
| `retracted` | — |

#### Query invalidation

All four status mutations invalidate the relevant query key on success so the list refreshes without a page reload. Research questions: `['research-questions']`. Claims: `['claims']`. Gaps: `['research-gaps']`. Evidence links: `['hypotheses']` (they render within the hypothesis detail).

---

## Files

| File | Change |
|---|---|
| `src/neurodb/db.py` | Migration 8 (evidence_links.status) + Migration 9 (research_questions.status) |
| `src/neurodb/api/routes/research.py` | 6 new retract/archive/approve/reject endpoints |
| `src/neurodb/api/schemas/research.py` | Add `status` field to EvidenceLink, ResearchQuestion response schemas |
| `src/neurodb/api/routes/datasets.py` | LEFT JOIN with dataset_research_packets; add usefulness_state and missing_context |
| `src/neurodb/api/schemas/datasets.py` | Add `usefulness_state` and `missing_context` to DatasetItem schema |
| `frontend/src/hooks/useChat.ts` | Add `evidenceSummary` to `Message`; handle `context_summary` SSE event |
| `frontend/src/components/MessageBubble.tsx` | Render evidence lens `<details>` when `evidenceSummary` present |
| `frontend/src/api/types.ts` | Add `evidenceSummary` to `Message`; add `usefulness_state` + `missing_context` to `DatasetItem` |
| `frontend/src/api/client.ts` | Add `api` methods for the 6 new retract/archive endpoints |
| `frontend/src/components/StatusChip.tsx` | New — reusable status chip with inline dropdown |
| `frontend/src/pages/ResearchPanel.tsx` | Add Claims accordion, Gaps accordion; status chips on question cards and evidence links |

---

## Testing

### Automated (unit)

| Test | Coverage |
|---|---|
| Migration 8 idempotent — re-run does not fail | DB migration |
| Migration 9 idempotent — re-run does not fail | DB migration |
| `POST /api/research/evidence-links/{id}/retract` sets status | Retract endpoint |
| `POST /api/research/questions/{id}/archive` sets status | Archive endpoint |
| `POST /api/research/claims/{id}/approve` and `/reject` set status | Claim transitions |
| `POST /api/research/gaps/{id}/resolve` and `/archive` set status | Gap transitions |
| `GET /api/datasets` includes `usefulness_state` and `missing_context` when packet exists | Dataset API |
| `GET /api/datasets` returns null fields when no packet | Dataset API backward compat |
| `context_summary` event attaches `evidenceSummary` to current message | useChat |
| Evidence lens `<details>` renders when `evidenceSummary` present | MessageBubble |
| Evidence lens absent when `evidenceSummary` is null | MessageBubble |
| Gap warning appended when `gaps > 0` | MessageBubble |
| StatusChip renders correct color for each status category | StatusChip |
| StatusChip transitions list matches current status | StatusChip |
| Dataset card shows left-border and label for each usefulness state | Datasets panel |
| Dataset card shows no border when usefulness_state is null | Datasets panel |

### Manual

| Step | Pass criterion |
|---|---|
| Submit a Neuro Tutor message in Contextual mode | Evidence lens `<details>` appears below response; collapsed label shows mode and counts |
| Expand evidence lens | Counts match what agent used; gaps shown in amber if present |
| Submit a message in Local DB mode | No evidence lens appears |
| Open Datasets panel; search for any dataset | Result cards with a research packet show colored left-border and usefulness label |
| Dataset with no research packet | Card renders as before — no border, no label |
| Open Research panel; locate a research question | Status chip visible; Archive transition fires and status updates |
| Open Claims section | Claim cards visible with status chips; Approve/Reject/Archive transitions work |
| Open Gaps section | Gap cards visible; Resolve/Archive transitions work |
| Expand a hypothesis with evidence links | Each link has a Retract chip; Retract fires and link shows `retracted` |

---

## Open Items Addressed

| Log ID | Resolution |
|---|---|
| LOG-061 | Evidence links, claims, gaps, and research questions all get status chips with valid-transition dropdowns; EvidenceLink and ResearchQuestion gain DB status fields |

## Deferred

| Item | Deferred to |
|---|---|
| Approved paper retract (Knowledge Library) | Later UI pass |
| Hypothesis archive / dismiss | LOG-048 — separate issue |
| Active focus selector | P5c or later UI pass |
| Per-answer source ID drill-down | Requires Agent Core structured metadata |
