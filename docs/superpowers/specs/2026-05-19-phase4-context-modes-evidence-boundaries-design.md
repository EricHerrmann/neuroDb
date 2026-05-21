# Phase 4 — Context Modes and Evidence Boundaries

**Date:** 2026-05-19
**Status:** Implemented — automated verification passed; manual verification pending
**Owner:** Agent Core epoch (shared mechanics); Tutor and Research epochs (agent behavior)
**Parent spec:** `docs/superpowers/specs/2026-05-18-learning-research-memory-refocus-design.md` Phase 4

---

## Goal

Add shared context modes and evidence-boundary behavior across NeuroTutorAgent
and NeuroResearchAgent.

Phase 1 made datasets honest through research packets. Phase 2 added papers,
topics, concepts, and topic bundles. Phase 3 added claims, evidence links,
research gaps, and question bundles. Phase 4 makes agents use those local
resources deliberately instead of treating all answers as the same kind of
model response.

The user should be able to ask the same question in three modes:

| Mode | Primary behavior |
|---|---|
| `general` | Model-first neurology explanation. Local context is optional and small. |
| `contextual` | Model-first, but actively focused by NeuroDb topics, papers, notes, claims, gaps, and dataset packets. |
| `grounded` | Local approved-source-first. Claims without local support are refused, qualified, or recorded as gaps. |

Default mode for Tutor and Research is `contextual`.

---

## Problem

The project now has local resources that can focus answers:

- topic bundles from Phase 2
- question bundles, claims, evidence links, and gaps from Phase 3
- dataset research packets from Phase 1
- approved Knowledge Library summaries and study notes

But those resources are still exposed mostly as tools. The agent has to decide,
turn by turn, whether to retrieve them and how to explain their evidentiary
limits. That creates inconsistent behavior:

- the tutor may overuse local context when the model's general neurology
  knowledge is better
- the research assistant may answer from training knowledge when the user expects
  local evidence
- grounded answers do not yet have a strict local-support contract
- the UI cannot reliably show what local resources were used in a turn

Phase 4 introduces a shared context contract so retrieval, prompts, and stream
metadata all agree on the mode.

---

## Non-Goals

- No new large UI surface. Full controls and evidence lens are Phase 5.
- No model-routing or token-budget telemetry changes. Those are Phase 6.
- No new claim extraction schema. Phase 3 owns claims, links, and gaps.
- No raw-asset download or dataset analysis.
- No automatic conversion of legacy free-text evidence into structured links.

Phase 4 may add API fields and persisted preferences so the current UI can pass a
mode, but the polished UI affordance remains Phase 5.

---

## Architecture

Phase 4 adds four layers.

1. **Context mode contract**
   - canonical mode names
   - default behavior
   - valid answer-boundary labels
   - source-count metadata shape

2. **Context orchestrator**
   - shared helper that receives a user message, mode, agent kind, and optional
     active focus
   - retrieves compact typed context through DB-owned helpers
   - returns a `ContextBundle` and a prompt-ready context block

3. **Agent integration**
   - BaseAgent accepts mode and context bundle
   - NeuroTutorAgent and NeuroResearchAgent add mode-specific prompt rules
   - grounded mode enforces local-source qualification

4. **API and preference plumbing**
   - chat requests can carry `context_mode`
   - `app_preferences` persists the default context mode
   - SSE includes source counts so the UI can later render an evidence lens

---

## Context Mode Contract

Use lowercase wire values:

```python
ContextMode = Literal["general", "contextual", "grounded"]
```

User-facing labels remain:

| Wire value | UI label |
|---|---|
| `general` | General |
| `contextual` | Use NeuroDb context |
| `grounded` | Strictly grounded |

Invalid values are rejected at API boundaries. Agents should never infer a fourth
mode from prose.

### Mode Rules

| Mode | Retrieval | Answer boundary | Local gap behavior |
|---|---|---|---|
| `general` | Do not proactively retrieve unless active focus is supplied or the user asks for local context. | Label local context only if used. | No automatic gap creation. |
| `contextual` | Retrieve active topic/question bundle when available; otherwise do lightweight topic/question lookup from the message. | Separate general model knowledge from NeuroDb context. | Mention gaps when bundle exposes them; do not block answer. |
| `grounded` | Retrieve approved/local resources first. Use only local sources for factual research claims. | Required `Local evidence` and `Unsupported or missing` sections. | If local support is absent, qualify/refuse and optionally call `add_gap` in Research mode. |

---

## Active Focus

Phase 4 supports an optional active focus. Phase 5 will provide the UI selector.

```python
class ActiveFocus(TypedDict, total=False):
    focus_type: Literal["topic", "research_question"]
    focus_id: int
    label: str
```

Resolution order:

1. explicit request fields
2. persisted app preference keys, if present:
   - `active_topic_id`
   - `active_research_question_id`
3. lightweight lookup from the user message in `contextual` or `grounded`
4. no focus

If both topic and research question are present, research question wins because
it contains a question workspace and may link to a topic.

---

## Context Orchestrator

**New module:** `src/neurodb/agents/context_orchestrator.py`

The helper owns retrieval policy, not storage. It calls existing DB helper
functions and store APIs.

```python
class ContextRequest(TypedDict, total=False):
    mode: ContextMode
    agent_mode: Literal["neuro_tutor", "neuro_research"]
    user_message: str
    active_focus: ActiveFocus | None
    max_papers: int
    max_claims: int
    max_notes: int
    max_datasets: int

class SourceCounts(TypedDict):
    papers: int
    concepts: int
    study_notes: int
    dataset_packets: int
    claims: int
    evidence_links: int
    gaps: int
    semantic_hits: int

class ContextBundle(TypedDict, total=False):
    mode: ContextMode
    agent_mode: str
    active_focus: ActiveFocus | None
    topic_bundle: dict | None
    question_bundle: dict | None
    knowledge_hits: list[dict]
    semantic_hits: list[dict]
    source_counts: SourceCounts
    gap_summaries: list[dict]
    warnings: list[str]
    prompt_block: str
```

Primary function:

```python
def build_context_bundle(
    engine,
    *,
    request: ContextRequest,
    knowledge_store=None,
    vector_store=None,
    context_store=None,
) -> ContextBundle:
    ...
```

### Retrieval Policy

`general`:

- include prior session context through existing `prior_context`
- do not call `get_topic_bundle` or `get_question_bundle` unless an active focus
  is explicit
- optional semantic search only when the user explicitly asks "from NeuroDb",
  "from my notes", "local evidence", or equivalent phrasing

`contextual`:

- if active focus is a topic, call `get_topic_bundle`
- if active focus is a research question, call `get_question_bundle`
- run Knowledge Library semantic search with the user message when
  `knowledge_store` is available
- run vector search against existing dataset/note collection when
  `vector_store` is available
- return compact counts and summaries; do not dump raw JSON into the prompt

`grounded`:

- require topic/question bundle or approved local search hits
- prefer approved claims, approved papers, study notes, and dataset packets with
  `research_context_ready` or `analysis_ready`
- include sparse/partial dataset packets only as limitations, not as support
- add a warning when no approved local support is found
- for Research mode, expose enough gap context for the agent to call `add_gap`
  when the user asks for a research conclusion that local evidence cannot support

---

## Prompt-Ready Context Block

The orchestrator returns a compact text block appended to the system prompt.

Format:

```text
NeuroDb context mode: contextual
Active focus: topic 12 — stroke recovery

Use these source boundaries:
- General model knowledge: allowed, label it when mixed with local context.
- NeuroDb context: papers=2, concepts=3, notes=1, claims=0, datasets=1, gaps=0.
- Dataset caveat: sparse or partial dataset packets are context only, not evidence.

Compact local context:
...
```

The block should stay short. Long paper abstracts, claim lists, or dataset packet
metadata are summarized or capped by per-type limits.

---

## Answer Boundary Conventions

Agents should use consistent labels.

### General Mode

No required headings. If local context is used:

```text
From NeuroDb:
...
```

### Contextual Mode

Expected structure when local context is present:

```text
General neurology:
...

From your NeuroDb context:
...

Local gaps:
...
```

If no local context is found, say so plainly and continue with general model
knowledge.

### Grounded Mode

Required structure:

```text
Local evidence:
...

Unsupported or missing:
...

Careful answer:
...
```

Rules:

- Do not present model-only knowledge as local evidence.
- Do not use sparse dataset packets as direct support.
- If local evidence is absent, answer with the gap rather than inventing support.
- Research agent may call `add_gap` for missing local evidence; Tutor should only
  explain the absence unless the user asks to save a note.

---

## Agent Core Changes

**File:** `src/neurodb/agents/base.py`

Constructor additions:

```python
context_mode: str = "contextual"
context_bundle: dict | None = None
```

BaseAgent responsibilities:

- validate or store mode provided by the API/call site
- expose `_context_mode` and `_context_bundle` to subclasses
- include context source counts in stream events when available
- avoid owning retrieval policy directly

SSE additions:

Before the first model token:

```json
{
  "type": "context_summary",
  "context_mode": "contextual",
  "active_focus": {"focus_type": "topic", "focus_id": 12, "label": "stroke recovery"},
  "source_counts": {
    "papers": 2,
    "concepts": 3,
    "study_notes": 1,
    "dataset_packets": 1,
    "claims": 0,
    "evidence_links": 0,
    "gaps": 0,
    "semantic_hits": 2
  },
  "warnings": []
}
```

The non-streaming `chat()` path does not need a new public return type in Phase 4.
Tests should cover `chat_stream()` metadata because the React UI consumes SSE.

---

## Tutor Agent Changes

**File:** `src/neurodb/agents/tutor_agent.py`

Constructor accepts `context_mode` and `context_bundle`, passes both to BaseAgent.

Prompt changes:

- `general`: teach normally using model neurology knowledge; local context is
  optional
- `contextual`: use the context bundle to personalize explanations around the
  user's topic, papers, notes, and dataset packets
- `grounded`: only make local-source-supported claims; explain gaps without
  overstating the local library

Tool behavior:

- keep existing `search_topics`, `get_topic_bundle`, `search_knowledge_library`,
  and `queue_source`
- avoid redundant topic lookup when `context_bundle.topic_bundle` already exists
- keep queuing external sources as candidate papers; do not auto-approve

Tutor-specific boundary:

The tutor can use model knowledge broadly in `general` and `contextual` modes
because learning is one primary goal. In `grounded` mode, it may still explain
terms, but any factual claim about "what the literature shows" must be tied to
local approved papers, claims, notes, or dataset packets.

---

## Research Agent Changes

**File:** `src/neurodb/agents/research_agent.py`

Constructor accepts `context_mode` and `context_bundle`, passes both to BaseAgent.

Prompt changes:

- `general`: brainstorm mechanisms and research framing, while clearly labeling
  ungrounded ideas as model reasoning
- `contextual`: start from question/topic bundle when present; use claims, gaps,
  and evidence links as the organizing structure
- `grounded`: require local evidence links or approved local claims before
  presenting research claims; create or suggest gaps for unsupported claims

Tool behavior:

- if context bundle contains a question bundle, do not call `get_question_bundle`
  again unless stale or incomplete
- `draft_hypothesis` in grounded mode should be followed by `add_evidence_link`
  calls when local support exists
- in grounded mode, missing support should call or suggest `add_gap`

Research-specific boundary:

Grounded mode is stricter for Research than Tutor. If local approved evidence is
absent, the agent should not produce a research conclusion. It can produce:

- a gap statement
- a proposed search/curation path
- a clearly labeled model-informed hypothesis seed, only if the user asked for
  brainstorming rather than grounded synthesis

---

## API and Preference Changes

**Files:**

- `src/neurodb/api/schemas/chat.py`
- `src/neurodb/api/routes/chat.py`
- `src/neurodb/api/schemas/preferences.py`
- `src/neurodb/api/routes/preferences.py`

`ChatTurnRequest` adds:

```python
context_mode: str | None = None
active_focus_type: str | None = None
active_focus_id: int | None = None
```

Resolution:

1. request `context_mode`
2. persisted `app_preferences.context_mode`
3. default `contextual`

Persisted preference:

- key: `context_mode`
- allowed values: `general`, `contextual`, `grounded`

Preferences response includes:

```json
{
  "agent_mode": "neuro_tutor",
  "context_mode": "contextual",
  "relevance_threshold": 0.7
}
```

Add route:

```text
PUT /api/preferences/context-mode
```

with body:

```json
{ "mode": "grounded" }
```

Phase 5 owns the visible UI control, but this route lets manual tests and future
frontend work drive the mode.

---

## Typed Semantic Retrieval

Phase 4 should not create a sprawling new vector architecture. It should add a
thin typed adapter over existing stores and only add new embeddings where the
write path is already local and deterministic.

Minimum:

- Knowledge Library semantic search remains `knowledge_library`
- dataset/note semantic search remains `neuro_research`
- context orchestrator records returned hit types in `source_counts.semantic_hits`

Optional within Phase 4 if implementation remains small:

- embed approved claims into a `claims` collection when claim status becomes
  `approved`
- embed topic/concept names and descriptions into a `topic_context` collection

If optional embeddings are deferred, context modes still work through SQL bundles
and existing semantic stores. Do not block Phase 4 on full Chroma reindexing.

---

## Testing

### Unit Tests

**`tests/unit/test_context_modes.py`**

- valid modes accepted; invalid modes rejected
- default mode is `contextual`
- persisted preference overrides default
- request mode overrides persisted preference

**`tests/unit/test_context_orchestrator.py`**

- `general` without focus returns empty or minimal local context
- `contextual` with topic focus calls `get_topic_bundle`
- `contextual` with question focus calls `get_question_bundle`
- `grounded` with no approved/local support returns a warning
- source counts are correct for papers, concepts, notes, dataset packets, claims,
  evidence links, gaps, and semantic hits
- prompt block includes mode and evidence-boundary instructions

**`tests/unit/test_tutor_context_modes.py`**

- tutor prompt changes by mode
- contextual mode includes context bundle instructions
- grounded mode includes local-source-only rule
- existing tools remain present

**`tests/unit/test_research_context_modes.py`**

- research prompt changes by mode
- grounded mode requires local evidence or gap reporting
- context bundle can suppress redundant question-bundle lookup in terminal paths

**`tests/unit/test_api_chat_context_mode.py`**

- chat request passes `context_mode` to agent builder
- invalid mode returns 400
- persisted default is used when request omits mode
- `context_summary` SSE event is emitted before the answer

### Integration Tests

**`tests/integration/test_phase4_context_modes.py`**

Fixture setup:

- create topic `stroke recovery`
- link concept, approved paper, approved claim, study note, and one dataset packet
- create one research question linked to the topic
- create one open gap

Assertions:

- same user message in `general` produces no required local source counts
- same message in `contextual` returns source counts and context prompt block
- same message in `grounded` includes local evidence requirement and gap warning
- Research agent receives question bundle in contextual/grounded modes
- Tutor agent receives topic bundle in contextual/grounded modes

---

## Manual Test Plan

Before implementation, create:

`docs/testsPlans/manualTestPlan_phase4_context_modes.md`

Required evals:

1. Automated prerequisite: `uv run pytest tests/ -q`
2. API preference: set mode to `general`, `contextual`, `grounded`
3. Tutor: same question in all three modes shows visibly different source
   behavior
4. Research: grounded mode identifies a missing local-evidence gap
5. SSE: context summary event reports source counts
6. Regression: existing Topic/Question bundle tools still work

---

## Acceptance Criteria

- `context_mode` is accepted at chat request boundaries and persisted as an app
  preference.
- Tutor and Research agents receive a context bundle and mode-specific prompt
  rules.
- Contextual mode retrieves and summarizes active topic or research-question
  context.
- Grounded mode qualifies or refuses unsupported local claims instead of treating
  model knowledge as evidence.
- SSE emits source-count metadata that Phase 5 can render as an evidence lens.
- Existing Phase 2 topic bundle and Phase 3 question bundle tools continue to
  work.

---

## Implementation Slices

### P4.1 — Mode Contract and Preferences

- add mode validation helper
- add `context_mode` to chat schema
- add preference response/update route
- unit-test API validation and default resolution

### P4.2 — Context Orchestrator

- add `ContextRequest`, `ContextBundle`, `SourceCounts`
- retrieve topic/question bundles by active focus
- add compact prompt block generation
- unit-test retrieval policy by mode

### P4.3 — BaseAgent Stream Metadata

- add constructor fields for `context_mode` and `context_bundle`
- emit `context_summary` event in `chat_stream`
- preserve existing non-streaming behavior

### P4.4 — Tutor and Research Prompt Integration

- update constructors and prompt builders
- add mode-specific source-boundary rules
- avoid redundant bundle tool calls when context bundle already exists

### P4.5 — Integration and Manual Plan

- create manual test plan before implementation
- add Phase 4 integration fixture
- verify no regressions in Phase 2 and Phase 3 helper tests

---

## Open Decisions

1. Should active focus be persisted globally at Phase 4, or should Phase 4 only
   accept request-scoped focus and leave persistence to Phase 5?
2. Should grounded Tutor mode be allowed to queue candidate papers from model
   knowledge, or should it only recommend curation as a next step?
3. Should approved claims be embedded in Phase 4, or should claim semantic search
   wait until after the SQL context-mode behavior is signed off?
4. Should `local_db` agent mode ignore context mode, or should it expose only the
   retrieval-count metadata for consistency?
