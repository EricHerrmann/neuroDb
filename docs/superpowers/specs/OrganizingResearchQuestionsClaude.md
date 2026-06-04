# Organizing Research Questions with NeuroDb

_Prepared: 2026-05-31_

---

## Executive Summary

NeuroDb is already a capable local research platform — it ingests public neuroscience datasets, indexes papers semantically, formulates and critiques hypotheses, and maintains cross-session memory through grounded agent conversations. What it does **not yet have** is a first-class home for the kinds of speculative, exploratory research questions a curious researcher generates before they are ready to become hypotheses.

This document maps the current platform capabilities against the lifecycle of a research question — from "something I noticed and want to think about" through categorized, evidence-linked, tutored exploration — and identifies the specific gaps that would make NeuroDb a genuine research-question companion, not just a dataset browser and hypothesis store.

The illustrative question used throughout: *Do frontier LLMs and biological neural systems converge on similar architectures for storing and retrieving semantic information — pattern-matching on received cues, context-gated retrieval, and distributed associative storage — and if so, what does that convergence reveal about the computational demands of general intelligence?*

That question has a home here. It just needs the scaffolding to grow.

---

## Table of Contents

1. [What NeuroDb Currently Offers](#1-what-neurodb-currently-offers)
2. [The Research Question Lifecycle](#2-the-research-question-lifecycle)
3. [How Current Capabilities Map to That Lifecycle](#3-how-current-capabilities-map-to-that-lifecycle)
4. [Gap Analysis: What Is Missing](#4-gap-analysis-what-is-missing)
5. [Illustrative Use Case: The LLM–Brain Convergence Question](#5-illustrative-use-case-the-llmbrain-convergence-question)
6. [Recommended Next Capabilities](#6-recommended-next-capabilities)

---

## 1. What NeuroDb Currently Offers

### Data Layer

- **Four live dataset connectors**: OpenNeuro (fMRI/EEG), DANDI (neurophysiology recordings), Allen Brain Institute, NeuroVault (statistical maps). Each ingested dataset carries provenance, brain-region tags, modality, participant metadata, and a research packet describing supported/unsupported analytical workflows.
- **57 structured tables** in DuckDB, organized by epoch: DB (datasets), Tutor (papers, topics, concepts, study notes), Research (hypotheses, evidence, claims, gaps), Agent (session index, model call log, telemetry).

### Semantic Retrieval

Three independent ChromaDB collections:
- **neuro_research** — datasets and study notes (searched by topic/concept similarity)
- **knowledge_library** — approved papers and learning sources
- **agent_context** — cross-session conversation summaries (cosine-distance retrieval enables sessions to build on prior work)

### Research Structure

- **Topics** and **Concepts** provide a lightweight taxonomy for organizing what is being studied.
- **Papers** (candidate → approved lifecycle) link to topics and concepts, accumulating a curated reading list per subject area.
- **Hypotheses** follow a structured schema: mechanism, predictions, confounds, limitations, and evidence links (claims, papers, datasets, study notes).
- **Hypothesis review**: a premium model critique loop that flags unsupported claims, missing confounds, and suggested revisions.
- **Research gaps**: formal gap records anchored to a question or hypothesis, tracking what evidence is still missing.

### Agent Layer

- **NeuroTutorAgent**: guides learning through papers and datasets; supports queued imports and study note tagging.
- **NeuroResearchAgent**: formulates hypotheses, searches datasets, links evidence, and initiates peer-review critique.
- **Multi-provider, tiered routing**: economy/standard/premium tiers across Anthropic, OpenAI, Gemini, Groq, and DeepSeek — each model call is logged with cost and context telemetry.

### Cross-Session Memory

Session summaries are embedded and retrieved semantically, so a new session on a related topic surfaces what was learned or debated in prior sessions. This is the closest the system currently comes to "remembering your questions."

---

## 2. The Research Question Lifecycle

A research question is not a hypothesis. It starts as a hunch, an analogy, a provocation. It needs to be:

1. **Captured** — recorded before it evaporates, attached to a date and a context
2. **Categorized** — tagged to one or more topics, domains, or conceptual clusters
3. **Connected** — linked to papers, datasets, prior notes, or other questions that bear on it
4. **Explored** — discussed with an agent that can surface relevant evidence, propose framings, push back with counterexamples
5. **Matured** — either promoted to a testable hypothesis, archived as answered, or flagged as out-of-scope for the current evidence base
6. **Remembered** — retrievable across sessions so it can be revisited as new evidence accumulates

NeuroDb supports steps 3–6 well. It has significant gaps at steps 1–2.

---

## 3. How Current Capabilities Map to That Lifecycle

| Step | Current Capability | Where It Lives |
|---|---|---|
| Capture | Partial — `research_questions` table exists (schema only) | `research_questions` (DB epoch) |
| Categorize | Topics and Concepts provide taxonomy; no direct question→topic link | `topics`, `concepts`, join tables |
| Connect to papers | Papers link to topics/concepts; a question could be connected indirectly | `papers`, `paper_topics`, `paper_concepts` |
| Connect to datasets | Dataset research packets carry topic/brain-region metadata | `dataset_research_packets`, `dataset_packet_topics` |
| Agent-guided exploration | Tutor and Research agents support this; no "question mode" exists | `NeuroTutorAgent`, `NeuroResearchAgent` |
| Promote to hypothesis | Research agent can formulate a hypothesis from context | `research_hypotheses`, `evidence_links` |
| Track status | Hypotheses have a status field; questions have no status tracking | `research_hypotheses.status` |
| Cross-session recall | Session summaries are semantically retrieved; no question-specific index | `agent_context` ChromaDB collection |

The `research_questions` table exists in the schema but is not wired to agents, UI panels, or any structured workflow. It is an unfilled slot waiting for implementation.

---

## 4. Gap Analysis: What Is Missing

### 4.1 First-Class Question Capture

No current workflow lets a user say "save this question" and have it:
- stored with a timestamp and session reference
- tagged to existing topics/concepts
- shown in a UI panel
- retrievable by semantic search in a future session

The `research_questions` table exists but has no CRUD surface, no agent tool, and no UI panel.

### 4.2 Question Taxonomy and Categorization

Topics and Concepts exist, but there is no question→topic join, no question domain tags, and no way to group questions into clusters (e.g., "convergence questions," "mechanism questions," "measurement questions"). Questions accumulate as a flat list.

### 4.3 Socratic Agent Mode

Both existing agents (Tutor and Research) are task-oriented. Neither is designed to:
- hold a speculative question open deliberately
- probe it from multiple angles (analogy, counterexample, constraint)
- surface related questions rather than pushing toward a hypothesis

A "question exploration mode" — closer to Socratic dialogue than to hypothesis formulation — does not exist.

### 4.4 Question Status and Lifecycle Tracking

There is no status field on questions (open, active, shelved, promoted, answered). A researcher cannot see at a glance which questions are live, which led somewhere, and which were dead ends.

### 4.5 Question→Hypothesis Lineage

When a question matures into a hypothesis, there is no formal link. The `research_hypotheses` table has no `origin_question_id` foreign key. Intellectual provenance is lost.

### 4.6 Semantic Question Index

Study notes and sessions are semantically indexed; questions are not. A future session on a related topic cannot surface prior questions the way it surfaces prior session summaries.

---

## 5. Illustrative Use Case: The LLM–Brain Convergence Question

**The question**: Frontier LLMs appear to store and retrieve information through distributed pattern-matching over high-dimensional embeddings, triggered by input cues — analogous to how biological memory works (pattern completion from partial cues, context-gated retrieval, associative spreading activation). Is this convergence structural, functional, or merely metaphorical? And if structural, what does it imply about the computational constraints that any general intelligence — biological or artificial — must satisfy?

### What NeuroDb can do with this today

- **Topic creation**: create a "LLM-brain convergence" topic and connect it to existing concepts (semantic memory, hippocampal indexing, transformer attention, pattern completion)
- **Literature search**: Tutor agent can query PubMed and Semantic Scholar for papers on memory consolidation, sparse distributed representations, predictive coding, and transformer memory mechanisms; approved papers feed into the knowledge library
- **Dataset connection**: datasets from OpenNeuro or DANDI covering memory encoding/retrieval tasks (e.g., associative learning, cued recall fMRI) can be tagged to this topic
- **Hypothesis scaffolding**: once evidence accumulates, Research agent can formulate a hypothesis ("attractor dynamics in hippocampal CA3 and key-value attention in transformers are functionally equivalent under a generalized pattern-completion framework") with confounds and evidence links
- **Cross-session continuity**: each session on this topic generates a summary that informs the next session

### What it cannot do yet

- Store the original question with a timestamp and "this is where it started" provenance
- Tag it to topics without going through a hypothesis
- Explore it in a mode designed for open-ended Socratic dialogue rather than hypothesis formulation
- Surface it automatically in a future unrelated session on, say, "hippocampal indexing" because they share conceptual territory

---

## 6. Recommended Next Capabilities

Listed in order of implementation priority based on impact and fit with existing architecture.

### Priority 1 — Wire the `research_questions` table

The table exists. The missing pieces are small:

- Add CRUD to a FastAPI route (`/api/questions`)
- Add a Questions panel to the React UI (list + add form)
- Add a `question_topics` join table mirroring the pattern of `paper_topics`
- Add a semantic index for questions in the `neuro_research` ChromaDB collection so they surface in Tutor/Research agent context retrieval

**Cost**: low; the pattern is established by papers, topics, and concepts.

### Priority 2 — Question Status Lifecycle

Add a `status` column to `research_questions` (open / active / promoted / archived / answered) and a `promoted_hypothesis_id` foreign key. This creates the question→hypothesis lineage without restructuring the existing schema.

### Priority 3 — Socratic Exploration Mode

Add a new context mode (alongside `discovery`, `focused`, `evidence-boundary`) called `inquiry`. In `inquiry` mode:
- The agent holds the question open rather than driving toward a hypothesis
- It surfaces related questions (semantic search over `research_questions`)
- It proposes framings, analogies, and counterexamples rather than evidence links
- It can propose "save this as a candidate question" rather than "formulate hypothesis"

This requires a new system prompt branch in the agent context orchestrator, not a new agent.

### Priority 4 — Tutor-Driven Question Seeding

Allow the Tutor agent to emit a `propose_question()` tool call when a session surfaces an interesting tension or gap. Proposed questions land in `research_questions` with `status=candidate` and await user confirmation — the same pattern used by `queue_source()` for papers and `import_queue` for datasets.

### Priority 5 — Question Clustering View

Add a simple SQL-backed clustering view in the UI that groups questions by shared topic or concept tags. This does not require ML or new infrastructure — a GROUP BY over the `question_topics` join is sufficient to show thematic clusters, and the research panel already renders similar grouped views for hypotheses.

---

_This document is a living design note. Update it as capabilities are added._
