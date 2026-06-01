# Review: Claude vs Codex Research Question Organization Notes

**Date:** 2026-05-31
**Scope:** Compare `docs/OrganizingResearchQuestionsClaude.md` with `docs/OrganizingResearchQuestionsCodex.md` and summarize overlapping findings, gaps Claude identified that Codex did not emphasize, similar next efforts, and contradictions in proposed next efforts.

---

## Executive Summary

The two documents agree on the main product conclusion: NeuroDb already has a strong learning/research substrate, but it needs a first-class research-question workspace so speculative questions can be captured, categorized, revisited, tutored, and matured into evidence-aware hypotheses.

The Codex document is more aligned with the current implementation. It correctly treats research questions, question status, Research panel listing, and agent question-recording as existing but incomplete capabilities. Claude's document is useful for framing the question lifecycle and proposes several valuable additions, but some of its gap claims are stale or incorrect against the current codebase.

The strongest synthesis is:

- Build a Research Question detail workspace.
- Add direct create/edit/topic assignment in the UI.
- Add explicit active-focus selection for chat.
- Add question-anchored or question-associated notes.
- Add semantic indexing for questions and hypotheses.
- Add a Socratic/inquiry workflow, but implement it as an agent mode or task behavior rather than a fourth context mode unless there is a clear contract change.

---

## Comparison Table

| Category | Finding / Gap / Effort | Claude Position | Codex Position | Review Finding |
|---|---|---|---|---|
| Similar finding | NeuroDb is already a capable local learning/research platform | Emphasizes dataset connectors, semantic retrieval, hypotheses, critique, and cross-session memory | Emphasizes durable questions/hypotheses, source curation, semantic memory, topics/concepts, claims/gaps, and context modes | Agreement. Both see the platform as foundation-ready rather than greenfield. |
| Similar finding | First-class research-question workflow is missing | Says NeuroDb lacks a first-class home for speculative exploratory questions | Says the main missing piece is a first-class question workspace user flow | Agreement. This is the central shared conclusion. |
| Similar finding | Topics and concepts are the right categorization substrate | Treats topics/concepts as lightweight taxonomy, but says direct question links are missing | Treats topics/concepts as existing organization primitives and recommends assignment from question workflow | Agreement on direction. Codex is more precise that `ResearchQuestion.topic_id` exists, while broader many-to-many concept linking is still missing. |
| Similar finding | Semantic question retrieval is missing | Says questions are not semantically indexed | Says research questions and hypotheses are stored in DuckDB but not clearly indexed as their own semantic retrieval collections | Agreement. This should be a high-value next step. |
| Similar finding | Chat needs deliberate question focus | Says no "question mode" exists | Says backend accepts active focus but React chat lacks an active topic/question selector | Agreement on user need. Codex identifies a concrete partially implemented backend path. |
| Similar finding | A question should mature into hypotheses without losing provenance | Recommends promoted hypothesis lineage | Recommends question workspace with draft hypotheses and evidence links | Agreement on outcome. Claude is more explicit about lineage fields. |
| Similar finding | Existing agents are not enough as-is | Recommends Socratic exploration mode | Recommends a question-to-concept tutoring loop and active question workflow | Agreement. Both documents call for a more deliberate tutoring/exploration loop around questions. |
| Gap Claude identified, not emphasized by Codex | Research-question lifecycle model | Defines capture, categorize, connect, explore, mature, remember | Codex gives a practical workflow but not a lifecycle model | Add this framing to future design work. It is a useful product rubric. |
| Gap Claude identified, not emphasized by Codex | Socratic exploration behavior | Calls for an agent mode that holds speculative questions open, probes analogies, and surfaces counterexamples | Codex calls for tutor workflows but does not name Socratic mode | Valuable gap. Use this as behavior design for question tutoring. |
| Gap Claude identified, not emphasized by Codex | Tutor-driven question seeding | Proposes a `propose_question()` tool similar to `queue_source()` | Codex focuses on user-created questions and question workspace | Strong addition. This would let learning sessions generate candidate questions without forcing immediate hypothesis work. |
| Gap Claude identified, not emphasized by Codex | Question clustering view | Suggests grouping questions by shared topics/concepts | Codex recommends categorization fields and filters, but not a clustering view | Useful UI addition after direct question-topic/concept linking exists. |
| Gap Claude identified, not emphasized by Codex | Session provenance for original question capture | Says saved questions should retain timestamp and session reference | Codex mentions create/edit and recent chat sessions but not explicit origin session linkage | Add `origin_session_id` or equivalent when designing the question workspace. |
| Gap Claude identified, not emphasized by Codex | Question-to-hypothesis lineage field | Suggests `promoted_hypothesis_id` | Codex says question workspace should show draft hypotheses but does not specify lineage fields | Good schema/API detail. Prefer a flexible relationship if multiple hypotheses can originate from one question. |
| Similar next effort | Add question UI | Recommends Questions panel with list and add form | Recommends Research Question detail API and UI route, plus create/edit | Agreement. Codex version is broader because the detail workspace matters more than a flat panel. |
| Similar next effort | Add question semantic index | Recommends indexing questions in `neuro_research` ChromaDB | Recommends typed semantic indexes for research questions and hypotheses | Agreement. Codex expands the scope to hypotheses too. |
| Similar next effort | Link questions to topics/concepts | Recommends `question_topics` join table | Recommends assign/change topic and attach concepts | Agreement with nuance. Current schema has `ResearchQuestion.topic_id`, so a join table is only needed if questions need multiple topics. Concept links are still a real gap. |
| Similar next effort | Add question status/lifecycle | Recommends open/active/promoted/archived/answered | Recommends explicit categorization/maturity states and status control | Agreement. Current `ResearchQuestion.status` exists, so this is a vocabulary/API/UI workflow issue more than a missing-column issue. |
| Similar next effort | Add exploratory agent behavior | Recommends Socratic `inquiry` mode | Recommends question-to-concept tutoring loop | Agreement on need, different implementation framing. |
| Contradiction in next efforts | New context mode naming and location | Proposes a new context mode alongside `discovery`, `focused`, and `evidence-boundary` called `inquiry` | Codex describes existing context modes as `general`, `contextual`, and `grounded`, and recommends active focus plus tutoring workflows | Claude conflicts with current implementation terminology. If added, `inquiry` should be an agent/task behavior or a carefully defined fourth context mode alongside current names, not alongside obsolete mode names. |
| Contradiction in next efforts | Wire `research_questions` table as if it is unused | Says table exists but has no CRUD surface, no agent tool, no UI panel, and no status tracking | Codex says Research agent can record questions, Research panel lists questions, and questions have status/archive flow | Claude is stale. Needed work is direct create/edit/detail/topic assignment and richer lifecycle, not initial wiring from zero. |
| Contradiction in next efforts | Add status column to `research_questions` | Recommends adding a status column | Codex treats question status as existing and needing intentional UI/workflow use | Claude proposal is factually outdated. `ResearchQuestion.status` already exists. |
| Contradiction in next efforts | Add `question_topics` before using existing `topic_id` | Recommends a join table as part of initial wiring | Codex recommends topic assignment generally | Potential conflict. Start with existing `topic_id` for one primary topic, then add many-to-many only if real questions need multiple durable topic links. |
| Contradiction in next efforts | Add `promoted_hypothesis_id` to question | Recommends a single FK from question to promoted hypothesis | Codex describes a workspace where a question can show draft hypotheses | A single promoted FK may be too narrow because one question can yield multiple hypotheses. Prefer `ResearchHypothesis.question_id` as existing lineage plus a status or relationship view; add a promoted pointer only if UI needs one selected result. |

---

## Gaps Claude Identified That Codex Should Incorporate

Claude's strongest additions are product-shape details rather than storage basics:

- Use the lifecycle model: capture, categorize, connect, explore, mature, remember.
- Add Socratic exploration behavior so an agent can keep a question open and probe it from multiple angles instead of rushing to a hypothesis.
- Add Tutor-driven question seeding through a pending `propose_question()` tool.
- Preserve original-question provenance with a session reference.
- Add question clustering by topic/concept once question links exist.
- Make question-to-hypothesis lineage explicit in the UI and API.

These additions are compatible with the Codex direction and should be folded into a future implementation plan.

## Stale or Incorrect Claims in Claude's Document

Claude's review appears to understate current implementation in several places:

- `research_questions` is not schema-only. The Research agent has a `record_research_question` tool, and the Research panel lists questions.
- `ResearchQuestion.status` already exists.
- The UI has a Research Questions section, though it lacks direct create/edit/detail workflow.
- The chat/context implementation uses `general`, `contextual`, and `grounded`, not `discovery`, `focused`, and `evidence-boundary`.
- `ResearchHypothesis.question_id` already provides a basic question-to-hypothesis link, although the UI could make lineage clearer.

These are not fatal to Claude's design direction, but they should be corrected before using it as an implementation plan.

## Recommended Synthesis

The best next plan should combine Codex's implementation-aware sequencing with Claude's lifecycle framing:

1. Build a Research Question detail workspace rather than only a flat Questions panel.
2. Add direct question create/edit controls and topic assignment using existing `ResearchQuestion.status` and `ResearchQuestion.topic_id`.
3. Add active topic/question focus selection to Chat and pass it through the existing `/api/chat/turn` request fields.
4. Extend note capture so notes can attach to question workspaces, directly or through topic/concept anchors.
5. Add semantic indexing for questions and hypotheses with typed metadata.
6. Add Socratic inquiry behavior as a mode of Tutor/Research interaction.
7. Add candidate question seeding from Tutor sessions.
8. Add many-to-many question-topic/concept links and clustering only after the simple primary-topic workflow proves insufficient.

This avoids rebuilding existing question storage while still moving NeuroDb toward the user's intended workflow: a durable, searchable, tutored workspace for exploratory neuroscience questions.
