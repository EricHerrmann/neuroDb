# Source-Provenance Citations Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make NeuroTutor and NeuroResearch tag every paper citation with its provenance — `(Knowledge Library · <level>)` for library papers, or a Markdown URL link for non-library results.

**Architecture:** A shared constant `CITATION_PROVENANCE_RULE` (and a `data_tier_label` mapping helper) in `agents/behavior_instructions.py` is appended to both agents' system prompts. The topic/grouping bundle serialization gains `data_tier` + `url` so library papers cited from local context carry their level and link. No schema/migration change.

**Tech Stack:** Python, SQLAlchemy ORM over DuckDB/SQLite, pytest.

## Global Constraints

- Level mapping: `data_tier` values `metadata` / `abstract` / `full_text` render as `metadata` / `abstract` / `full text`. Unknown/empty → `metadata`.
- Library tag format: `(Knowledge Library · <level>)` (middle dot `·`, U+00B7). Non-library: Markdown link `[Title](url)`. Neither: `(not in Knowledge Library)`.
- The rule must never let the model assert a library status/level not present in a tool result or local context (preserve existing anti-fabrication guarantees).
- Scope: NeuroTutor + NeuroResearch only. No UI/React, no schema, no migration.
- The constant is defined once and imported by both agents (DRY).

## File Structure

- Modify `src/neurodb/agents/behavior_instructions.py` — add `CITATION_PROVENANCE_RULE` constant + `data_tier_label()` helper.
- Modify `src/neurodb/agents/tutor_agent.py` — append the constant in `_build_system_prompt`.
- Modify `src/neurodb/agents/research_agent.py` — append the constant in `_build_system_prompt`.
- Modify `src/neurodb/db/grouping_store.py` — add `data_tier` + `url` to bundle paper dicts.
- Modify `docs/testsPlans/manualTestPlan_literature_search_providers.md` — add a citation-rendering manual section.
- Tests: `tests/unit/test_behavior_instructions.py` (new), `tests/unit/test_tutor_agent.py`, `tests/unit/test_research_agent.py`, `tests/unit/test_grouping_store.py` (new or existing).

---

### Task 1: Shared constant + level-mapping helper

**Files:**
- Modify: `src/neurodb/agents/behavior_instructions.py`
- Test: `tests/unit/test_behavior_instructions.py` (create)

**Interfaces:**
- Consumes: nothing.
- Produces: `CITATION_PROVENANCE_RULE: str`; `data_tier_label(data_tier: str | None) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_behavior_instructions.py
from neurodb.agents.behavior_instructions import (
    CITATION_PROVENANCE_RULE,
    data_tier_label,
)


def test_data_tier_label_maps_known_values():
    assert data_tier_label("metadata") == "metadata"
    assert data_tier_label("abstract") == "abstract"
    assert data_tier_label("full_text") == "full text"


def test_data_tier_label_falls_back_to_metadata():
    assert data_tier_label(None) == "metadata"
    assert data_tier_label("") == "metadata"
    assert data_tier_label("weird") == "metadata"
    assert data_tier_label(" Full_Text ") == "full text"


def test_citation_rule_mentions_key_elements():
    text = CITATION_PROVENANCE_RULE
    assert "Knowledge Library" in text
    assert "full text" in text
    # non-library papers get a URL link
    assert "URL" in text or "url" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_behavior_instructions.py -q --no-cov`
Expected: FAIL — `ImportError: cannot import name 'CITATION_PROVENANCE_RULE'`.

- [ ] **Step 3: Write minimal implementation**

Append to `src/neurodb/agents/behavior_instructions.py` (after the existing code):

```python
CITATION_PROVENANCE_RULE = (
    "When you cite a specific paper, mark its source provenance inline, right "
    "after the paper. If the paper came from a Knowledge Library result (a "
    "search_knowledge_library result, or a paper in the provided local/topic "
    "context), append '(Knowledge Library · <level>)', where <level> is that "
    "result's data_tier rendered as 'metadata', 'abstract', or 'full text'. If "
    "the paper is not in the Knowledge Library (for example a search_literature "
    "result), instead link it with its URL using Markdown, e.g. "
    "[Title](https://example.org). If a cited paper is neither in the Knowledge "
    "Library nor has a URL, write '(not in Knowledge Library)' and apply the "
    "usual model-knowledge / needs-verification labeling. Never state a Knowledge "
    "Library status or level that did not come from a tool result or the provided "
    "local context."
)

_DATA_TIER_LABELS = {
    "metadata": "metadata",
    "abstract": "abstract",
    "full_text": "full text",
}


def data_tier_label(data_tier: str | None) -> str:
    """Map a stored Paper.data_tier to a human citation level."""
    return _DATA_TIER_LABELS.get((data_tier or "").strip().lower(), "metadata")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_behavior_instructions.py -q --no-cov`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/behavior_instructions.py tests/unit/test_behavior_instructions.py
git commit -m "feat(agents): shared citation-provenance rule + data_tier label helper"
```

---

### Task 2: Wire the rule into both agent prompts

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py:284-291` (`_build_system_prompt`)
- Modify: `src/neurodb/agents/research_agent.py:473-484` (`_build_system_prompt`)
- Test: `tests/unit/test_tutor_agent.py`, `tests/unit/test_research_agent.py`

**Interfaces:**
- Consumes: `CITATION_PROVENANCE_RULE` (Task 1).
- Produces: both agents' `_build_system_prompt()` output contains the rule.

- [ ] **Step 1: Write the failing tests**

Add to `tests/unit/test_tutor_agent.py` (uses the existing `_agent()` helper):

```python
def test_tutor_prompt_includes_citation_provenance_rule():
    from neurodb.agents.behavior_instructions import CITATION_PROVENANCE_RULE
    prompt = _agent()._build_system_prompt()
    assert CITATION_PROVENANCE_RULE in prompt
```

Add to `tests/unit/test_research_agent.py` (uses the existing `_agent()` helper):

```python
def test_research_prompt_includes_citation_provenance_rule():
    from neurodb.agents.behavior_instructions import CITATION_PROVENANCE_RULE
    prompt = _agent()._build_system_prompt()
    assert CITATION_PROVENANCE_RULE in prompt
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_tutor_agent.py::test_tutor_prompt_includes_citation_provenance_rule tests/unit/test_research_agent.py::test_research_prompt_includes_citation_provenance_rule -q --no-cov`
Expected: FAIL — assertion error (rule not in prompt).

- [ ] **Step 3: Write minimal implementation**

In `src/neurodb/agents/tutor_agent.py`, update the import and `_build_system_prompt`:

Change the existing import line
```python
from neurodb.agents.behavior_instructions import load_agent_behavior_instructions
```
to
```python
from neurodb.agents.behavior_instructions import (
    CITATION_PROVENANCE_RULE,
    load_agent_behavior_instructions,
)
```

Then in `_build_system_prompt`, add the rule to `prompt_parts` (after the behavior block, before context rules):

```python
    def _build_system_prompt(self) -> str:
        prompt_parts = [_TUTOR_SYSTEM_PROMPT]
        behavior_instructions = load_agent_behavior_instructions()
        if behavior_instructions:
            prompt_parts.append(behavior_instructions)
        prompt_parts.append(CITATION_PROVENANCE_RULE)
        prompt_parts.append(_context_prompt_rules(self._context_mode))
        prompt_parts.append(TEMPORAL_DISCLOSURE_RULES)
        system = "\n\n".join(prompt_parts)
        if self._context_bundle and self._context_bundle.get("prompt_block"):
            system = f"{system}\n\n{self._context_bundle['prompt_block']}"
        if self.prior_context:
            system = f"{system}\n\n{self.prior_context}"
        return system
```

In `src/neurodb/agents/research_agent.py`, update the import line
```python
from neurodb.agents.behavior_instructions import load_agent_behavior_instructions
```
to
```python
from neurodb.agents.behavior_instructions import (
    CITATION_PROVENANCE_RULE,
    load_agent_behavior_instructions,
)
```

Then in `_build_system_prompt`, add the rule to the `prompt_parts.extend([...])` list:

```python
        prompt_parts.extend([
            CITATION_PROVENANCE_RULE,
            _context_prompt_rules(self._context_mode),
            TEMPORAL_DISCLOSURE_RULES,
            f"Current date: {current_date}",
        ])
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_tutor_agent.py tests/unit/test_research_agent.py -q --no-cov`
Expected: PASS (new tests pass; existing prompt tests unaffected).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py src/neurodb/agents/research_agent.py tests/unit/test_tutor_agent.py tests/unit/test_research_agent.py
git commit -m "feat(agents): inject citation-provenance rule into tutor + research prompts"
```

---

### Task 3: Add data_tier + url to grouping bundle papers

**Files:**
- Modify: `src/neurodb/db/grouping_store.py:300-310` (bundle paper dicts)
- Test: `tests/unit/test_grouping_store.py` (create)

**Interfaces:**
- Consumes: nothing new.
- Produces: `get_grouping_bundle()` paper dicts include `data_tier` and `url`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_grouping_store.py
from datetime import datetime, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.db.grouping_store import get_grouping_bundle
from neurodb.schema import Base, Grouping, GroupingLink, Paper


def _engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_bundle_papers_include_data_tier_and_url():
    engine = _engine()
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as s:
        grouping = Grouping(name="LTP", type="topic", description="d", created_at=now)
        s.add(grouping)
        s.flush()
        paper = Paper(
            title="LTP paper", normalized_title="ltp paper", source_type="paper",
            topic_context="ctx", status="approved", queued_at=now,
            data_tier="full_text", currency_status="current",
            url="https://doi.org/10.1/ltp",
        )
        s.add(paper)
        s.flush()
        s.add(GroupingLink(
            grouping_id=grouping.id, anchor_type="paper", anchor_id=paper.id,
            status="confirmed", created_at=now,
        ))
        s.commit()
        gid = grouping.id

    with Session(engine) as s:
        bundle = get_grouping_bundle(s, gid)

    assert len(bundle["papers"]) == 1
    p = bundle["papers"][0]
    assert p["data_tier"] == "full_text"
    assert p["url"] == "https://doi.org/10.1/ltp"
    # existing fields preserved
    assert p["title"] == "LTP paper"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_store.py -q --no-cov`
Expected: FAIL — `KeyError: 'data_tier'`.

- [ ] **Step 3: Write minimal implementation**

In `src/neurodb/db/grouping_store.py`, change the bundle paper dict (lines ~300-310) to:

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

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_grouping_store.py -q --no-cov`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_store.py tests/unit/test_grouping_store.py
git commit -m "feat(db): expose data_tier + url on grouping bundle papers"
```

---

### Task 4: Manual gate + full suite

**Files:**
- Modify: `docs/testsPlans/manualTestPlan_literature_search_providers.md`

**Interfaces:**
- Consumes: nothing.
- Produces: a manual citation-rendering check.

- [ ] **Step 1: Add the manual section**

Append to `docs/testsPlans/manualTestPlan_literature_search_providers.md` before the `## Pass/Fail` section:

```markdown
### Step 4 — Citation provenance (NeuroTutor + NeuroResearch)
With the workbench running (see Environment setup):
1. Ask the tutor a topic question that pulls from the Knowledge Library, e.g.
   "What does our library say about long-term potentiation?"
   - Pass: each cited library paper shows `(Knowledge Library · <level>)` with a
     plausible level (metadata / abstract / full text); no `WARN`/JSON in the answer.
2. Ask the tutor to "search the literature for synaptic plasticity LTP".
   - Pass: cited live-search papers render as Markdown links to their URL, with no
     false `(Knowledge Library …)` tag on papers not in the library.
3. Repeat step 1 in a NeuroResearch chat.
   - Pass: same provenance behavior (the rule is shared across both agents).
```

- [ ] **Step 2: Run the full suite**

Run (with the API server stopped so the DuckDB lock is free): `uv run pytest tests/ -q`
Expected: no new failures beyond those tracked in `docs/testLog.md` (the 5 `test_model_config` failures are already fixed on main; the `test_api_app_factory` lock error only appears if a server is running).

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_literature_search_providers.md
git commit -m "docs(agents): manual gate for citation-provenance rendering"
```

---

## Self-Review

**Spec coverage:**
- §2.1 inline tag formats (library level / non-library URL / neither) → Task 1 (rule text) + Task 4 (manual verification).
- §2.2 common to both agents → Task 2.
- §2.3 no asserting unverified status → encoded in `CITATION_PROVENANCE_RULE` (Task 1), asserted present in both prompts (Task 2).
- §4.1 shared code constant in behavior_instructions.py → Task 1.
- §4.2 rule text → Task 1.
- §4.3 `data_tier_label` mapping helper → Task 1.
- §4.4 grouping bundle `data_tier` + `url` → Task 3.
- §7.1 unit tests (mapping, both-agent prompt wiring, bundle fields) → Tasks 1–3.
- §7.2 manual gate → Task 4.
- §8 projectStatus sync → the manual plan already exists in `projectStatus.md`; this only extends it (no new reference row). Active focus may be updated when the manual gate is run/signed off.

**Placeholder scan:** none — every code/test step shows full content.

**Type consistency:** `CITATION_PROVENANCE_RULE` (str) and `data_tier_label(data_tier: str | None) -> str` are named identically across Tasks 1–2; bundle keys `data_tier`/`url` consistent between Task 3 code and test; `data_tier` values (`metadata`/`abstract`/`full_text`) match the mapping in Task 1.

## Execution Handoff

After saving, offer execution choice (subagent-driven vs inline).
