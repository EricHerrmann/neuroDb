# Organizing Research Questions with NeuroDb

**Date:** 2026-05-31
**Author:** Codex
**Scope:** Review of current NeuroDb docs and code for using the project to craft, remember, categorize, create, and tutor the user through neuroscience questions. This document does not evaluate the neuroscience merits of any specific question.

---

## Executive Summary

NeuroDb is already close to the shape needed for a personal neuroscience question workspace. It can remember prior conversations, store study notes, curate papers into an approved Knowledge Library, search approved source summaries semantically, group material by topics and concepts, persist research questions and draft hypotheses, track claims and evidence gaps, and run Tutor or Research chat in `general`, `contextual`, or `grounded` modes.

For questions like "are LLM retrieval and memory patterns useful analogies for human memory?", the strongest current workflow is: capture the question in Neuro Research, ask Neuro Tutor to help break it into concepts, queue or approve relevant papers, add study notes as the user's understanding changes, extract or approve source-linked claims, and use research gaps to mark what is not locally supported yet. NeuroDb can then retrieve those objects later through semantic memory and typed bundles.

The main missing piece is not another low-level store. The system needs a first-class "question workspace" user flow: create and edit questions directly in the UI, assign a question to topics and concepts, make that question the active chat focus, capture notes against the question itself, and show a question map of related papers, concepts, claims, notes, hypotheses, gaps, and datasets. Much of the backend foundation exists, but the deliberate question-centered workflow is still partly agent-driven and partly hidden behind chat tools.

## Major Discussion Points

- Current capabilities that already help organize research questions
- How to use NeuroDb today for exploratory neuroscience questions
- What each current surface contributes: Tutor, Research, Knowledge Library, Study Log, ChromaDB, DuckDB, context modes
- Current gaps in the question-centered workflow
- Recommended next build sequence
- Example workflow for the user's LLM/human-memory analogy question, without assessing the science

---

## Current Capabilities

### Durable Question and Hypothesis Storage

The Research epoch already has durable objects for inquiry:

- `research_questions` stores candidate questions with status and topic context.
- `research_hypotheses` stores structured draft hypotheses with mechanism, predictions, confounds, limitations, datasets, and status.
- `hypothesis_reviews` stores premium-model critiques.
- `claims`, `evidence_links`, and `research_gaps` give research work an audit trail instead of keeping everything as free-form chat text.

The relevant implementation is in `src/neurodb/schema.py`, `src/neurodb/research_tools.py`, `src/neurodb/db/claim_store.py`, and `src/neurodb/agents/research_agent.py`.

### Topics, Concepts, Papers, and Study Notes

NeuroDb now has first-class organization primitives:

- `topics` for durable subject areas.
- `concepts` for learnable mechanisms, methods, anatomy terms, or ideas.
- `papers` for pending or approved source records.
- linking tables for paper-topic, paper-concept, topic-concept, dataset-topic, and dataset-paper relationships.
- `study_notes` that the schema can anchor to datasets, topics, concepts, or papers.

The current `topic_store` helper can create topics and concepts, link related objects, search topics, and return a topic bundle with papers, concepts, notes, and dataset packets.

This is a good fit for question exploration because a question can be decomposed into a topic plus concepts, then connected to papers, claims, notes, and gaps as understanding improves.

### Semantic Memory

The project uses ChromaDB in several roles:

- `knowledge_library` stores approved paper/review/textbook summaries for semantic retrieval.
- `agent_context` stores session summaries for cross-session memory.
- `neuro_research` indexes datasets and study notes for semantic search.

This means the project can retrieve prior material based on cues rather than exact keywords. For the user's intended use, this is important: a future prompt about "cue-based retrieval", "semantic memory", or "LLM vector search" can recover related summaries and notes if they were captured clearly.

### Tutor and Research Agents

NeuroDb has two relevant agent roles:

- `NeuroTutorAgent` is optimized for learning. It can search the Knowledge Library, search literature, queue sources for review, retrieve topic bundles, and explain with local context.
- `NeuroResearchAgent` is optimized for structured inquiry. It can record research questions, draft hypotheses, search approved knowledge, cross-reference datasets, extract claims from approved papers, add evidence links, add gaps, and nominate papers.

The separation is useful. The Tutor should help the user understand concepts and remember learning. The Research agent should turn questions into structured, evidence-aware workspaces.

### Context Modes and Evidence Boundaries

The current chat route supports context modes:

- `general`: model-first explanation, local context only when explicitly useful.
- `contextual`: model knowledge focused by NeuroDb context.
- `grounded`: local-source-first, with missing support called out.

For speculative or analogy-forming questions, `contextual` is the best default. It allows broad model reasoning while still organizing around the user's saved topics, notes, and sources. `grounded` becomes useful once the user wants to know what the local corpus actually supports.

### UI Surfaces

The React workbench has useful panels:

- Chat panel with Tutor/Research modes and context mode selector.
- Knowledge Library panel for pending/approved/rejected sources.
- Study Log panel for notes and chat history.
- Research panel for metrics, research questions, claims, gaps, hypotheses, evidence links, and reviews.
- Dataset, registry, suggestions, and SQL panels for supporting work.

This is enough to start using NeuroDb as a learning/research notebook today, but the UI still reflects the implementation history more than the ideal question-centered workflow.

---

## How to Use NeuroDb Today

For a new question, use this practical loop:

1. In `Neuro Research`, ask the agent to record the question and identify the topic context.
2. In `Neuro Tutor`, ask for a concept breakdown and learning path.
3. Ask Tutor or Research to search literature and queue relevant papers or reviews.
4. Approve useful sources in Knowledge Library so they become searchable local context.
5. Add Study Log notes as personal understanding changes.
6. Ask Research to extract candidate claims from approved papers.
7. Approve or reject claims in the Research panel.
8. Ask Research to draft hypotheses only after the question has some approved claims, notes, or papers.
9. Use gaps to preserve unresolved uncertainty instead of forcing premature answers.
10. Revisit the question later in `contextual` mode so prior sessions, approved sources, notes, and topic/question bundles can steer the discussion.

For the user's current example, the question can be stored without judging it:

```text
Question: In what ways are cue-driven retrieval, semantic stores, and pattern-matching behavior in frontier LLM systems useful or misleading analogies for human memory and learning?

Topic candidates:
- memory and retrieval
- semantic representations
- learning systems
- computational neuroscience analogies
- LLM architecture analogies

Concept candidates:
- cue-dependent retrieval
- semantic memory
- associative memory
- vector embeddings
- pattern completion
- working memory
- consolidation
- analogy limits
```

The important thing is to capture the question, the vocabulary around it, and the uncertainty boundaries. The system should not need to decide whether the analogy is correct on day one.

---

## What NeuroDb Has

### Good Fit for the Requested Use

NeuroDb already supports:

- long-lived learning memory through session summaries
- source curation through pending and approved papers
- semantic retrieval through ChromaDB
- durable notes through Study Log
- topic and concept organization in DuckDB
- structured research questions and hypotheses
- claims, evidence links, and gaps for auditability
- context modes that separate general reasoning from local evidence
- dataset usefulness states so sparse datasets are not overclaimed
- model/provider routing and telemetry that make agent behavior inspectable

### Especially Useful Existing Objects

The most relevant current objects for organizing questions are:

| Object | Current Value |
|---|---|
| `ResearchQuestion` | Stores the inquiry itself and workflow status |
| `Topic` | Groups a durable subject area |
| `Concept` | Breaks a question into learnable parts |
| `Paper` | Tracks pending and approved sources |
| `StudyNote` | Preserves the user's own understanding |
| `Claim` | Turns source material into reviewable assertions |
| `EvidenceLink` | Connects hypotheses to specific support |
| `ResearchGap` | Keeps unsupported or missing evidence visible |
| `ChatSession` / `agent_context` | Recovers prior discussion by semantic similarity |

---

## What NeuroDb Needs Next

### 1. First-Class Question Workspace

The top missing feature is a dedicated Research Question detail view. It should show:

- question text and status
- linked topic and concepts
- user notes
- approved papers
- candidate and approved claims
- open and resolved gaps
- draft hypotheses
- evidence links
- relevant dataset packets and their usefulness states
- recent chat sessions related to the question

The backend already has many of the necessary tables, but the UI does not yet present them as one workspace.

### 2. Direct Question Creation and Editing

Today, research questions are primarily created through the Research agent tool path. The Research panel lists and archives questions, but it does not provide a normal create/edit form.

Needed:

- create question from UI
- edit question text and topic context
- set status intentionally
- assign or change topic
- attach concepts
- merge duplicate questions
- park questions without losing them

### 3. Active Focus Selector for Chat

The chat backend accepts `active_focus_type` and `active_focus_id`, and the context orchestrator can build topic or question bundles. The current React chat sends message, agent mode, and history, but does not expose a question/topic active-focus selector.

Needed:

- choose active topic or research question in the UI
- pass it into `/api/chat/turn`
- show active focus near the context mode control
- include context-summary counts for the chosen question

This would make "tutor me on this question" much more reliable.

### 4. Question-Anchored Notes

The schema generalizes `StudyNote` anchors to datasets, topics, concepts, and papers, but the current Study Log API/UI still works mainly through dataset source/source ID. For question work, notes should also attach directly to a research question or at least to its topic/concepts.

Needed:

- note creation for topic, concept, paper, and research question contexts
- UI controls for selecting the anchor type
- semantic indexing that preserves anchor metadata
- question detail view that shows all related notes

The schema may need a direct `question_id` anchor if notes should belong to a specific question rather than only to the question's topic.

### 5. Typed Semantic Indexes for Questions and Hypotheses

The memory-refocus design recommends typed ChromaDB indexes for research questions and hypotheses. Current code has semantic search for approved source summaries, session summaries, datasets, and study notes. Research questions and hypotheses are stored in DuckDB but are not clearly indexed as their own semantic retrieval collections.

Needed:

- index research questions when created or updated
- index hypothesis summaries when drafted or reviewed
- include typed metadata so retrieval can distinguish notes, questions, hypotheses, claims, and papers
- expose similarity search in the Research panel

### 6. Better Question Categorization

The current structures can support categories indirectly through topics, concepts, statuses, and text fields. A stronger question system should add explicit categorization:

- question type: explanatory, mechanistic, comparative, methodological, translational, dataset-seeking, hypothesis-generating
- maturity: raw, clarified, sourced, evidence-mapped, hypothesis-ready, parked
- evidence posture: model-only, has notes, has approved sources, has claims, has local datasets, grounded
- personal learning state: new, familiar, confusing, needs review, teach-back ready

These categories would help the system decide whether to tutor, search, extract claims, draft hypotheses, or simply preserve the question.

### 7. Question-to-Concept Tutoring Loop

The Tutor can already retrieve topic bundles and teach with context, but the workflow should explicitly turn a research question into a learning plan:

- identify prerequisite concepts
- mark which concepts the user has notes for
- suggest a next concept
- ask retrieval or teach-back questions
- save the user's answers as study notes
- revisit open confusion in later sessions

This would make NeuroDb a tutor for the question, not just an answer generator.

---

## Recommended Build Sequence

1. Add a Research Question detail API and UI route.
2. Add create/edit/topic assignment for research questions.
3. Add an active focus selector to Chat and pass it to `/api/chat/turn`.
4. Extend Study Log to create notes anchored to topics, concepts, papers, and questions.
5. Add semantic indexing for research questions and hypotheses.
6. Add categorization fields and filters after the basic question workspace is in use.
7. Add tutor workflows that generate concept maps, retrieval questions, and teach-back prompts for an active question.

This sequence uses existing architecture instead of replacing it. The project already has the storage, agent, and retrieval foundation; the next work should make the question object the center of the user experience.

---

## Bottom Line

NeuroDb can already help organize exploratory neuroscience questions if the user is willing to work through the Tutor, Research, Knowledge Library, Study Log, and Research panels together. It can remember the conversation, categorize material through topics and concepts, retrieve related context semantically, curate sources, track claims, and preserve gaps.

The next major product step is to make a research question feel like a durable workspace. Once a question can be selected as active focus, linked to concepts and papers, annotated directly, semantically retrieved, and used as the anchor for tutoring, NeuroDb will fit the user's intended workflow much more naturally.
