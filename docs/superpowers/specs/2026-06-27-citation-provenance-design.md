# Source-Provenance Citations (NeuroTutor + NeuroResearch)

- **Date:** 2026-06-27
- **Status:** Design — approved in brainstorming, pending spec review
- **Scope:** Agent response behavior — how NeuroTutor and NeuroResearch cite papers. Plus one supporting data change in the topic/grouping bundle serialization.

## 1. Problem & Motivation

When the agents cite a paper they do not tell the reader whether that paper is in the curated Knowledge Library (and at what depth) or is an external result. The reader cannot tell a fully-ingested, quotable source from a metadata-only stub or a live web hit. The agents already carry the data needed to distinguish these (`Paper.data_tier`, `search_literature` URLs) but never surface it in citations.

This adds an inline **provenance tag** to every paper citation, shared across both agents ("common behavior").

## 2. Goals

1. When an agent cites a specific paper, append an inline provenance tag:
   - **In the Knowledge Library:** `(Knowledge Library · <level>)` where `<level>` is the paper's `data_tier` mapped to the words **metadata / abstract / full text**.
   - **Not in the library** (e.g. a `search_literature` result): a Markdown link to the paper's URL instead.
   - **Neither in the library nor has a URL:** `(not in Knowledge Library)`, plus the existing model-knowledge / needs-verification labeling.
2. The rule is **common** to NeuroTutor and NeuroResearch, defined once.
3. The rule never lets the model assert a library status or level that did not come from a tool result or local context (consistent with existing anti-fabrication rules).

## 3. Non-Goals (YAGNI)

- No UI/React changes.
- No change to how papers are stored or how `data_tier` is computed; values are taken as-is.
- No footnote/table citation styles (inline tag only).
- No change to `search_knowledge_library` or `search_literature` result shapes (they already carry what is needed).

## 4. Design

### 4.1 Where the rule lives (decision: shared code constant)

Define a single module-level constant `CITATION_PROVENANCE_RULE: str` in `src/neurodb/agents/behavior_instructions.py`. Both `tutor_agent.py` and `research_agent.py` append it to their system prompt `prompt_parts` during construction (the same place they already append `load_agent_behavior_instructions()`).

Rationale: this is a correctness rule (it governs whether the user is told a source is verified/in-library), and the existing related anti-fabrication rules live in the code prompts. A shared constant guarantees presence (cannot be silently removed by editing the optional `docs/agent_behavior.md`) and is unit-testable. It is defined once and imported by both agents (DRY).

### 4.2 Rule text

`CITATION_PROVENANCE_RULE` reads approximately:

> When you cite a specific paper, mark its source provenance inline, right after the paper. If the paper came from a Knowledge Library result (a `search_knowledge_library` result or a paper in the provided local/topic context), append `(Knowledge Library · <level>)`, where `<level>` is that result's `data_tier` rendered as `metadata`, `abstract`, or `full text`. If the paper is not in the Knowledge Library (for example a `search_literature` result), instead link it with its URL using Markdown, e.g. `[Title](https://…)`. If a cited paper is neither in the Knowledge Library nor has a URL, write `(not in Knowledge Library)` and apply the usual model-knowledge / needs-verification labeling. Never state a Knowledge Library status or level that did not come from a tool result or the provided local context.

### 4.3 Level mapping helper

Add a pure helper (in `behavior_instructions.py`, next to the constant):

```python
def data_tier_label(data_tier: str | None) -> str:
    """Map a stored Paper.data_tier to a human citation level."""
    return {
        "metadata": "metadata",
        "abstract": "abstract",
        "full_text": "full text",
    }.get((data_tier or "").strip().lower(), "metadata")
```

`full_text` → `full text`; unknown/empty → `metadata` (the schema default). The agents do not need to call this at runtime (the model formats the tag from the `data_tier` value it sees), but it documents the canonical mapping and is unit-tested so the rule text and data stay aligned. Use of the helper in code (e.g. pre-formatting) is optional and out of scope; the contract is the mapping itself.

### 4.4 Data plumbing — topic/grouping bundle papers

`search_knowledge_library` results already include `data_tier` (via `knowledge_store.search` metadata); `search_literature` results already include `url` and are inherently non-library. The gap is the topic/grouping context path.

In `src/neurodb/db/grouping_store.py`, `get_grouping_bundle()` serializes papers (currently `id, title, doi, status, summary` at lines ~300-308). Add two fields so library papers cited from local/topic context can show level and link:

```python
"papers": [
    {
        "id": p.id,
        "title": p.title,
        "doi": p.doi,
        "status": p.status,
        "summary": p.summary,
        "data_tier": p.data_tier,
        "url": p.url,
    }
    for p in papers
    if p is not None
],
```

`Paper.data_tier` is non-nullable (`schema.py`, default `"metadata"`); `Paper.url` is nullable. No migration needed — both columns already exist.

### 4.5 Data flow

```
cite a paper
 ├─ from search_knowledge_library result → data_tier present → "(Knowledge Library · <label>)"
 ├─ from local/topic context (get_grouping_bundle) → now carries data_tier + url → same tag
 ├─ from search_literature result → url present, not in library → "[Title](url)"
 └─ model knowledge / no url → "(not in Knowledge Library)" + needs-verification label
```

## 5. Components & Boundaries

- `agents/behavior_instructions.py` — owns `CITATION_PROVENANCE_RULE` and `data_tier_label`. One responsibility: shared agent-behavior text/helpers. Both agents depend on it; it depends on nothing in the agents.
- `agents/tutor_agent.py`, `agents/research_agent.py` — consume the constant by appending it to `prompt_parts`. No other change.
- `db/grouping_store.py` — adds two fields to the bundle paper dicts. Pure serialization change.

## 6. Error Handling / Edge Cases

- Missing/unknown `data_tier` → `metadata` (helper fallback); never crash.
- Library paper with no URL → tag is level-only (URL is not required for library papers).
- Non-library paper with no URL → `(not in Knowledge Library)`; no fabricated link.
- The rule explicitly forbids asserting library status/level absent from tool results or context, preserving existing anti-fabrication guarantees.

## 7. Testing (contracts → failing tests → implementation, per CLAUDE.md)

### 7.1 Automated (unit)
- `data_tier_label`: `metadata`→`metadata`, `abstract`→`abstract`, `full_text`→`full text`, unknown/None→`metadata`.
- Prompt wiring: NeuroTutor system prompt contains `CITATION_PROVENANCE_RULE`; NeuroResearch system prompt contains `CITATION_PROVENANCE_RULE` (guards both agents against drift). Assert via the constructed prompt / `prompt_parts`.
- `grouping_store.get_grouping_bundle`: returned paper dicts include `data_tier` and `url` with the paper's values (fixture with a known `data_tier` and `url`).

### 7.2 Manual gate
Add a short section to `docs/testsPlans/manualTestPlan_literature_search_providers.md` (or a focused new plan) with the mandatory `uv run pytest tests/ -q` prerequisite first, then:
- Tutor cites a Knowledge Library paper → shows `(Knowledge Library · <level>)` with the correct level.
- Tutor cites a `search_literature` result → shows a Markdown link to the URL, no false library tag.
- Research agent shows the same behavior (common rule).

## 8. Project-State Sync
- If a new manual plan file is created, register it in `docs/projectStatus.md` (source-document + active-test-plan rules). If the existing literature manual plan is extended instead, no new reference row is needed; update active focus if it changes.

## 9. Open Questions
None.
