# Learning Plans — Feature Capture & Design

- **Date:** 2026-06-02
- **Status:** Captured from use; design approved at capture level. Placement and sequencing deferred (see Placement).
- **Candidate epoch:** Research (`src/neurodb/research/`), with a Tutor-epoch agent tool and a UI panel.
- **Origin:** Surfaced from real use — the NeuroTutor produced a good reading plan for a research question, but the only way to keep it was to copy it into a Word doc by hand. Saving, working through, and cross-referencing plans should be built in.

## Problem

The tutor generates reading/study plans today and then discards them. There is no
persistence, no per-step progress, and no way to relate work across the multiple
plans a user runs concurrently. The user must manually save plans outside the tool
and has no in-app view of "where am I across all my plans."

**Not currently planned (verified 2026-06-02):** the Research-question lifecycle
(`docs/researchQuestionDesignClaude.md`, `2026-06-01-research-question-phase1-design.md`)
tracks a *question's* maturation toward a hypothesis (capture → categorize → status
→ evidence/gaps). It does not cover a user-facing, savable, multi-step learning plan
with per-step progress and cross-plan source/topic sharing. This feature is new and
sits between the Tutor epoch (generates plans) and the Research epoch (questions,
cross-referencing).

## Intent (from clarifying questions)

1. A plan is a **standalone first-class object**, not required to hang off a question
   — but its "where are we on the plan" maturation naturally parallels research-question
   maturation, and the two can feed each other. The research-question format may adjust
   to reflect this relationship.
2. A plan is an **ordered list of mixed steps**: each step is either a **source to read**
   (paper / preprint / textbook) or an **action** ("summarize X", "compare A vs B",
   "answer this sub-question").
3. Progress is tracked **per step** with a status and an optional note; the plan shows
   overall % complete. Notes tie into the existing Study Log.
4. Cross-referencing means **shared sources/topics across plans** — seeing when the same
   paper, topic, or concept appears in multiple plans, so reading it once advances several.
5. Plans are created via a **tutor `save_plan` tool** (parallel to `queue_source`): the
   tutor generates the plan in chat, then writes structured rows; the user reviews/edits.

## Design (Approach A — first-class tables in the Research epoch)

### Data model

`learning_plans`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `title` | text | Short plan name. |
| `origin_prompt` | text | The question/ask that generated the plan. |
| `origin_session_id` | int FK → chat_sessions, nullable | The tutor chat it came from. |
| `research_question_id` | int FK → research_questions, nullable | Optional link; not required. |
| `status` | text | `active` \| `paused` \| `done`. |
| `created_at` | text (ISO) | |

`plan_steps`
| Column | Type | Notes |
| --- | --- | --- |
| `id` | int PK | |
| `plan_id` | int FK → learning_plans | |
| `order_index` | int | Step order within the plan. |
| `step_type` | text | `read` \| `action`. |
| `paper_id` | int FK → papers, nullable | Set for `read` steps. |
| `action_text` | text, nullable | Set for `action` steps. |
| `status` | text | `todo` \| `in_progress` \| `done` \| `skipped`. |
| `note` | text, nullable | Free text; may reference a Study Log note. |
| `created_at` | text (ISO) | |

Topics/concepts attach to a plan through the **existing unified grouping links**
(a plan is a new groupable entity type, the same way papers and questions are),
which is what powers cross-referencing.

### Creation flow

Tutor generates a plan in chat → calls `save_plan(title, origin_prompt, steps[])`
(parallel to `queue_source`). For each `read` step the tutor supplies a source
(reusing the existing paper-queuing/dedup path so the paper lands in the library);
for each `action` step it supplies `action_text`. The user then reviews and edits
in the Plans panel.

### Progress

Plan % complete is derived from step statuses (`done` / total, with `skipped`
excluded from the denominator). "Where are we" = the first non-terminal step.
Per-step notes feed the Study Log.

### Cross-reference (core v1)

Because `read` steps reference `papers` and plans group under topics, NeuroDb can
surface "this paper/topic appears in N plans." Reading a shared source once advances
every plan that includes it. This is the primary cross-plan value.

### Relationship to research questions

Plan maturation parallels question maturation. The optional `research_question_id`
link lets a question later surface "plans investigating me" and a plan reference its
driving question. This is an **integration point that may reshape the research-question
effort** — flagged as an open question below, per the user's note.

### UI

- A dedicated **Plans panel**: list of plans with status and % complete; per-plan view
  showing ordered steps with status controls and notes.
- A **"save this as a plan"** affordance where the tutor generates a plan.

## Scope

**v1 (this feature):**
- `learning_plans` + `plan_steps` tables and migration.
- `save_plan` tutor tool + structured persistence (reusing paper queuing for read steps).
- Per-step status + notes; plan % complete.
- Cross-reference by shared source/topic.
- Plans panel + tutor save affordance.

**Future (explicitly deferred — YAGNI for v1):**
- Unified multi-plan progress dashboard.
- Semantic "plans related to this one" suggestions.
- Auto-creating a Study Log note / Knowledge Library entry on completing a read step.
- Deep plan↔question↔claim graph linking beyond the single optional FK.

## Approaches Considered

- **A (chosen):** first-class `learning_plans`/`plan_steps` in the Research epoch +
  tutor `save_plan` tool. Delivers all intent answers; co-evolves with research questions.
- **B (rejected):** embed a plan inside each research question. Conflicts with the
  "standalone" requirement; cannot represent pure-learning plans without a question.
- **C (rejected):** persist the tutor plan as a structured study-note blob. Gives save +
  checkbox but no real shared-source/topic cross-referencing across plans — the core ask.

## Placement & Sequencing (deferred)

Per the user: this **must not start before** the in-flight Unified Groupings work
(Phase 4 manual sign-off + Phase 5 legacy-table retirement) and Research Question
Phase 1 are complete. It **may fold into the research-question effort or shift that
effort's focus**, given the maturation parallel and the optional question link.
Final epoch placement and phase ordering to be decided after those efforts land.

## Open Questions

1. Does adding learning plans change the research-question format/lifecycle (shared
   maturation model, "plans investigating this question" view), or do they stay
   independent with only the optional FK?
2. Naming: "Learning Plan" vs "Study Plan" vs "Reading Plan" — chosen working name is
   **Learning Plans** to avoid confusion with the existing Study Log; confirm before build.
3. Do `action` steps need their own typed outcomes (e.g., link to a created claim or
   note), or is a free-text note sufficient for v1? (Currently free-text only.)
4. Should a plan be groupable under topics automatically from its read-step papers'
   topics, or only via explicit user/agent topic assignment?

## Testing Approach (for the eventual plan)

- Unit: `save_plan` persistence (steps, read vs action, dedup of read-step papers);
  per-step status transitions; plan % complete derivation; cross-reference query
  ("plans sharing a paper/topic").
- Integration: tutor chat → `save_plan` → rows persisted → progress update path.
- A manual test plan will be created in `docs/testsPlans/` before implementation begins
  (per CLAUDE.md), with the standard `uv run pytest tests/ -q` prerequisite step.
