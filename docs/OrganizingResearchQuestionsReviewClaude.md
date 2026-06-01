# Organizing Research Questions — Cross-Model Review

_Prepared: 2026-05-31_
_Scope: Comparison of OrganizingResearchQuestionsClaude.md (Claude) and OrganizingResearchQuestionsCodex.md (Codex)_

---

## Executive Summary

Both analyses converge on the same core diagnosis: NeuroDb's backend has substantial infrastructure for organizing research questions, but the `research_questions` object is not yet a first-class citizen in the agent workflow, the UI, or the semantic retrieval layer. The papers agree on the top-priority remediation — wire the existing table, add a CRUD surface, link questions to topics, and index them semantically — and diverge primarily on what to build after that foundation is in place.

The Codex paper is more detailed on UI mechanics and categorization taxonomy. The Claude paper is more specific about agent behavior and question lifecycle framing. Together they complement each other better than either does alone.

---

## 1. Similar Findings

| Finding | Claude | Codex |
|---|---|---|
| `research_questions` table exists but is not wired to any agent, UI, or workflow | Yes — called the "unfilled slot waiting for implementation" | Yes — "still partly agent-driven and partly hidden behind chat tools" |
| Backend foundation (schema, agents, ChromaDB) substantially exceeds what the UI exposes | Yes — notes the schema exists without CRUD surface, agent tool, or UI panel | Yes — "the UI does not yet present them as one workspace" |
| Topics and Concepts are the right organizing primitives for questions | Yes — proposes `question_topics` join mirroring `paper_topics` | Yes — proposes decomposing a question into a topic plus concepts |
| Questions need semantic indexing (ChromaDB), not only DuckDB storage | Yes — proposes adding to `neuro_research` collection | Yes — proposes typed semantic indexes for questions and hypotheses |
| Question→topic linking is missing | Yes — "no question→topic join" | Yes — calls out "assign or change topic" as missing from create/edit |
| Question status lifecycle tracking is missing | Yes — proposes `status` column (open/active/promoted/archived/answered) | Yes — proposes `maturity` axis and intentional status setting from UI |
| Question→hypothesis lineage is missing | Yes — notes no `origin_question_id` FK in `research_hypotheses` | Implicit — calls for dedicated hypothesis workspace linked to question detail view |
| Cross-session recall via ChromaDB is the closest current approximation of "remembering your questions" | Yes | Yes — both cite `agent_context` collection as the existing fallback |

---

## 2. Gaps in Codex Not Identified in Claude

These items appear in the Codex paper but have no counterpart in the Claude paper.

| Gap | Codex Description | Why It Matters |
|---|---|---|
| Active focus selector in the chat UI | The chat backend already accepts `active_focus_type` and `active_focus_id`; the React UI does not expose them. Wiring this requires no new backend work. | Unlocks context-bundle steering without any agent changes — the highest-leverage UI gap |
| Hypothesis semantic indexing | Questions and hypotheses should both have dedicated ChromaDB collections; current code only indexes datasets, study notes, and session summaries | Hypotheses are as much a retrieval target as questions; Claude's semantic index proposal stops at questions |
| Richer categorization taxonomy | Four-axis model: question type (explanatory / mechanistic / comparative / methodological / translational), maturity (raw → hypothesis-ready → parked), evidence posture (model-only → grounded), personal learning state (new → teach-back ready) | Makes routing decisions (tutor vs. extract claims vs. draft hypothesis) automatable rather than user-directed |
| Merge and park operations on questions | Duplicate questions should be mergeable; parked questions should remain recoverable | Practical data hygiene that Claude's CRUD proposal omits |
| Question-to-concept tutoring loop | Structured learning plan: identify prerequisite concepts, mark which have notes, suggest next concept, generate retrieval/teach-back questions, save answers as study notes, revisit confusion across sessions | Deeper than Socratic mode — a durable multi-session learning workflow against a single question |
| Practical "How to Use Today" guide | Step-by-step loop for working in the current system before any new features are built | Claude focuses entirely on the gap; Codex also documents what works now |
| Dataset usefulness state as a signal | Noted that sparse datasets should not be overclaimed when anchored to a question | Prevents overclaiming in question workspaces before evidence is curated |

---

## 3. Similar Next Efforts

Both papers recommend the same first-phase build sequence, in the same order.

| Effort | Claude | Codex |
|---|---|---|
| Add CRUD API for `research_questions` | Priority 1 — `/api/questions` FastAPI route | Build sequence step 1 — Research Question detail API and route |
| Add question UI (list + create/edit form) | Priority 1 — Questions panel in React UI | Build sequence step 2 — create/edit/topic assignment |
| Add `question_topics` join table | Priority 1 — mirrors `paper_topics` pattern | Implicit in concept assignment and topic-bundle retrieval |
| Add semantic index for questions | Priority 1 — add to `neuro_research` ChromaDB collection | Build sequence step 5 — typed semantic indexes |
| Add `status` column to `research_questions` | Priority 2 — (open/active/promoted/archived/answered) | Build sequence step 6 — maturity and status as categorization fields |
| Add question→hypothesis lineage | Priority 2 — `promoted_hypothesis_id` FK | Implied by question detail view showing draft hypotheses |

---

## 4. Contradictions in Next Efforts

These represent genuinely different architectural bets for the work that follows the first-phase foundation.

| Topic | Claude's Position | Codex's Position | Assessment |
|---|---|---|---|
| **Priority of agent behavior vs. UI wiring** | Socratic agent mode (inquiry context) is Priority 3 — build new agent behavior early | Active focus selector (Priority 3 in Codex's sequence) — wire existing architecture to UI before building new agent behavior | Codex's sequencing is more conservative and lower-risk; new agent behavior on top of unwired infrastructure creates hard-to-test surface area |
| **How to unlock open-ended exploration** | New `inquiry` context mode alongside `discovery`, `focused`, `evidence-boundary` — agent holds question open and surfaces analogies/counterexamples | Expose existing `contextual` mode via active focus selector; use `grounded` once evidence accumulates | Codex's approach reuses existing modes; Claude's creates a new code path. If existing modes are insufficient, Claude's path is necessary; if they suffice, it's premature |
| **Agent-initiated question creation** | Tutor agent emits `propose_question()` tool call when a session surfaces a gap; lands with `status=candidate` | Not proposed — question creation is user-initiated from UI or Research agent | Claude's approach adds agent autonomy earlier; Codex keeps the user in control of what enters the question store |
| **Question clustering** | Priority 5 — SQL GROUP BY over `question_topics` in UI, no ML needed | Not proposed as a discrete step — clustering falls out of categorization fields and filters (step 6) | Claude's approach is simpler to ship; Codex's categorization approach is more expressive but requires schema additions first |
| **Tutoring architecture** | Socratic mode stays in the existing agent context orchestrator as a new system-prompt branch | Structured concept-map tutoring loop as a dedicated workflow (step 7) — prerequisite concepts, teach-back questions, confusion revisiting | Codex's tutoring loop is more structured and measurable; Claude's Socratic mode is more flexible but harder to evaluate |

---

## 5. Summary of Findings

### Where the papers agree most strongly

The first three steps are identical across both papers: wire the `research_questions` table to a CRUD API, add a UI panel with create/edit, and add semantic indexing. If one paper is right about nothing else, this first phase is load-bearing for everything downstream. Both papers also agree that the backend is underutilized relative to what the UI and agent tooling expose — the gap is surface area, not schema.

### What Codex adds that is worth adopting

The active focus selector is the most underrated finding in the Codex paper. The backend already accepts `active_focus_type` and `active_focus_id`; wiring the React UI to pass them costs almost nothing and immediately makes every existing context mode more useful for question-centered work. This should be promoted into the first build phase alongside the CRUD API.

The four-axis categorization taxonomy (type, maturity, evidence posture, learning state) is more expressive than Claude's single `status` field and would make routing decisions between Tutor and Research agents automatable. It is, however, a larger schema change — it belongs in a second phase after the basic question workspace is functional.

Hypothesis semantic indexing (not just question indexing) is a clean addition to the Claude paper's proposal that costs little and fills a clear gap.

### Where Claude's framing adds value

The research question lifecycle (capture → categorize → connect → explore → mature → remember) is a cleaner mental model for evaluating completeness than Codex's feature list. It makes it easy to identify which lifecycle stages are served and which are not. The proposed `inquiry` agent mode is the right long-term destination even if it should wait until the UI is wired.

The `propose_question()` agent tool is the only mechanism in either paper for closing the loop between unstructured conversation and the question store. Without it, interesting tensions surfaced during Tutor sessions must be manually transcribed into questions. Whether this belongs in Phase 1 or Phase 2 is a judgment call, but neither paper addresses the full agent→question feedback path as thoroughly.

### Recommended synthesis

A merged build sequence, drawing the best from both papers:

1. Add CRUD API for `research_questions` + Questions panel in React UI
2. Add `question_topics` join table + topic/concept assignment in UI
3. Wire `active_focus_type` / `active_focus_id` into the chat UI (Codex — zero backend cost)
4. Add semantic indexes for research questions and hypotheses in ChromaDB (both papers)
5. Add `status` + `promoted_hypothesis_id` FK to `research_questions` (Claude Priority 2)
6. Add `propose_question()` Tutor agent tool (Claude Priority 4 — closes the session→question loop)
7. Add categorization fields (Codex's four-axis taxonomy) + question clustering view (Claude Priority 5)
8. Add `inquiry` context mode for Socratic exploration (Claude Priority 3 — now has infrastructure under it)
9. Add structured tutoring loop for active questions (Codex step 7)

---

_This document is a living review note. Update it as either source paper evolves._
