# Learning and Research Memory Refocus - Design Spec

**Date:** 2026-05-18
**Status:** Draft - user-approved direction; Phases 1-4 implemented, Phase 4 manual verification pending
**Source:** User brainstorming on shallow dataset value, learning goals, and agent grounding

---

## Thesis

NeuroDb is a neurology learning and research memory system. Its dual purpose is:

1. Learn neuroscience and neurology in a way that compounds across sessions.
2. Explore existing research, add to it through independent study, and investigate neurology with public evidence.

Datasets are tools for those goals, not the purpose of the project. A dataset record is useful only when it helps the user understand a topic, interpret a paper, evaluate a claim, form a research question, test a hypothesis, or find a follow-up path.

The current DB over-centers shallow dataset records. Many imported records contain little more than source, ID, title, modality, and subject count. That is not enough for learning, research exploration, or hypothesis work. The refocus must therefore solve two problems:

1. Reframe the system around learning and research objects rather than dataset cataloging.
2. Improve dataset sourcing so imported datasets carry enough source-native context to judge research usefulness.

---

## Current Limitation

The local DB can prove that a dataset exists, but often cannot explain why the dataset matters.

Common missing context:

- associated papers, DOIs, abstracts, authors, and publication status
- source landing page, README, task description, and protocol notes
- topics, concepts, brain regions, diseases, measures, and behavioral tasks
- participant groups, inclusion criteria, exclusion criteria, and clinical context
- acquisition, preprocessing, and analysis details
- file inventories, image/map previews, or links to source-native visual assets
- explicit limitations and whether the record is useful for teaching, research synthesis, or direct analysis

This creates bad downstream behavior. The UI presents shallow records as if they are research resources. The tutor and research assistant can retrieve records, but the records do not carry enough context to focus a strong neurology model productively. The research assistant may be forced to either ignore the DB or overstate what the DB supports.

---

## Design Principles

1. **Model knowledge remains valuable.** The primary model's neurology training may be better than the current local corpus. NeuroDb should not pretend local data is more complete than it is.
2. **Local context focuses the model.** NeuroDb should steer responses toward the user's active topics, papers, notes, hypotheses, and dataset resources.
3. **Evidence boundaries are visible.** Agents must distinguish general model knowledge, approved sources, user notes, dataset metadata, and assistant inference.
4. **Datasets are supporting resources.** Datasets are attached to topics, claims, papers, questions, and hypotheses when useful.
5. **Dataset imports must be source-aware.** Importing a dataset should harvest useful research context when the source exposes it, and record what is missing when it does not.
6. **Sparse records remain honest.** A sparse dataset can stay in the DB, but it must be labeled as sparse rather than silently treated as research-ready.
7. **Phases follow epoch ownership.** Each phase belongs to the epoch that already owns the relevant surface.

---

## Target Object Model

The DB should eventually support these first-class objects.

| Object | Purpose | Owner |
|---|---|---|
| `ResearchTopic` | A durable subject area such as stroke recovery, cortical remapping, epilepsy, basal ganglia, or hippocampal plasticity | DB schema, Tutor/Research write workflows |
| `Concept` | A learnable idea, mechanism, anatomy term, method, or clinical concept | DB schema, Tutor write workflows |
| `Paper` | Research paper, review, textbook chapter, guideline, or source-native publication | DB schema, Tutor curation |
| `Claim` | A source-linked assertion, finding, limitation, or methodological statement | DB schema, Research extraction/review |
| `EvidenceLink` | Typed relationship among claims, papers, datasets, notes, questions, and hypotheses | DB schema |
| `DatasetResource` | Dataset record plus research packet, sourcing status, usefulness, and missing context | DB schema/connectors |
| `StudyNote` | User note tied to concept, topic, source, dataset, or question | Existing DB/Tutor surface, expanded links |
| `ResearchQuestion` | Inquiry workspace that gathers local context and drives research activity | Existing Research storage, expanded |
| `Hypothesis` | Structured candidate contribution, grounded in claims, papers, datasets, and limitations | Existing Research storage, expanded |

Relationships should support the path:

```text
topic -> concept -> paper -> claim -> evidence link -> dataset resource -> question -> hypothesis -> study note
```

The path is not a required workflow order. It is the graph the tutor and research assistant can retrieve from.

---

## Dataset Research Packet

Every imported dataset should have an associated research packet. This packet separates "we found this dataset" from "this dataset is useful for research or learning."

Minimum packet fields:

| Category | Examples |
|---|---|
| Source identity | source, source ID, landing URL, API URL, version/date, license/access notes |
| Source-native text | description, README excerpts, task/protocol notes, keywords, metadata JSON |
| Publication linkage | DOI, PubMed ID, paper URL, title, abstract, authors, journal, year |
| Topics and concepts | source keywords, inferred topics, brain regions, diseases, methods, measures |
| Participant context | subject count, groups, diagnosis, age range, inclusion/exclusion notes where available |
| Methods | modality, task, acquisition, preprocessing, analysis/modeling fields where exposed |
| Assets | manifest, file counts, file types, sizes, thumbnails/maps/previews when available, raw-download policy |
| Usefulness | research value, teaching value, analysis readiness, supported workflows, unsupported workflows |
| Gaps | missing paper, missing README, missing participants, missing task, missing files, missing license, etc. |
| Provenance | field-level source, confidence, transform version, harvest timestamp |

Heavy raw assets should not be downloaded by default. The packet should store manifests, links, checksums, sizes, source previews, and on-demand download options. Source-provided summaries, paper links, thumbnails, maps, README files, task metadata, and file inventories should be harvested when feasible.

### Dataset Usefulness States

| State | Meaning |
|---|---|
| `sparse` | Exists locally but lacks enough context for research interpretation |
| `partial` | Has some useful context, but gaps remain |
| `research_context_ready` | Has enough paper/topic/method context for learning and research synthesis |
| `analysis_ready` | Has enough accessible data and metadata for direct local analysis |
| `not_useful_for_focus` | Stored, but not relevant to the current topic/question |

Agents and UI should display these states directly.

---

## Context Modes

The interface should expose how local context is used. These modes apply to tutor and research workflows.

| Mode | Behavior | Default use |
|---|---|---|
| `General` | Model-first. Use strong neurology training knowledge. Local context is optional and only used when clearly relevant. | Broad learning questions, definitions, anatomy, physiology |
| `Contextual` | Model-first, but actively retrieve and use NeuroDb context to focus the answer around the user's active interests. | Default tutor and research mode |
| `Grounded` | Approved/local-source-first. Claims require local source labels. Use model knowledge only to explain source-grounded material or state gaps. | Research synthesis, hypothesis drafts, evidence review |

The system should not force a false choice between model knowledge and local knowledge. The intended stack is:

```text
general neurology model knowledge
+ active focus
+ local papers / notes / claims / dataset resources
+ explicit evidence boundaries
```

---

## Agent Behavior

### NeuroTutorAgent

The tutor teaches using model knowledge, but uses NeuroDb to personalize and compound learning.

Required behavior:

- retrieve active topic, relevant concepts, approved papers, study notes, previous session summaries, and useful dataset resources
- label whether the explanation is general neurology, NeuroDb context, or source-grounded
- recommend next concepts or readings based on the active topic
- save durable study notes when the user asks or when a workflow explicitly captures them
- identify when local dataset resources are sparse or not useful for the learning question

Example answer boundary:

```text
General neurology:
...

From your NeuroDb context:
...

Local dataset value:
This dataset is related, but currently sparse. It has a title and modality but no linked paper or task metadata.
```

### NeuroResearchAgent

The research assistant should use local resources to focus, constrain, and audit research work. It should still rely on model knowledge for broad neurology reasoning when the mode allows it.

Required behavior:

- start from a research question or active focus, not from a dataset list
- retrieve papers, claims, limitations, study notes, prior hypotheses, and dataset research packets
- distinguish locally supported findings from general model knowledge
- identify evidence gaps and dataset insufficiency explicitly
- produce hypotheses only with evidence links, limitations, confounds, and unsupported-claim labels
- nominate sources for Tutor curation rather than writing directly to the knowledge library

Research synthesis should include an evidence lens:

```text
Evidence used:
- General model knowledge: yes
- Approved papers: 4
- User notes: 2
- Dataset resources: 1 partial
- Local gaps: no dataset with lesion-location metadata
```

---

## UI Design Impact

The workbench should make learning/research focus visible before dataset browsing.

### Top-Level Navigation

Recommended long-term workbench areas:

- Learn
- Research Questions
- Knowledge Library
- Evidence / Claims
- Datasets
- Study Notes
- Hypotheses

Datasets remain available, but they are no longer the main destination for the project.

### Persistent Context Control

Chat and research surfaces should show:

```text
Response focus: General | Use NeuroDb context | Strictly grounded
Active focus: [topic or research question]
Using: 5 papers - 3 notes - 2 claims - 1 dataset
```

The default is `Use NeuroDb context`.

### Dataset Detail Surface

Dataset cards should show:

- usefulness state
- linked papers/topics/concepts
- source-native summary
- missing context
- file/asset manifest
- whether it can support the active question

Dataset search results should not imply research readiness when the record is sparse.

---

## Retrieval and Indexing Impact

The ChromaDB layer should evolve from a generic semantic bucket into typed retrieval paths.

| Collection / Index | Content | Owner |
|---|---|---|
| `knowledge_library` | Approved paper/review/textbook summaries | Tutor |
| `agent_context` | Session summaries and active topic memory | Agent Core |
| `study_notes` | User notes and concept tags | Tutor/DB helper |
| `paper_context` | Paper abstracts, source summaries, publication metadata | Tutor/DB helper |
| `claims` | Source-linked findings, limitations, and evidence statements | Research/DB helper |
| `dataset_resources` | Dataset research packets and source-native descriptions | DB helper |
| `research_questions` | Question descriptions and topic context | Research helper |
| `hypotheses` | Draft/accepted hypothesis summaries | Research helper |

Retrieval policy should be mode-aware:

- `General`: optional local retrieval, small context budget
- `Contextual`: retrieve active focus plus related notes/papers/datasets
- `Grounded`: retrieve approved/local sources first and require source labels

---

## Phased Implementation Plan By Epoch

This plan avoids a rewrite. Each phase produces a useful increment and maps to existing epoch ownership.

### Phase 0 - Cross-Epoch Design Baseline

**Owner:** Documentation / project coordination  
**Status:** Complete

Deliverables:

- approve mission refocus and dataset-sourcing thesis
- define context modes, dataset packet, and evidence boundaries
- use this spec to update individual epoch plans when each implementation phase starts

Acceptance criteria:

- `docs/projectStatus.md` references this spec
- no runtime behavior changes required

### Phase 1 - DB: Dataset Research Packet And Sourcing Audit

**Owner:** DB epoch  
**Status:** Complete — implemented and manually signed off 2026-05-18
**Fits existing plan:** DB Phase 9, Research-Grade Metadata Enrichment

Deliverables:

- add a normalized `dataset_research_packets` table or equivalent schema
- add source-aware enrichment hooks for OpenNeuro, DANDI, NeuroVault, and Allen Brain Atlas
- harvest landing URLs, README/description text, publication links, manifests, and source-native metadata when exposed
- add usefulness state and missing-context fields
- add field-level provenance and confidence for inferred values
- add a coverage report by source

Acceptance criteria:

- every dataset can be labeled `sparse`, `partial`, `research_context_ready`, or `analysis_ready`
- coverage report shows which fields are populated by source
- shallow records remain visible but are marked as sparse
- agents can retrieve packet summaries through a DB-owned helper

### Phase 2 - DB + Tutor: Papers, Topics, Concepts, And Study Context

**Owner:** DB epoch for schema, Tutor epoch for curation/write workflows  
**Status:** Design complete — ready for implementation plan; see `docs/superpowers/specs/2026-05-18-phase2-papers-topics-concepts-design.md`  
**Fits existing plan:** DB Phase 8/9 plus Tutor backlog sprint

Deliverables:

- add first-class `papers`, `topics`, `concepts`, and linking tables
- extend Knowledge Library entries to link to topics/concepts/papers
- support approved/candidate/rejected status for source-derived paper context
- embed approved paper summaries, concepts, and study notes in typed retrieval paths
- allow dataset packets to link to papers/topics/concepts

Acceptance criteria:

- a topic page can show related approved papers, concepts, notes, and dataset resources
- a dataset can show linked papers and topics
- Tutor can retrieve topic/context bundles without raw SQL

### Phase 3 - Research: Claims, Evidence Links, And Question-Centered Workflow

**Owner:** Research epoch, with DB-owned schema

Deliverables:

- expand `research_questions` into workspaces with active topic, status, and linked resources
- add `claims` and `evidence_links` storage
- add tools to extract candidate claims from approved papers and mark them as candidate/approved/rejected
- link hypotheses to evidence, claims, papers, datasets, limitations, and confounds
- add gap tracking for unsupported claims and missing local evidence

Acceptance criteria:

- a research question can display papers, notes, claims, datasets, and hypotheses
- hypothesis drafts cite evidence links rather than only free-text evidence JSON
- research assistant can report which local evidence supports or does not support an answer

### Phase 4 - Agent Core + Tutor + Research: Context Modes And Evidence Boundaries

**Owner:** Agent Core for shared mode mechanics, Tutor/Research for prompts/tools
**Status:** Implemented — automated verification passed; manual verification pending; see `docs/superpowers/specs/2026-05-19-phase4-context-modes-evidence-boundaries-design.md`

Deliverables:

- add context mode to chat/research requests and persisted preferences
- define shared answer-boundary conventions for `General`, `Contextual`, and `Grounded`
- add retrieval orchestration helpers that return typed context bundles
- update NeuroTutorAgent and NeuroResearchAgent prompts to use context bundles and label source boundaries
- include counts of retrieved papers, notes, claims, datasets, and gaps in stream metadata

Acceptance criteria:

- the same question produces visibly different behavior in General, Contextual, and Grounded modes
- research answers identify general model knowledge vs NeuroDb context
- grounded mode refuses or qualifies claims that lack local/approved support

### Phase 5 - UI: Focus Controls, Evidence Lens, And Dataset Honesty

**Owner:** UI epoch
**Fits existing plan:** UI-5 Enhancements or UI-6 after common UI-5 sign-off

**Required pre-design checkpoint:** Before implementing Phase 5, hold a focused
user brainstorm on agent mode control. Phase 4 proved the plumbing with explicit
`general`, `contextual`, and `grounded` settings, but the product direction
should not require the user to manually choose a mode for every question.

Brainstorm topics:

- whether the default should be `auto`, where the agent/router chooses the
  effective mode from user intent, active focus, and evidence needs
- when user language should force grounded behavior, such as "use local evidence
  only" or "what does NeuroDb support?"
- when user language should force general behavior, such as broad teaching,
  definitions, or mechanism explanations
- how the UI should display the effective mode and why it was selected
- whether the user should be able to lock a mode for a session, a turn, or a
  research workspace
- how to prevent mode controls from becoming a burden while still preserving
  user authority over evidence strictness

Tentative direction pending that brainstorm:

- default user-facing control should be `Auto`
- API should distinguish `requested_mode` from `effective_mode`
- explicit user override should remain available: General, Use NeuroDb context,
  Strictly grounded
- evidence lens should display the effective mode, source counts, active focus,
  and unsupported-local-evidence warnings

Deliverables:

- add context control to chat and research surfaces, with `Auto` as the default
  unless the user brainstorm decides otherwise
- add active focus selector for topic or research question
- add evidence lens showing retrieved counts and unsupported local gaps
- add research-question workspace with tabs for overview, literature, concepts, claims, datasets, notes, and hypotheses
- update dataset cards to show usefulness state, packet summary, missing context, and active-question relevance

Acceptance criteria:

- agent/router can select the effective context mode automatically for common
  learning and research turns
- user can override or lock General, Use NeuroDb context, or Strictly grounded
  when they explicitly want to constrain the response
- UI shows the effective mode and, when useful, why that mode was selected
- UI shows what local resources were used in an answer
- dataset browser makes sparse vs research-ready status obvious
- research workflow starts from question/focus rather than dataset list

### Phase 6 - Config Control: Context Policy, Budgets, And Telemetry

**Owner:** Config Control epoch

Deliverables:

- add config for context budgets by mode and task type
- log retrieval counts, context mode, evidence-source counts, and grounded-mode gap counts in telemetry
- define model-tier defaults for extraction, claim review, research synthesis, and grounded answer review
- preserve existing provider routing through `neurodb_models.toml`

Acceptance criteria:

- telemetry can answer whether local context is being used and whether it improves workflows
- context size remains controlled for cost and latency
- premium models are reserved for high-value review/synthesis steps

---

## Epoch Impact Summary

| Epoch | Impact | First phase |
|---|---|---|
| DB | Adds research packets, richer source-aware dataset ingestion, papers/topics/concepts/claims/evidence schema, and coverage reports | Phase 1 |
| Agent Core | Adds shared context mode plumbing, context bundle injection, stream metadata for evidence counts | Phase 4 |
| Tutor | Becomes a model-knowledge-plus-NeuroDb-context learning agent; owns curation and concept/study memory workflows | Phase 2 |
| Research | Becomes question-centered and evidence-link based; uses dataset resources as one support type | Phase 3 |
| UI | Adds context controls, active focus, evidence lens, question workspace, and honest dataset usefulness display | Phase 5 |
| Config Control | Adds context budgets, retrieval telemetry, and task routing policy for extraction/review/synthesis | Phase 6 |

---

## Testing Strategy

Each implementation phase must create or update a manual test plan before code changes if it changes a user-visible workflow.

Minimum automated coverage by phase:

- DB Phase 1: connector fixture tests for packet extraction, missing-context labels, provenance, and idempotent enrichment
- Tutor Phase 2: unit tests for topic/paper/concept links and typed retrieval helper behavior
- Research Phase 3: tests for claim/evidence-link persistence and hypothesis grounding
- Agent Phase 4: tests for context-mode prompt/retrieval selection and source-boundary metadata
- UI Phase 5: component tests for context control, evidence lens, and dataset usefulness display
- Config Phase 6: tests for context budget routing and telemetry fields

Manual verification should focus on human-visible evidence boundaries:

- General mode can teach well when local context is weak
- Contextual mode focuses on the active topic/question
- Grounded mode identifies unsupported local claims
- sparse dataset records are visibly marked and not overused

---

## Risks And Tradeoffs

| Risk | Mitigation |
|---|---|
| Schema scope grows too quickly | Start with dataset packets and topic/paper links before full claim graph |
| Agents over-trust local sparse data | Use usefulness states, missing-context labels, and grounded-mode refusal rules |
| Agents ignore local context because model knowledge is stronger | Default to Contextual mode and show retrieved local counts |
| Source APIs expose inconsistent metadata | Use source-specific harvesters and field-level provenance/confidence |
| Raw data is too large to download | Store manifests/previews/links by default, raw assets on demand |
| UI becomes too complex | Keep question/focus as the main workflow; show datasets as supporting resources |
| Curation burden increases | Separate candidate from approved sources and claims |

---

## Open Decisions

1. Should `ResearchTopic` and `Concept` be separate tables immediately, or should Phase 2 start with a single `knowledge_nodes` table and typed edges?
2. Should claim extraction be automatic on source approval, user-triggered, or research-agent-triggered?
3. What is the minimum dataset packet needed before a record is `research_context_ready`?
4. Which source should be enriched first: OpenNeuro, DANDI, NeuroVault, or Allen Brain Atlas?
5. Should active focus be one global preference or scoped separately to Tutor and Research?
