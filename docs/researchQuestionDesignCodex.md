# Research Question Workspace Design - Codex

Prepared: 2026-05-31
Author: Codex

## Driving Goal

The design is driven by the user goal in `docs/myOrganQRvw.md`: NeuroDb should let the user consider a speculative research question, ask for adjacent or similar research, find papers, review and load them into the DB, associate them with appropriate topics, and find related studies with usable data so the question can mature into a stronger or weaker thesis based on evidence.

The first implementation target is therefore lifecycle steps 1-3:

1. Capture the original question and its starting context.
2. Categorize it into logical topics and concepts.
3. Connect it to papers, datasets, notes, claims, and open gaps.

Steps 4-6, exploration, maturation, and remembering, should build on that substrate. Socratic agent behavior is valuable, but it should not be the first hard dependency. The system needs durable question, topic, source, and dataset links first.

## Source Review

This plan synthesizes:

- `docs/myOrganQRvw.md`: user goal and preferred research-question lifecycle.
- `docs/archive/OrganizingResearchQuestionsClaude.md`: lifecycle framing and missing Socratic/question workflow.
- `docs/archive/OrganizingResearchQuestionsCodex.md`: current capability review, UI gaps, categorization model, and active-focus finding.
- `docs/archive/OrganizingResearchQuestionsCodexReview.md`: implementation-aware review noting stale claims in earlier design notes and recommending use of existing storage where possible.
- `docs/archive/OrganizingResearchQuestionsReviewClaude.md`: cross-model synthesis and sequencing tradeoffs.
- `docs/researchQuestionDesignClaude.md`: existing phased design.
- Current code in `src/neurodb/schema.py`, `src/neurodb/research_tools.py`, `src/neurodb/db/claim_store.py`, `src/neurodb/api/routes/research.py`, `src/neurodb/api/routes/chat.py`, `src/neurodb/agents/context_orchestrator.py`, `frontend/src/hooks/useChat.ts`, `frontend/src/components/ChatPanel.tsx`, and `frontend/src/pages/ResearchPanel.tsx`.

## Current Implementation Facts

NeuroDb already has several load-bearing pieces:

- `ResearchQuestion` exists with `question`, `topic_context`, `status`, timestamps, and a single nullable `topic_id`.
- `ResearchHypothesis.question_id` already records hypothesis lineage back to a question.
- `ResearchGap` can already anchor to a question, a hypothesis, or both.
- `record_research_question` exists as a Research agent tool.
- GET `/api/research/questions` lists questions, and POST `/api/research/questions/{id}/archive` archives one.
- `get_question_bundle()` retrieves the question, its single topic, topic claims, hypotheses, and gaps.
- `/api/chat/turn` already accepts `active_focus_type` and `active_focus_id`.
- `build_context_bundle()` already retrieves a question bundle when `active_focus_type=research_question`.
- React `ResearchPanel` lists questions and status chips, but it has no create/edit/detail workflow.
- React `useChat()` does not send context mode or active focus in its request body.
- `ChatPanel` exposes context mode preferences, but not topic/question active focus.

The central gap is not whether research questions exist. They exist, but they are not yet a first-class workspace for the user's paper/dataset review loop.

## Key Design Choice

`docs/archive/OrganizingResearchQuestionsCodexReview.md` correctly notes that current code already has `ResearchQuestion.status`, a Research agent recording tool, a Research panel question list, and a single `ResearchQuestion.topic_id`. This plan does not treat question storage as greenfield.

The only deliberate expansion in Phase 1 is many-to-many question-topic and question-concept linking. That is justified by the user's stated goal: questions should be broken into logical topics, and papers pulled for a question should be conditionally associated with the appropriate topic slices. To limit migration risk, the existing `topic_id` remains as a primary-topic compatibility hint until the many-to-many path is proven.

## Design Principles

- Questions are not hypotheses. A question can stay uncertain while accumulating sources, notes, and datasets.
- Topics and concepts are the organizing layer. Questions should be decomposed into multiple logical topics/concepts instead of forced into one `topic_id`.
- The user confirms durable associations. The agent may suggest topic, paper, dataset, or question links, but the user controls what is stored as accepted structure.
- Evidence boundaries remain visible. Linked datasets should carry usefulness and limitations, not just relevance.
- Socratic behavior is a mode of working over an active question, not a replacement for durable linking.
- Each phase must have a manual test plan before implementation if it changes a user-visible workflow, and every manual plan must start with `uv run pytest tests/ -q` with the existing pass criterion from project rules.

## Phase 0 - Contracts and Test Planning

Goal: define the first-phase contracts before code changes.

Deliverables:

- Manual test plan for the research-question workspace in `docs/testsPlans/`.
- API schemas for question creation, update, detail, topic links, concept links, source links, and dataset links.
- Migration plan for preserving existing `research_questions.topic_id` while introducing many-to-many topic links.
- Explicit status vocabulary for questions.

Recommended question statuses:

- `candidate`: proposed by an agent or captured quickly, not yet accepted as active work.
- `open`: accepted and available for exploration.
- `active`: currently being explored or curated.
- `parked`: intentionally paused, still recoverable.
- `promoted`: yielded at least one hypothesis.
- `answered`: enough evidence has resolved the current version of the question.
- `archived`: hidden from normal active workflow but retained for audit history.

Open review question:

- Should `open` and `active` both exist, or should active state be represented only by the chat active-focus selector?

Exit criteria:

- The manual test plan exists.
- The first-phase API request/response objects are named.
- The status vocabulary is accepted or reduced.

## Phase 1 - Capture and Categorize

Lifecycle stages: capture, categorize.

Goal: create and organize questions directly, without requiring the agent to be the only write path.

Schema:

- Add `question_topics` with `question_id`, `topic_id`, `created_at`, and a uniqueness constraint on `(question_id, topic_id)`.
- Add `question_concepts` with `question_id`, `concept_id`, `created_at`, and a uniqueness constraint on `(question_id, concept_id)`.
- Add `origin_session_id` to `research_questions` as nullable provenance.
- Keep `research_questions.topic_id` as a backward-compatible primary-topic hint for now.
- During migration, backfill `question_topics` from existing non-null `topic_id`.

API:

- POST `/api/research/questions`: create a question.
- PATCH `/api/research/questions/{id}`: edit text, status, and topic context.
- GET `/api/research/questions/{id}`: return detail with topics and concepts.
- POST `/api/research/questions/{id}/topics`: link a topic.
- DELETE `/api/research/questions/{id}/topics/{topic_id}`: unlink a topic.
- POST `/api/research/questions/{id}/concepts`: link a concept.
- DELETE `/api/research/questions/{id}/concepts/{concept_id}`: unlink a concept.
- Extend GET `/api/research/questions` with `topic_id` and `concept_id` filters.

UI:

- Add create/edit controls in `ResearchPanel`.
- Show topic and concept badges on question rows.
- Add filters by status, topic, and concept.
- Add a compact question detail state inside the Research panel before adding a full route.

Agent:

- Extend `record_research_question` to allow candidate topic/concept suggestions.
- Add an agent helper for "decompose this question into candidate topics and concepts"; suggestions remain pending until user confirmation.

Tests:

- Unit tests for question-topic and question-concept linking.
- Migration test proving single `topic_id` rows are backfilled into `question_topics`.
- API integration test: create question, link topic/concept, filter by topic.
- Idempotency test: duplicate links do not create duplicate rows.

## Phase 2 - Connect Papers and Datasets

Lifecycle stage: connect.

Goal: satisfy the user's primary workflow: from a question, find adjacent research, review papers, load accepted papers into the DB, and link related datasets that can support or challenge the question.

Schema:

- Add `question_papers` with `question_id`, `paper_id`, `link_status`, `relevance_note`, `created_at`, and uniqueness on `(question_id, paper_id)`.
- Add `question_datasets` with `question_id`, `packet_id`, `link_status`, `relevance_note`, `created_at`, and uniqueness on `(question_id, packet_id)`.
- Add nullable `question_id` to `study_notes` so notes can attach directly to a question.
- Consider `link_status` values: `candidate`, `accepted`, `rejected`, `retracted`.

API:

- POST `/api/research/questions/{id}/papers`: link an approved paper or pending source to a question.
- PATCH `/api/research/questions/{id}/papers/{paper_id}`: update status or relevance note.
- DELETE `/api/research/questions/{id}/papers/{paper_id}`: remove or retract a link.
- POST `/api/research/questions/{id}/datasets`: link a dataset research packet to a question.
- PATCH `/api/research/questions/{id}/datasets/{packet_id}`: update status or relevance note.
- DELETE `/api/research/questions/{id}/datasets/{packet_id}`: remove or retract a link.
- Extend study-log create/update endpoints to accept `question_id`.
- Expand question detail to include linked papers, dataset packets, notes, hypotheses, and gaps.

Agent:

- Add `find_papers_for_question(question_id)` using question text, topics, and concepts as the search query basis.
- Add `nominate_paper_for_question(question_id, paper_id, relevance_note)`.
- Add `find_datasets_for_question(question_id)` using linked topics/concepts and dataset packet metadata.
- Add `nominate_dataset_for_question(question_id, packet_id, relevance_note)`.
- The agent should distinguish "adjacent research worth reading" from "evidence strong enough to support a claim."

UI:

- In question detail, show a paper review queue scoped to the question.
- Let the user accept, reject, or retract a paper-question link.
- Show dataset candidates with source, modality, topic overlap, usefulness state, limitations, and relevance note.
- Let the user create question-anchored notes.

Context bundle:

- Update `get_question_bundle()` to include linked papers, datasets, question notes, topics, concepts, hypotheses, gaps, and relevant claims.
- Update context-budget counts so question bundles are visible in telemetry and the chat context summary.

Tests:

- Unit tests for paper and dataset link CRUD and idempotency.
- Unit tests for `get_question_bundle()` including papers, datasets, notes, topics, and concepts.
- API integration test for the paper review loop: question to paper nomination to accepted link.
- API integration test for dataset nomination and visibility in question detail.
- Manual test for the operator workflow: ask for adjacent papers, approve a paper, see it linked to the question, then ask for related datasets.

## Phase 3 - Active Focus and Socratic Exploration

Lifecycle stage: explore.

Goal: let the user ask the agent to work on a specific question and have the agent explore it Socratically without prematurely converting it into a hypothesis.

UI:

- Add an active-focus selector to `ChatPanel` for neuro-tutor and neuro-research modes.
- Options: no focus, topic, research question.
- Pass `active_focus_type` and `active_focus_id` from `useChat()` to `/api/chat/turn`.
- Display the selected focus and context-summary counts near the chat controls.

Agent:

- Add an inquiry prompt section when active focus is a research question.
- The inquiry section should instruct the agent to:
  - hold the question open,
  - surface adjacent research,
  - identify pros, cons, analogies, limits, and counterexamples,
  - name missing evidence,
  - propose related questions when useful,
  - avoid drafting a hypothesis unless the user asks.

Tutor loop:

- Add `propose_question()` for moments when the Tutor surfaces a tension or gap.
- Proposed questions enter as `candidate` and appear in the Research panel for confirmation.

Related questions:

- Add `find_related_questions()` using shared topic/concept links first.
- Add semantic similarity later in Phase 4; do not block Phase 3 on embeddings.

Tests:

- Frontend test proving active focus is included in `/api/chat/turn`.
- Backend test proving invalid active focus is rejected and valid question focus builds a question bundle.
- Agent prompt test proving inquiry instructions are present only for research-question focus.
- Integration test: active question focus causes the response context summary to include question bundle counts.
- Manual test: in contextual mode, the agent explores pros/cons and does not draft a hypothesis unless requested.

## Phase 4 - Semantic Recall and Question Clustering

Lifecycle stage: remember.

Goal: make questions recoverable across sessions by meaning, not only by exact topic selection.

Semantic index:

- Add a typed question embedding in ChromaDB.
- Either use a dedicated `research_questions` collection or store in `neuro_research` with `type=question` metadata.
- Index on question create/update/status change.
- Metadata should include `question_id`, `status`, topic IDs, concept IDs, and origin session ID.

Hypothesis index:

- Add hypothesis embeddings with `type=hypothesis` metadata or a dedicated collection.
- Index on hypothesis create/update/review completion.
- Include `hypothesis_id`, `question_id`, and status.

Recall:

- On a new neuro-tutor or neuro-research chat, retrieve semantically similar questions and hypotheses.
- Present them as context hints, not as automatically active focus.

Cluster view:

- Add GET `/api/research/questions/clusters`.
- Start with SQL grouping by shared `question_topics`.
- Later add semantic clusters only if topic grouping is insufficient.

Tests:

- Unit tests for idempotent question/hypothesis indexing.
- Integration test: a similar prompt retrieves a saved question as a context hint.
- API test for cluster endpoint grouping by topic.
- Manual test: start a new session on a related concept and confirm the prior question is surfaced.

## Phase 5 - Mature Into Hypotheses

Lifecycle stage: mature.

Goal: promote a question into one or more hypotheses with traceable lineage, without losing the original question.

Schema:

- Add nullable `promoted_hypothesis_id` to `research_questions` for the primary promoted hypothesis.
- Keep `research_hypotheses.question_id` as the many-hypotheses lineage mechanism.

API:

- POST `/api/research/questions/{id}/promote`: draft a hypothesis from the question bundle and set lineage fields.
- PATCH `/api/research/questions/{id}/status`: controlled status transitions.

Agent:

- When an active question is present and the user asks for a hypothesis, pass `question_id` automatically to the draft-hypothesis path.
- Require the response to identify what evidence supports, contradicts, or is missing from the proposed thesis.

UI:

- Add "Promote to hypothesis" in question detail.
- Show all hypotheses linked to the question.
- Show the primary promoted hypothesis when set.
- Show unresolved gaps before promotion so the user sees what remains weak.

Tests:

- Unit test: promotion creates a hypothesis with `question_id`.
- Unit test: `promoted_hypothesis_id` is set only after successful creation.
- Integration test: promoted question shows linked hypothesis and keeps original question visible.
- Manual test: question with linked papers/datasets is promoted and the agent names limitations.

## Recommended Build Order

1. Phase 0: contracts and manual test plan.
2. Phase 1: direct question create/edit plus many-to-many topics and concepts.
3. Phase 2: paper/dataset/note links and full question bundle.
4. Phase 3: active focus in chat and Socratic inquiry behavior.
5. Phase 4: semantic recall and cluster view.
6. Phase 5: promotion workflow and primary hypothesis lineage.

This keeps the user's stated goal in front: first make it possible to collect, organize, and connect real sources and datasets around a question. Then make the agent a better Socratic partner over that durable workspace.

## Review Questions Before Implementation

1. Should topic/concept suggestions be accepted automatically on question creation, or should they always require user confirmation?
2. Should paper and dataset links be allowed while sources are still pending, or only after paper approval and dataset ingestion are complete?
3. Should question notes belong directly to a question, or is topic/concept anchoring enough for the first version?
4. Should "active" be a stored question status, or only a transient chat focus state?
5. Is a compact in-panel question detail sufficient, or should `/research/questions/{id}` become its own route in the first implementation phase?
