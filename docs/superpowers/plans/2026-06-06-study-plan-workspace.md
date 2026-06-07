# Study Plan Workspace Phased Implementation Plan

**Goal:** Make Study Plan the primary UI driver for learning and research work,
with tags, chats, sources, and progress organized around an active plan.

**Current baseline:** Learning Plans store a proposed/active plan shell and flat
ordered `plan_steps`. Tags and chats remain sibling views under the former Study
Log panel. Read-step paper titles are now surfaced through the plan detail API so
confirmed read steps remain readable after paper resolution.

**Scope note:** This plan is intentionally phased. Phase 1 is a narrow polish
and naming pass. Later phases require schema/API changes and should each get
their own tests and manual gate updates before implementation.

---

## Phase 1 — Readable Steps + Study Plan Naming

**Goal:** Make the current Learning Plans feature readable and consistently
named without changing its storage model.

- Return read-step display metadata from `GET /api/research/plans/{id}`:
  `source_title`, `source_type`, and `topic_context`.
- Render read-step titles in the plan detail UI before and after confirmation.
- Rename visible "Study Log" labels to "Study Plan" while keeping existing
  route/API identifiers stable for compatibility.
- Update the pending Learning Plans manual test plan to expect Study Plan naming.

**Exit criteria:** Existing proposed and active plans show meaningful read-step
titles in the Study Plan panel; tests cover proposed and confirmed read steps.

---

## Phase 2 — Phase/Section Structure

**Goal:** Preserve the structure users naturally expect from agent-authored
plans, such as "PHASE 1 — Biological Ground Truth."

- Add optional section metadata to plan steps, either as `section_title` on
  `plan_steps` or a separate `plan_sections` table if section-level ordering,
  summaries, or lifecycle state are needed.
- Extend `propose_learning_plan` and `update_learning_plan` tool schemas so
  agents can provide sectioned steps directly.
- Render grouped steps in Study Plan detail.
- Keep flat step ordering as a compatibility fallback for existing plans.

**Exit criteria:** New plans can persist and render named sections; existing
flat plans still load and can be edited.

---

## Phase 3 — Plan-Linked Tags And Notes

**Goal:** Make tags/notes supporting artifacts inside the active plan rather
than a separate sibling list.

- Add plan/step anchors for study notes.
- Allow note creation from a plan step.
- Show notes under the active plan and optionally under each step.
- Preserve the existing `/api/study-log` routes until a compatibility migration
  is deliberately planned.

**Exit criteria:** A note can be attached to a plan or step, appears in the plan
workspace, and remains queryable through existing study-note APIs.

---

## Phase 4 — Plan-Linked Chats

**Goal:** Treat chat sessions as activity that advances a plan.

- Add optional `plan_id` and `step_id` lineage to chat sessions or a join table.
- Let users start or continue a chat from a plan step.
- Show related chat sessions and summaries inside the active plan.
- Make agent-proposed plan updates reference the chat session that produced them.

**Exit criteria:** Chats can be filtered by active plan, and plan updates can be
traced back to the session that proposed them.

---

## Phase 5 — Study Plan As Primary Workspace

**Goal:** Promote Study Plan from one panel view to the main organizing surface.

- Default the Study Plan panel to Plans rather than tags.
- Add an active-plan selector and current-step/next-action affordance.
- Move tags and chats into plan-scoped supporting sections.
- Surface progress, pending changes, linked sources, linked notes, and related
  chats in one plan-centric detail view.

**Exit criteria:** A user can choose an active plan and drive daily work from
that plan without switching to separate Tags or Chats views for routine actions.

---

## Phase 6 — Agent Plan Operations

**Goal:** Let Tutor and Research agents operate against the active plan with
clear user approval gates.

- Add active-plan context to agent prompt bundles.
- Let agents propose step additions, removals, reordering, and section changes.
- Keep all agent changes in a proposed state until user confirmation.
- Record rationale and source/chats behind each proposed change.

**Exit criteria:** Agents can help maintain the Study Plan, but every structural
change remains auditable and user-confirmed.
