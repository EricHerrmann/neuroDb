# Research Question Workspace — Phased Design Plan

_Prepared: 2026-05-31_
_Author: Claude_
_Driving goal: The user wants to consider a question, ask for adjacent research, find and load papers into the DB associated with relevant topics, find related datasets whose data can strengthen or contradict the thesis, then come back later and pick up where they left off — with an agent that explores rather than concludes._

---

## Design Anchors

**Lifecycle model (from user's review):** Capture → Categorize → Connect → Explore → Mature → Remember

**User's explicit framing:**
> "I want to be able to consider a question, ask for existing research that are adjacent or similar to the topic, find papers, review them, then load them into the DB and associate them with the appropriate topics… questions should be broken into logical topics… as the question matures, the data can be used to strengthen or conversely contradict the thesis."
> "I think this naturally fits with the Socratic Agent Mode."

**Design decisions confirmed before this plan:**
- Questions support multiple topics from Phase 1 (agent suggests topics from question text; user confirms)
- Inquiry/Socratic mode auto-activates when a research question is set as active focus — no new context-mode picker needed

---

## Current State (verified against code, 2026-05-31)

### What exists and works
| Capability | Location |
|---|---|
| `research_questions` table (`id`, `question`, `topic_context`, `status`, `created_at`, `updated_at`, `topic_id` single FK) | `schema.py:297` |
| `research_hypotheses.question_id` FK (nullable) | `schema.py:315` |
| `record_research_question` agent tool | `research_agent.py:130` |
| GET `/api/research/questions` (list + status filter) | `routes/research.py:67` |
| POST `/api/research/questions/{id}/archive` | `routes/research.py:282` |
| `get_question_bundle()` — pulls hypotheses + gaps for a question | `db/claim_store.py:251` |
| `active_focus_type="research_question"` + `active_focus_id` wired in context orchestrator | `context_orchestrator.py:117` |
| ResearchPanel shows question list with status chips and archive action | `ResearchPanel.tsx` |
| Context modes: `general`, `contextual`, `grounded` | `research_agent.py:724` |

### What is missing
- No direct question creation from UI — only via Research agent tool
- No question detail view (workspace showing papers, datasets, notes, gaps, hypotheses in one place)
- No `question_topics` join table — single `topic_id` FK only
- No `question_concepts` join table
- No active focus selector in ChatPanel — backend accepts it, UI never sends it
- No agent-suggested topic/concept extraction from question text
- No paper → question direct links (papers link to topics, not questions)
- No dataset → question direct links
- No study notes anchored to a research question
- No semantic index for questions in ChromaDB
- No inquiry/Socratic agent behavior
- No `propose_question()` Tutor agent tool

---

## Phase 1 — Capture & Categorize

**Lifecycle stages served:** Capture (1), Categorize (2)
**Goal:** A question can be created directly in the UI, tagged to multiple agent-suggested topics and concepts, and is findable by topic from any panel or chat.

### Schema changes

**`question_topics` join table** (many-to-many, mirrors `paper_topics` pattern)
```
question_topics(id, question_id FK→research_questions, topic_id FK→topics, created_at)
UniqueConstraint(question_id, topic_id)
```

**`question_concepts` join table**
```
question_concepts(id, question_id FK→research_questions, concept_id FK→concepts, created_at)
UniqueConstraint(question_id, concept_id)
```

**Migration note:** The existing `topic_id` FK on `research_questions` becomes the "primary topic" hint — keep it nullable and populate `question_topics` from any existing non-null `topic_id` rows during migration. Do not remove `topic_id` in this phase; leave it as backward-compatible for `get_question_bundle()` until Phase 2 updates that function.

**`research_questions` new column:** `origin_session_id` (nullable, stores the `ChatSession.id` that first surfaced the question — provenance)

### API changes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/research/questions` | Create question with `question`, optional `topic_context`, optional `origin_session_id` |
| PUT | `/api/research/questions/{id}` | Edit question text and topic_context |
| GET | `/api/research/questions/{id}` | Single question detail (question + topics + concepts + status) |
| POST | `/api/research/questions/{id}/topics` | Add a topic link |
| DELETE | `/api/research/questions/{id}/topics/{topic_id}` | Remove a topic link |
| POST | `/api/research/questions/{id}/concepts` | Add a concept link |
| DELETE | `/api/research/questions/{id}/concepts/{concept_id}` | Remove a concept link |
| GET | `/api/research/questions?topic_id={id}` | Filter questions by topic (extend existing route) |

### Agent changes

**Research agent — `extract_question_topics` tool:**
When a question is recorded or created, the agent runs a lightweight analysis pass and returns candidate topics and concepts the user can confirm or reject in the UI. This is not a separate agent call — it is an additional tool the agent can call within the same `record_research_question` turn.

Tool returns:
```json
{
  "question_id": 42,
  "suggested_topics": ["memory and retrieval", "LLM architecture analogies"],
  "suggested_concepts": ["semantic memory", "vector embeddings", "pattern completion"]
}
```
These land as pending suggestions in the ResearchPanel question detail view. The user confirms (creates the join rows) or dismisses.

### UI changes

**ResearchPanel — question creation form:**
- Text area for question text
- Submit → calls POST `/api/research/questions`, triggers agent topic extraction in background
- Pending suggested topics/concepts appear as confirm/dismiss chips below the question

**ResearchPanel — question list improvements:**
- Show topic badges on each question row
- Filter bar: filter by topic or status
- "Find questions by topic" is now viable (GET questions?topic_id=X)

**No question detail view yet** — that is Phase 2.

### Test plan (before implementation)
- Unit: `question_topics` and `question_concepts` CRUD
- Unit: migration populates `question_topics` from existing `topic_id` FK rows
- Unit: `extract_question_topics` returns plausible suggestions for a sample question
- Integration: create question via API → confirm suggested topic → question appears filtered by that topic
- Idempotency: adding the same topic twice does not create a duplicate row

---

## Phase 2 — Connect

**Lifecycle stages served:** Connect (3)
**Goal:** A question is the active focus of a chat session, which causes the agent to surface adjacent papers and datasets, propose associations, and let the user build an evidence base directly against the question.

### Schema changes

**`question_papers` join table** (question → approved paper link)
```
question_papers(id, question_id FK→research_questions, paper_id FK→papers, created_at)
UniqueConstraint(question_id, paper_id)
```

**`question_datasets` join table** (question → dataset packet link)
```
question_datasets(id, question_id FK→research_questions, packet_id FK→dataset_research_packets, created_at, relevance_note TEXT nullable)
UniqueConstraint(question_id, packet_id)
```

**`study_notes` schema extension:** Add `question_id` (nullable FK→research_questions) as an additional anchor alongside the existing `dataset_id`, `topic_id`, `concept_id`, `paper_id` anchors.

**`get_question_bundle()` update:** Extend to include linked papers (via `question_papers`), linked datasets (via `question_datasets`), linked concepts (via `question_concepts`), and question-anchored study notes. Update the context orchestrator's question bundle budget accordingly.

### API changes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/research/questions/{id}/papers` | Link an approved paper to a question |
| DELETE | `/api/research/questions/{id}/papers/{paper_id}` | Remove paper link |
| POST | `/api/research/questions/{id}/datasets` | Link a dataset packet to a question |
| DELETE | `/api/research/questions/{id}/datasets/{packet_id}` | Remove dataset link |
| POST | `/api/study-log/notes` extension | Accept `question_id` anchor (extend existing endpoint) |

### Agent changes

**Research agent — when `active_focus_type=research_question`:**
- Agent can call `find_papers_for_question(question_id)` — searches Knowledge Library and literature by the question's topics/concepts, returns candidate papers with relevance notes
- Agent can call `link_paper_to_question(question_id, paper_id)` after user approves a paper in Knowledge Library
- Agent can call `link_dataset_to_question(question_id, packet_id)` — surfaces datasets tagged to the question's topics and flags usefulness state

These calls are conditional on an active question being set — the agent proposes, the user confirms in the ResearchPanel question detail view.

### UI changes

**ChatPanel — active focus selector:**
- Dropdown: "No focus" (default) | topics list | questions list
- Selecting a question passes `active_focus_type=research_question` + `active_focus_id` on every `/api/chat/turn` call
- Shows a small "Q: [question short title]" badge near the context mode selector when active

**ResearchPanel — question detail view** (new route: `/research/questions/{id}`):
Columns:
1. Question text + status + topics + concepts (edit/add in place)
2. Papers linked to this question (approve paper → auto-suggest question link when a question is active)
3. Datasets linked to this question (usefulness state visible)
4. Study notes anchored to this question
5. Hypotheses derived from this question (existing `question_id` FK)
6. Research gaps open for this question (existing `question_id` FK)

### Test plan (before implementation)
- Unit: `question_papers`, `question_datasets` join CRUD; idempotency
- Unit: `get_question_bundle()` includes papers, datasets, notes in output
- Unit: context orchestrator budget includes question papers and datasets
- Integration: set active focus to question → agent surfaces related papers → user links paper → detail view shows link
- Integration: study note with `question_id` anchor appears in question detail view

---

## Phase 3 — Explore (Socratic Mode)

**Lifecycle stages served:** Explore (4)
**Goal:** When a question is active focus, the agent shifts to inquiry behavior — it holds the question open, probes analogies and counterexamples, surfaces related questions, and does not push toward a hypothesis unless the user asks.

### Agent changes

**Inquiry behavior in context orchestrator:**
- When `active_focus_type=research_question` is present in the context bundle, inject a new system prompt section:
```
Inquiry stance: A research question is active. Your role is exploration, not conclusion.
- Hold the question open deliberately. Do not drive toward a hypothesis.
- When a claim could be argued either way, present both framings.
- Probe analogies: what does this question resemble? where does the analogy break?
- Surface counterexamples: what would falsify the premise?
- If a related question emerges, name it explicitly so the user can consider saving it.
- If the evidence base is thin, say so clearly instead of speculating.
```
- This section is appended to the existing context mode rules. It works with all three context modes — `contextual` is the recommended default for exploration.

**Tutor agent — `propose_question()` tool:**
- When the Tutor surfaces an interesting tension or gap during a session, it can emit:
```json
{"tool": "propose_question", "question": "...", "topic_context": "...", "origin_session_id": "..."}
```
- Proposed question lands in `research_questions` with `status="candidate"`, does not trigger topic extraction automatically
- ResearchPanel shows candidate questions in a "Pending questions" section with confirm/dismiss
- Same pattern as the existing `queue_source()` → `import_queue` flow for papers

**Research agent — `find_related_questions()` tool:**
- Searches `research_questions` by shared topics and concepts
- Returns questions with overlapping topic/concept tags
- Used during inquiry sessions when the agent identifies conceptual overlap

### UI changes

**ResearchPanel — candidate question queue:**
- "Pending Questions" section (status=candidate) with confirm (→ open) / dismiss (→ archived) actions
- Shows `origin_session_id` link to the session that generated it

### Semantic index: questions

Add research questions to a new ChromaDB collection `research_questions` (or extend `neuro_research` with `type=question` metadata):
- Index on create and on status change
- Metadata: `question_id`, `status`, `topic_ids` (list), `concept_ids` (list)
- Used by: `find_related_questions()`, context retrieval when no active focus is set

### Test plan (before implementation)
- Unit: inquiry system prompt section is injected when active_focus is a research_question
- Unit: inquiry section is absent when active_focus is a topic or when no focus is set
- Unit: `propose_question()` creates a `status=candidate` row, does not trigger topic extraction
- Unit: `find_related_questions()` returns questions sharing at least one topic or concept
- Integration: Tutor session proposes a question → question appears in Pending section → user confirms → question is searchable
- Manual: agent holds question open in contextual mode; does not spontaneously draft a hypothesis when active_focus is a question

---

## Phase 4 — Mature & Remember

**Lifecycle stages served:** Mature (5), Remember (6)
**Goal:** Questions progress explicitly to hypotheses (with traceable lineage), are retrievable across sessions by semantic similarity, and cluster visibly by shared topic/concept.

### Schema changes

**`research_questions` new column:** `promoted_hypothesis_id` (nullable FK→research_hypotheses) — set when a question is explicitly promoted in the UI. A question can yield multiple hypotheses (via `research_hypotheses.question_id`); this FK points to the one the user designated as primary.

**Status vocabulary extension:** Add `promoted` to the existing status set (`open`, `active`, `candidate`, `archived`). When `promote_to_hypothesis()` is called, status transitions to `promoted` and `promoted_hypothesis_id` is set.

### API changes

| Method | Route | Purpose |
|---|---|---|
| POST | `/api/research/questions/{id}/promote` | Draft a hypothesis from the question, set status=promoted, set promoted_hypothesis_id |
| GET | `/api/research/questions/cluster` | Return questions grouped by shared topic (SQL GROUP BY over `question_topics`; no ML needed) |

### Agent changes

**Research agent — hypothesis lineage:**
- `draft_hypothesis()` already accepts `question_id`; make this the required path when a research question is active focus (the active question's ID is passed automatically)
- After drafting, remind user they can promote the question from the detail view

### Semantic index: hypotheses

Extend ChromaDB indexing (or `neuro_research` collection with `type=hypothesis` metadata):
- Index hypothesis summary (`title` + `mechanism`) on create and on review completion
- Metadata: `hypothesis_id`, `question_id`, `status`
- Used by: cross-session retrieval, `find_related_questions()` can also surface related hypotheses

### UI changes

**ResearchPanel — question detail view additions:**
- "Promote to Hypothesis" button: calls POST `/api/research/questions/{id}/promote`, shows resulting hypothesis in the hypotheses section
- Question status badge shows `promoted` and links to the primary hypothesis

**ResearchPanel — question cluster view:**
- Grouped list: each topic becomes a header, questions tagged to that topic appear under it
- Questions shared across multiple topics appear once per topic group
- No ML — pure SQL GROUP BY over `question_topics`

**Cross-session recall:**
- When a new chat session starts, context orchestrator checks ChromaDB for questions semantically similar to the first user message
- Surfaced question IDs are mentioned in the system context: "You have a related question: [text]. Consider it active or ask me to set it."

### Test plan (before implementation)
- Unit: `promote()` sets status=promoted, creates hypothesis with question_id, sets promoted_hypothesis_id
- Unit: hypothesis semantic index is updated on draft and on review completion
- Unit: cluster endpoint returns questions grouped by topic, no duplicates within a group
- Integration: promote question → hypothesis appears in hypotheses panel with question lineage link
- Integration: start new session on related topic → related question surfaces in context hint
- Idempotency: re-indexing a question or hypothesis does not create duplicate ChromaDB documents

---

## Phased Summary

| Phase | Lifecycle stage | Key deliverable | Schema additions |
|---|---|---|---|
| 1 — Capture & Categorize | 1, 2 | Direct question creation + agent-suggested multi-topic tagging | `question_topics`, `question_concepts`, `origin_session_id` |
| 2 — Connect | 3 | Active focus selector in chat + question detail workspace + paper/dataset/note linking | `question_papers`, `question_datasets`, `question_id` on `study_notes` |
| 3 — Explore | 4 | Inquiry/Socratic agent behavior + candidate question seeding + question semantic index | `research_questions` ChromaDB collection |
| 4 — Mature & Remember | 5, 6 | Promote-to-hypothesis + hypothesis semantic index + question cluster view | `promoted_hypothesis_id` on `research_questions` |

Each phase is shippable independently. Phase 2 depends on Phase 1 (needs `question_topics` and question detail view). Phases 3 and 4 are independent of each other and can overlap.

---

## Open Design Questions (deferred, not blocking any phase)

1. **Four-axis categorization taxonomy** (type, maturity, evidence posture, learning state): The user found this unclear. Once Phase 1's topic/concept tagging is in use, revisit whether explicit category fields add value beyond what topic and status already provide. Do not add schema fields until the need is observed in practice.

2. **Many-to-many question→paper vs. topic-mediated linking**: Phase 2 adds `question_papers` for direct links. Whether papers should also inherit question association via shared topics (indirect path) is a retrieval question to answer once the detail view exists and the user can observe what surfaces.

3. **Inquiry as explicit context mode**: The current design auto-activates inquiry behavior via active focus. If the user later wants to enter inquiry mode on a topic (not a question), or without an active focus, a fourth context mode selector becomes necessary. Revisit after Phase 3 is in use.

---

_Phase 1 implementation started 2026-06-01. Manual test plan: `docs/testsPlans/manualTestPlan_research_question_phase1.md`. Implementation plan: `docs/superpowers/plans/2026-06-01-research-question-phase1.md`._

_Update this document when any phase begins implementation. Each phase should produce its manual test plan in `docs/testsPlans/` before implementation starts, per CLAUDE.md._
