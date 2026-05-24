# Memory Refocus Completion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Status:** Complete - implementation finished and manual T1-T5 signed off 2026-05-24
**Manual test plan:** `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md`

**Goal:** Fix the study log outer-join bug, add context budgets + retrieval telemetry, complete TOML task-type entries, and surface dataset usefulness state in agent context.

**Architecture:** Five independent work streams unified by execution order (highest blast radius first): (1) study log correctness in `study.py`, (2) context budgets wired through TOML → `model_config.py` → `context_orchestrator.py`, (3) retrieval telemetry via schema migration + `model_telemetry.py` + `base.py` + CLI, (4) TOML task-type entries (config-only), (5) dataset usefulness in orchestrator + agent prompts + `context_summary_event`.

**Tech Stack:** Python, SQLAlchemy ORM 2.0, DuckDB (runtime) + SQLite (tests), FastAPI, TOML config.

---

## File Map

| File | Change |
|------|--------|
| `src/neurodb/study.py` | `list_tags`, `search_tags`: outerjoin + anchor resolution |
| `neurodb_models.toml` | `[context_budgets.*]` sections + 4 new `[tasks.*]` entries |
| `src/neurodb/config/model_config.py` | `get_context_budget()` function + `ContextBudget` TypedDict |
| `src/neurodb/agents/context_orchestrator.py` | Apply budget limits; include `usefulness_state`; `dataset_usefulness` in `context_summary_event` |
| `src/neurodb/schema.py` | 5 new nullable columns on `ModelCallLog` |
| `src/neurodb/db.py` | Migration 015 |
| `src/neurodb/model_telemetry.py` | Accept context counts in `build_model_call_log` |
| `src/neurodb/agents/base.py` | Pass context counts to `_record_model_call` |
| `src/neurodb/cli/telemetry.py` | Context Usage section |
| `src/neurodb/agents/tutor_agent.py` | Usefulness-aware dataset prompt directive |
| `src/neurodb/agents/research_agent.py` | Usefulness-aware evidence grounding directive |
| `tests/unit/test_study_notes.py` | Tests for outer-join anchor resolution |
| `tests/unit/test_model_config.py` | Tests for `get_context_budget` |
| `tests/unit/test_context_orchestrator.py` | Tests for budget capping + `dataset_usefulness` |
| `tests/unit/test_telemetry.py` | Tests for context count persistence |
| `tests/unit/test_telemetry_cli.py` | Tests for Context Usage section |

---

## Task 1: LOG-059 — Study Log Outer Join Fix

**Files:**
- Modify: `src/neurodb/study.py`
- Modify: `tests/unit/test_study_notes.py`

### Background

`list_tags()` and `search_tags()` both use `.join(DatasetIndex, ...)` (INNER JOIN). `StudyNote.index_id` is nullable since Phase 2 — notes anchored to `topic_id`, `concept_id`, or `paper_id` have `index_id = NULL` and are silently excluded.

Anchor resolution precedence: `index_id` → `topic_id` → `concept_id` → `paper_id`.

| Anchor | `source` | `source_id` |
|--------|----------|-------------|
| `index_id` set | `datasets_index.source` | `datasets_index.source_id` |
| `topic_id` set | `"topic"` | `topics.name` |
| `concept_id` set | `"concept"` | `concepts.name` |
| `paper_id` set | `"paper"` | `papers.doi` or `papers.title[:50]` |
| none | `"note"` | `""` |

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_study_notes.py`:

```python
import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, DatasetIndex, IngestRun, Paper, StudyNote, Topic
from neurodb.study import list_tags, search_tags


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def _make_dataset(session):
    run = IngestRun(source="openneuro", run_at=_now(), version="1")
    session.add(run)
    session.flush()
    idx = DatasetIndex(source="openneuro", source_id="ds1", run_id=run.id)
    session.add(idx)
    session.flush()
    return idx


def test_list_tags_includes_topic_anchored_note(engine):
    with Session(engine) as s:
        topic = Topic(name="LTP", status="active", created_at=_now(), updated_at=_now())
        s.add(topic)
        s.flush()
        s.add(StudyNote(topic_id=topic.id, concept_tag="potentiation", tagged_at=_now()))
        s.commit()

    with Session(engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "topic"
    assert results[0]["source_id"] == "LTP"
    assert results[0]["concept_tag"] == "potentiation"


def test_list_tags_includes_concept_anchored_note(engine):
    with Session(engine) as s:
        concept = Concept(name="synaptic pruning", status="active",
                          created_at=_now(), updated_at=_now())
        s.add(concept)
        s.flush()
        s.add(StudyNote(concept_id=concept.id, concept_tag="pruning", tagged_at=_now()))
        s.commit()

    with Session(engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "concept"
    assert results[0]["source_id"] == "synaptic pruning"


def test_list_tags_includes_paper_anchored_note(engine):
    with Session(engine) as s:
        paper = Paper(title="LTP Review", normalized_title="ltp review",
                      doi="10.test/ltp", source_type="paper",
                      topic_context="plasticity", status="pending", queued_at=_now())
        s.add(paper)
        s.flush()
        s.add(StudyNote(paper_id=paper.id, concept_tag="LTP", tagged_at=_now()))
        s.commit()

    with Session(engine) as s:
        results = list_tags(s)
    assert len(results) == 1
    assert results[0]["source"] == "paper"
    assert results[0]["source_id"] == "10.test/ltp"


def test_list_tags_source_filter_excludes_topic_notes(engine):
    with Session(engine) as s:
        idx = _make_dataset(s)
        topic = Topic(name="LTP", status="active", created_at=_now(), updated_at=_now())
        s.add(topic)
        s.flush()
        s.add(StudyNote(index_id=idx.id, concept_tag="ds_note", tagged_at=_now()))
        s.add(StudyNote(topic_id=topic.id, concept_tag="topic_note", tagged_at=_now()))
        s.commit()

    with Session(engine) as s:
        results = list_tags(s, source="openneuro")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "ds_note"


def test_search_tags_matches_topic_anchored_note(engine):
    with Session(engine) as s:
        topic = Topic(name="plasticity", status="active",
                      created_at=_now(), updated_at=_now())
        s.add(topic)
        s.flush()
        s.add(StudyNote(topic_id=topic.id, concept_tag="LTP",
                        note_text="long-term potentiation", tagged_at=_now()))
        s.commit()

    with Session(engine) as s:
        results = search_tags(s, "potentiation")
    assert len(results) == 1
    assert results[0]["source"] == "topic"
    assert results[0]["source_id"] == "plasticity"
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_study_notes.py -v -k "topic_anchored or concept_anchored or paper_anchored or source_filter or search_tags_matches"
```

Expected: all 5 new tests fail (INNER JOIN excludes non-dataset notes).

- [ ] **Step 3: Implement the fix in `src/neurodb/study.py`**

Replace `list_tags` and `search_tags` with outer-join versions. Also add the needed imports at the top of the file.

Change the imports:
```python
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from neurodb.schema import Concept, DatasetIndex, Paper, StudyNote, Topic
```

Replace `list_tags`:
```python
def list_tags(
    session: Session,
    concept: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Return study notes with dataset info, optionally filtered.

    concept: substring match against concept_tag (case-insensitive)
    source: exact match against resolved source string
    """
    rows = session.execute(
        select(StudyNote, DatasetIndex, Topic, Concept, Paper)
        .outerjoin(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .outerjoin(Topic, Topic.id == StudyNote.topic_id)
        .outerjoin(Concept, Concept.id == StudyNote.concept_id)
        .outerjoin(Paper, Paper.id == StudyNote.paper_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note = row.StudyNote
        idx = row.DatasetIndex
        topic = row.Topic
        concept_obj = row.Concept
        paper = row.Paper
        resolved_source, resolved_source_id = _resolve_anchor(
            idx, topic, concept_obj, paper
        )
        if concept and concept.lower() not in note.concept_tag.lower():
            continue
        if source and source != resolved_source:
            continue
        results.append({
            "id": note.id,
            "source": resolved_source,
            "source_id": resolved_source_id,
            "concept_tag": note.concept_tag,
            "section_ref": note.section_ref,
            "note_text": note.note_text,
            "tagged_at": note.tagged_at,
        })
    return results
```

Replace `search_tags`:
```python
def search_tags(session: Session, keyword: str) -> list[dict]:
    """Return notes where keyword appears in concept_tag, note_text, or section_ref."""
    kw = keyword.lower()
    rows = session.execute(
        select(StudyNote, DatasetIndex, Topic, Concept, Paper)
        .outerjoin(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .outerjoin(Topic, Topic.id == StudyNote.topic_id)
        .outerjoin(Concept, Concept.id == StudyNote.concept_id)
        .outerjoin(Paper, Paper.id == StudyNote.paper_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note = row.StudyNote
        idx = row.DatasetIndex
        topic = row.Topic
        concept_obj = row.Concept
        paper = row.Paper
        in_concept = kw in note.concept_tag.lower()
        in_note = note.note_text and kw in note.note_text.lower()
        in_section = note.section_ref and kw in note.section_ref.lower()
        if in_concept or in_note or in_section:
            resolved_source, resolved_source_id = _resolve_anchor(
                idx, topic, concept_obj, paper
            )
            results.append({
                "source": resolved_source,
                "source_id": resolved_source_id,
                "concept_tag": note.concept_tag,
                "section_ref": note.section_ref,
                "note_text": note.note_text,
                "tagged_at": note.tagged_at,
            })
    return results
```

Add the `_resolve_anchor` helper (place before `list_tags`):
```python
def _resolve_anchor(
    idx: DatasetIndex | None,
    topic: "Topic | None",
    concept: "Concept | None",
    paper: "Paper | None",
) -> tuple[str, str]:
    """Return (source, source_id) for a study note based on which anchor is set."""
    if idx is not None:
        return idx.source, idx.source_id
    if topic is not None:
        return "topic", topic.name
    if concept is not None:
        return "concept", concept.name
    if paper is not None:
        source_id = paper.doi if paper.doi else (paper.title or "")[:50]
        return "paper", source_id
    return "note", ""
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_study_notes.py -v
```

Expected: all tests pass including the 5 new ones.

- [ ] **Step 5: Run the full suite to check for regressions**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/ -q
```

Expected: no new failures beyond those tracked in `docs/testLog.md`.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/study.py tests/unit/test_study_notes.py
git commit -m "fix(LOG-059): outerjoin study log — include topic/concept/paper-anchored notes"
```

---

## Task 2: Context Budgets — TOML + Config

**Files:**
- Modify: `neurodb_models.toml`
- Modify: `src/neurodb/config/model_config.py`
- Modify: `tests/unit/test_model_config.py`

### Background

`ContextRequest` already has `max_papers`, `max_claims`, `max_notes`, `max_datasets` fields. Budget wiring means: read limits from TOML per mode, pass them into `build_context_bundle()` via those existing fields in `ContextRequest`. The orchestrator already passes them down as `limit=` to retrieval calls (Task 3 will verify this). This task only adds the TOML section and the config reader.

- [ ] **Step 1: Write failing tests**

Add to `tests/unit/test_model_config.py`:

```python
from neurodb.config.model_config import get_context_budget


def test_get_context_budget_returns_grounded_limits(tmp_path, monkeypatch):
    toml_content = b"""
[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("grounded")
    assert budget["papers"] == 10
    assert budget["notes"] == 15
    assert budget["claims"] == 12
    assert budget["datasets"] == 5


def test_get_context_budget_returns_none_when_section_absent(tmp_path, monkeypatch):
    toml_content = b"""
[routing]
economy = "anthropic"
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("grounded")
    assert budget is None


def test_get_context_budget_returns_none_for_unconfigured_mode(tmp_path, monkeypatch):
    toml_content = b"""
[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
"""
    toml_file = tmp_path / "neurodb_models.toml"
    toml_file.write_bytes(toml_content)

    import neurodb.config.model_config as mod
    monkeypatch.setattr(mod, "_CONFIG_PATH", toml_file)
    monkeypatch.setattr(mod, "_cache", None)

    budget = get_context_budget("general")
    assert budget is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_model_config.py -v -k "context_budget"
```

Expected: `ImportError` or `AttributeError` — `get_context_budget` does not exist yet.

- [ ] **Step 3: Add `[context_budgets]` to `neurodb_models.toml`**

Append to the bottom of `neurodb_models.toml`:

```toml
[context_budgets.general]
papers = 2
notes = 3
claims = 3
datasets = 1

[context_budgets.contextual]
papers = 5
notes = 8
claims = 6
datasets = 3

[context_budgets.grounded]
papers = 10
notes = 15
claims = 12
datasets = 5
```

- [ ] **Step 4: Add `get_context_budget` to `src/neurodb/config/model_config.py`**

Add this function after `get_provider_fallback_order`:

```python
class ContextBudget(TypedDict):
    papers: int
    notes: int
    claims: int
    datasets: int
```

Add `from typing import TypedDict` to the imports at the top of the file.

Add the function:

```python
def get_context_budget(mode: str) -> "ContextBudget | None":
    """Return per-category item limits for the given context mode, or None if unconfigured."""
    config = load_model_config()
    budgets = config.get("context_budgets", {})
    mode_cfg = budgets.get(mode)
    if mode_cfg is None:
        return None
    return {
        "papers": int(mode_cfg["papers"]),
        "notes": int(mode_cfg["notes"]),
        "claims": int(mode_cfg["claims"]),
        "datasets": int(mode_cfg["datasets"]),
    }
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_model_config.py -v
```

Expected: all tests pass including the 3 new ones.

- [ ] **Step 6: Commit**

```bash
git add neurodb_models.toml src/neurodb/config/model_config.py tests/unit/test_model_config.py
git commit -m "feat: add context_budgets TOML config and get_context_budget helper"
```

---

## Task 3: Context Budget Wiring in Orchestrator

**Files:**
- Modify: `src/neurodb/agents/context_orchestrator.py`
- Modify: `tests/unit/test_context_orchestrator.py`

### Background

`ContextRequest` already has `max_papers`, `max_claims`, `max_notes`, `max_datasets`. Look at how topic_bundle and question_bundle are built — check if those getters accept limit params, or if the cap must be applied post-retrieval.

Check `get_topic_bundle` and `get_question_bundle` signatures to see if they accept limits. If they do not, apply the cap by slicing lists after retrieval. The budget from `get_context_budget(mode)` maps to `ContextRequest` fields: `papers → max_papers`, `notes → max_notes`, `claims → max_claims`, `datasets → max_datasets`.

`build_context_bundle` should: (1) call `get_context_budget(mode)` when no max_* fields are supplied in the request; (2) pass max_* through to retrieval. The existing request max_* fields take precedence over TOML budget (explicit request wins).

- [ ] **Step 1: Check whether topic/claim bundle getters accept limit params**

```bash
grep -n "def get_topic_bundle\|def get_question_bundle" \
  /home/oldha/projects/neuroDb/src/neurodb/db/topic_store.py \
  /home/oldha/projects/neuroDb/src/neurodb/db/claim_store.py
```

If they don't accept limits, the cap will be applied by slicing lists in `build_context_bundle` after retrieval. Read the return structures to identify which list keys to cap.

- [ ] **Step 2: Write failing test**

Add to `tests/unit/test_context_orchestrator.py`:

```python
from neurodb.agents.context_orchestrator import build_context_bundle, ContextRequest


def test_build_context_bundle_respects_max_datasets(engine):
    # seed two dataset packets via topic
    with Session(engine) as session:
        now = datetime.now(UTC).isoformat()
        topic = get_or_create_topic(session, "multi dataset topic", "test")
        from neurodb.schema import IngestRun, DatasetIndex, DatasetResearchPacket
        for i in range(3):
            run = IngestRun(source="openneuro", run_at=now, version="1")
            session.add(run)
            session.flush()
            idx = DatasetIndex(source="openneuro", source_id=f"ds{i}", run_id=run.id)
            session.add(idx)
            session.flush()
            pkt = DatasetResearchPacket(
                index_id=idx.id,
                usefulness_state="sparse",
                created_at=now, updated_at=now,
            )
            session.add(pkt)
            session.flush()
            from neurodb.db.topic_store import link_dataset_topic
            link_dataset_topic(session, idx.id, topic.id)
        session.commit()
        topic_id = topic.id

    request: ContextRequest = {
        "mode": "grounded",
        "agent_mode": "neuro_tutor",
        "user_message": "multi dataset topic",
        "active_focus": {"focus_type": "topic", "focus_id": topic_id},
        "max_datasets": 1,
    }
    bundle = build_context_bundle(engine, request=request)
    tb = bundle.get("topic_bundle") or {}
    packets = tb.get("dataset_packets", [])
    assert len(packets) <= 1
```

Note: if `link_dataset_topic` does not exist in topic_store, find the correct function name with `grep -n "def link_dataset" src/neurodb/db/topic_store.py` and adjust.

- [ ] **Step 3: Run test to verify it fails**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_context_orchestrator.py -v -k "max_datasets"
```

Expected: FAIL — no capping is applied yet.

- [ ] **Step 4: Wire budget into `build_context_bundle`**

In `src/neurodb/agents/context_orchestrator.py`, add import at top:

```python
from neurodb.config.model_config import get_context_budget
```

In `build_context_bundle`, after `mode = normalize_context_mode(request.get("mode"))`, add budget resolution:

```python
# Apply context budget: explicit request fields win; fall back to TOML budget.
_budget = get_context_budget(mode) or {}
max_papers = request.get("max_papers") or _budget.get("papers")
max_notes = request.get("max_notes") or _budget.get("notes")
max_claims = request.get("max_claims") or _budget.get("claims")
max_datasets = request.get("max_datasets") or _budget.get("datasets")
```

After `topic_bundle` or `question_bundle` is assigned, add slicing (within the `with Session(engine)` block, after the bundle is set):

```python
# Cap retrieval counts to budget limits.
if topic_bundle and max_datasets is not None:
    topic_bundle = dict(topic_bundle)
    topic_bundle["dataset_packets"] = topic_bundle.get("dataset_packets", [])[:max_datasets]
if topic_bundle and max_papers is not None:
    topic_bundle = dict(topic_bundle)
    topic_bundle["papers"] = topic_bundle.get("papers", [])[:max_papers]
if topic_bundle and max_notes is not None:
    topic_bundle = dict(topic_bundle)
    topic_bundle["study_notes"] = topic_bundle.get("study_notes", [])[:max_notes]
if topic_bundle and max_claims is not None:
    topic_bundle = dict(topic_bundle)
    topic_bundle["claims"] = topic_bundle.get("claims", [])[:max_claims]
if question_bundle and max_datasets is not None:
    question_bundle = dict(question_bundle)
    question_bundle["dataset_packets"] = question_bundle.get("dataset_packets", [])[:max_datasets]
if question_bundle and max_papers is not None:
    question_bundle = dict(question_bundle)
    question_bundle["papers"] = question_bundle.get("papers", [])[:max_papers]
if question_bundle and max_notes is not None:
    question_bundle = dict(question_bundle)
    question_bundle["study_notes"] = question_bundle.get("study_notes", [])[:max_notes]
if question_bundle and max_claims is not None:
    question_bundle = dict(question_bundle)
    question_bundle["claims"] = question_bundle.get("claims", [])[:max_claims]
```

Check topic_bundle and question_bundle key names against `get_topic_bundle` and `get_question_bundle` return values before committing. Adjust key names to match what those functions actually return.

- [ ] **Step 5: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_context_orchestrator.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/agents/context_orchestrator.py \
        src/neurodb/config/model_config.py \
        tests/unit/test_context_orchestrator.py
git commit -m "feat: wire context budget limits into build_context_bundle"
```

---

## Task 4: Retrieval Telemetry — Schema + Migration

**Files:**
- Modify: `src/neurodb/schema.py`
- Modify: `src/neurodb/db.py`
- Modify: `tests/unit/test_telemetry.py`

### Background

Five new nullable integer columns on `model_call_log`: `context_papers_count`, `context_notes_count`, `context_claims_count`, `context_datasets_count`, `context_gap_count`. Migration 015 uses the `try/except` pattern (not `IF NOT EXISTS`). Existing rows have NULL — no backfill needed.

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_telemetry.py`:

```python
from neurodb.schema import Base, ModelCallLog
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session


def test_model_call_log_has_context_count_columns():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    col_names = {c["name"] for c in inspect(engine).get_columns("model_call_log")}
    assert "context_papers_count" in col_names
    assert "context_notes_count" in col_names
    assert "context_claims_count" in col_names
    assert "context_datasets_count" in col_names
    assert "context_gap_count" in col_names


def test_model_call_log_context_counts_nullable():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = ModelCallLog(
            recorded_at="2026-05-23T00:00:00+00:00",
            task_type="agent.loop.neuro_tutor",
            provider="anthropic",
            model="claude-sonnet-4-6",
        )
        session.add(row)
        session.commit()
    with Session(engine) as session:
        row = session.query(ModelCallLog).first()
        assert row.context_papers_count is None
        assert row.context_notes_count is None
        assert row.context_claims_count is None
        assert row.context_datasets_count is None
        assert row.context_gap_count is None


def test_model_call_log_context_counts_persist_when_set():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        row = ModelCallLog(
            recorded_at="2026-05-23T00:00:00+00:00",
            task_type="agent.loop.neuro_research",
            provider="anthropic",
            model="claude-sonnet-4-6",
            context_papers_count=5,
            context_notes_count=8,
            context_claims_count=4,
            context_datasets_count=2,
            context_gap_count=1,
        )
        session.add(row)
        session.commit()
    with Session(engine) as session:
        row = session.query(ModelCallLog).first()
        assert row.context_papers_count == 5
        assert row.context_notes_count == 8
        assert row.context_claims_count == 4
        assert row.context_datasets_count == 2
        assert row.context_gap_count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry.py -v -k "context_count"
```

Expected: FAIL — columns do not exist on the ORM class yet.

- [ ] **Step 3: Add 5 columns to `ModelCallLog` in `schema.py`**

After `estimated_cost_usd` in the `ModelCallLog` class:

```python
context_papers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
context_notes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
context_claims_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
context_datasets_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
context_gap_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

- [ ] **Step 4: Add migration 015 in `db.py`**

Add this function before `_MIGRATIONS`:

```python
def _migration_015_model_call_log_context_counts(conn) -> None:
    """Add retrieval telemetry columns to model_call_log."""
    for col in (
        "context_papers_count",
        "context_notes_count",
        "context_claims_count",
        "context_datasets_count",
        "context_gap_count",
    ):
        try:
            conn.execute(text(f"ALTER TABLE model_call_log ADD COLUMN {col} INTEGER"))
        except Exception:
            pass  # column already exists
```

Add to `_MIGRATIONS`:

```python
15: _migration_015_model_call_log_context_counts,
```

- [ ] **Step 5: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py tests/unit/test_telemetry.py
git commit -m "feat: add context count columns to model_call_log (migration 015)"
```

---

## Task 5: Retrieval Telemetry — Population

**Files:**
- Modify: `src/neurodb/model_telemetry.py`
- Modify: `src/neurodb/agents/base.py`
- Modify: `tests/unit/test_telemetry.py`

### Background

`build_model_call_log` needs 5 new optional keyword args. `_record_model_call` in `base.py` needs to extract context counts from `self._context_bundle` and pass them through. Context counts come from `bundle["source_counts"]`: `papers → context_papers_count`, `study_notes → context_notes_count`, `claims → context_claims_count`, `dataset_packets → context_datasets_count`, `gaps → context_gap_count`.

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_telemetry.py`:

```python
from neurodb.model_telemetry import build_model_call_log


def test_build_model_call_log_accepts_context_counts():
    row = build_model_call_log(
        task_type="agent.loop.neuro_research",
        provider="anthropic",
        model="claude-sonnet-4-6",
        context_papers_count=9,
        context_notes_count=12,
        context_claims_count=8,
        context_datasets_count=3,
        context_gap_count=2,
    )
    assert row.context_papers_count == 9
    assert row.context_notes_count == 12
    assert row.context_claims_count == 8
    assert row.context_datasets_count == 3
    assert row.context_gap_count == 2


def test_build_model_call_log_context_counts_default_none():
    row = build_model_call_log(
        task_type="agent.loop.neuro_tutor",
        provider="anthropic",
        model="claude-sonnet-4-6",
    )
    assert row.context_papers_count is None
    assert row.context_gap_count is None
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry.py -v -k "accepts_context_counts or context_counts_default"
```

Expected: FAIL — `build_model_call_log` does not accept those kwargs yet.

- [ ] **Step 3: Update `build_model_call_log` in `model_telemetry.py`**

Add the 5 new kwargs to the function signature:

```python
def build_model_call_log(
    *,
    task_type: str,
    provider: str,
    model: str,
    mode: str | None = None,
    response=None,
    iteration: int | None = None,
    elapsed_ms: int | None = None,
    context_papers_count: int | None = None,
    context_notes_count: int | None = None,
    context_claims_count: int | None = None,
    context_datasets_count: int | None = None,
    context_gap_count: int | None = None,
) -> ModelCallLog:
```

Add the 5 fields to the `ModelCallLog(...)` constructor call:

```python
    return ModelCallLog(
        recorded_at=datetime.now(UTC).isoformat(),
        task_type=task_type,
        provider=provider,
        model=model,
        mode=mode,
        tool_name=tool_names[0] if tool_names else None,
        tool_names_json=json.dumps(tool_names) if tool_names else None,
        iteration=iteration,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stop_reason=_get_value(response, "stop_reason"),
        elapsed_ms=elapsed_ms,
        estimated_cost_usd=_estimate_cost_usd(model, input_tokens, output_tokens),
        context_papers_count=context_papers_count,
        context_notes_count=context_notes_count,
        context_claims_count=context_claims_count,
        context_datasets_count=context_datasets_count,
        context_gap_count=context_gap_count,
    )
```

- [ ] **Step 4: Update `_record_model_call` in `base.py`**

In `base.py`, the `_record_model_call` method should extract counts from `self._context_bundle` and pass them through. Change `_record_model_call` to:

```python
def _record_model_call(self, response, iteration: int, elapsed_ms: int) -> None:
    try:
        sc = (self._context_bundle or {}).get("source_counts") or {}
        record_model_call(
            self._engine,
            task_type=self._telemetry_task_type,
            provider=self._model_provider,
            model=self._model,
            mode=self._telemetry_mode,
            response=response,
            iteration=iteration,
            elapsed_ms=elapsed_ms,
            context_papers_count=sc.get("papers") or None,
            context_notes_count=sc.get("study_notes") or None,
            context_claims_count=sc.get("claims") or None,
            context_datasets_count=sc.get("dataset_packets") or None,
            context_gap_count=sc.get("gaps") or None,
        )
    except Exception:
        return
```

Note: `or None` converts 0 to None — context counts of 0 are treated the same as absent (no-context turns). This matches the spec: turns with no context bundle have NULL for all five fields.

- [ ] **Step 5: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry.py -v
```

Expected: all tests pass.

- [ ] **Step 6: Run full suite**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/model_telemetry.py src/neurodb/agents/base.py tests/unit/test_telemetry.py
git commit -m "feat: populate context count columns in model_call_log telemetry"
```

---

## Task 6: Retrieval Telemetry — CLI Context Usage Section

**Files:**
- Modify: `src/neurodb/cli/telemetry.py`
- Modify: `tests/unit/test_telemetry_cli.py`

### Background

Add a "Context Usage" section to `render_telemetry` output. It only appears when at least one row has non-NULL context counts. Format: `HH:MM:SS DD/MM/YY  agent_mode  mode  Np / Nn / Nc / Nd [  G gaps]`.

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_telemetry_cli.py`:

```python
def test_render_telemetry_shows_context_usage_section():
    engine = _engine()
    with Session(engine) as session:
        session.add(ModelCallLog(
            recorded_at="2026-05-23T13:45:22+00:00",
            task_type="agent.loop.neuro_research",
            provider="anthropic",
            model="claude-sonnet-4-6",
            mode="grounded",
            context_papers_count=9,
            context_notes_count=12,
            context_claims_count=8,
            context_datasets_count=3,
            context_gap_count=2,
        ))
        session.commit()

    output = render_telemetry(engine, tail=20)

    assert "Context Usage" in output
    assert "9p" in output
    assert "12n" in output
    assert "8c" in output
    assert "3d" in output
    assert "2 gaps" in output


def test_render_telemetry_omits_context_usage_when_no_counts():
    engine = _engine()
    with Session(engine) as session:
        session.add(ModelCallLog(
            recorded_at="2026-05-23T13:45:22+00:00",
            task_type="agent.loop.neuro_tutor",
            provider="anthropic",
            model="claude-sonnet-4-6",
        ))
        session.commit()

    output = render_telemetry(engine, tail=20)

    assert "Context Usage" not in output
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry_cli.py -v -k "context_usage"
```

Expected: FAIL — no Context Usage section exists yet.

- [ ] **Step 3: Add Context Usage section to `render_telemetry` and helpers**

In `render_telemetry`, add the new section:

```python
def render_telemetry(
    engine: Engine,
    *,
    tail: int = 20,
    provider: str | None = None,
    task_type: str | None = None,
    warnings_only: bool = False,
) -> str:
    sections: list[str] = []
    if not warnings_only:
        sections.append(
            _render_model_calls(engine, tail=tail, provider=provider, task_type=task_type)
        )
        context_section = _render_context_usage(engine, tail=tail)
        if context_section:
            sections.append(context_section)
    sections.append(
        _render_system_warnings(engine, tail=tail, provider=provider, task_type=task_type)
    )
    return "\n\n".join(sections)
```

Add the helper function `_render_context_usage` and `_query_context_usage`:

```python
def _render_context_usage(engine: Engine, *, tail: int) -> str | None:
    rows = _query_context_usage(engine, tail=tail)
    if not rows:
        return None
    lines = [f"Context Usage (last {tail} agent turns)", "-" * 72]
    for row in rows:
        p = row.context_papers_count or 0
        n = row.context_notes_count or 0
        c = row.context_claims_count or 0
        d = row.context_datasets_count or 0
        g = row.context_gap_count or 0
        counts = f"{p}p / {n}n / {c}c / {d}d"
        gap_str = f"  {g} gaps" if g else ""
        mode_str = row.mode or "unknown"
        lines.append(
            f"{format_recorded_at(row.recorded_at):17}  "
            f"{row.task_type:28}  "
            f"{mode_str:12}  "
            f"{counts}{gap_str}"
        )
    return "\n".join(lines)


def _query_context_usage(engine: Engine, *, tail: int) -> list:
    sql = text("""
        SELECT recorded_at, task_type, mode,
               context_papers_count, context_notes_count,
               context_claims_count, context_datasets_count, context_gap_count
        FROM model_call_log
        WHERE context_papers_count IS NOT NULL
           OR context_notes_count IS NOT NULL
           OR context_claims_count IS NOT NULL
           OR context_datasets_count IS NOT NULL
           OR context_gap_count IS NOT NULL
        ORDER BY recorded_at DESC
        LIMIT :limit
    """)
    try:
        with engine.connect() as conn:
            return list(conn.execute(sql, {"limit": tail}).fetchall())
    except Exception:
        return []
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_telemetry_cli.py -v
```

Expected: all tests pass.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/cli/telemetry.py tests/unit/test_telemetry_cli.py
git commit -m "feat: add Context Usage section to neurodb-telemetry CLI"
```

---

## Task 7: TOML Task-Type Defaults

**Files:**
- Modify: `neurodb_models.toml`
- Modify: `tests/unit/test_model_config.py`

### Background

Add 4 new task entries to `neurodb_models.toml`. Tier rationale: `agent.extract` is economy (format-fill from provided input); the other three require deep scientific reasoning (premium).

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_model_config.py`:

```python
def test_get_task_config_returns_agent_extract():
    tier, max_tokens = get_task_config("agent.extract")
    assert tier == "economy"
    assert max_tokens == 1024


def test_get_task_config_returns_agent_claim_review():
    tier, max_tokens = get_task_config("agent.claim_review")
    assert tier == "premium"
    assert max_tokens == 2048


def test_get_task_config_returns_agent_synthesis():
    tier, max_tokens = get_task_config("agent.synthesis")
    assert tier == "premium"
    assert max_tokens == 4096


def test_get_task_config_returns_agent_grounded_review():
    tier, max_tokens = get_task_config("agent.grounded_review")
    assert tier == "premium"
    assert max_tokens == 2048
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_model_config.py -v -k "agent_extract or agent_claim_review or agent_synthesis or agent_grounded"
```

Expected: `KeyError` — task types not defined in TOML yet.

- [ ] **Step 3: Add 4 task entries to `neurodb_models.toml`**

Append after `[tasks."research.hypothesis_review"]`:

```toml
[tasks."agent.extract"]
tier = "economy"
max_tokens = 1024

[tasks."agent.claim_review"]
tier = "premium"
max_tokens = 2048

[tasks."agent.synthesis"]
tier = "premium"
max_tokens = 4096

[tasks."agent.grounded_review"]
tier = "premium"
max_tokens = 2048
```

- [ ] **Step 4: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_model_config.py -v
```

Expected: all tests pass. Note: the monkeypatched tests from Task 2 may need `_cache` reset — they already do that via `monkeypatch.setattr(mod, "_cache", None)`.

- [ ] **Step 5: Commit**

```bash
git add neurodb_models.toml tests/unit/test_model_config.py
git commit -m "feat: add agent.extract/claim_review/synthesis/grounded_review task-type defaults"
```

---

## Task 8: Dataset Usefulness in Context Bundle + Evidence Lens

**Files:**
- Modify: `src/neurodb/agents/context_orchestrator.py`
- Modify: `src/neurodb/agents/tutor_agent.py`
- Modify: `src/neurodb/agents/research_agent.py`
- Modify: `tests/unit/test_context_orchestrator.py`

### Background

`topic_store.get_topic_bundle()` already includes `usefulness_state` in each dataset packet. The orchestrator just needs to preserve it when packaging the bundle (check it isn't stripped anywhere). The main change is adding `dataset_usefulness` to `context_summary_event`, and adding prompt directives.

`dataset_usefulness` breakdown structure:
```json
{
  "sparse": 2,
  "partial": 1,
  "research_context_ready": 1,
  "analysis_ready": 0
}
```

This field is omitted from `context_summary_event` output when no datasets were retrieved (i.e., when `source_counts["dataset_packets"] == 0`).

- [ ] **Step 1: Write failing test**

Add to `tests/unit/test_context_orchestrator.py`:

```python
def test_context_summary_event_includes_dataset_usefulness_breakdown(engine):
    """context_summary_event returns dataset_usefulness when datasets are present."""
    with Session(engine) as session:
        now = datetime.now(UTC).isoformat()
        topic = get_or_create_topic(session, "usefulness test", "test")
        from neurodb.schema import IngestRun, DatasetIndex, DatasetResearchPacket
        for state in ["sparse", "sparse", "partial", "research_context_ready"]:
            run = IngestRun(source="openneuro", run_at=now, version="1")
            session.add(run)
            session.flush()
            idx = DatasetIndex(source="openneuro",
                               source_id=f"ds_{state}_{id(run)}", run_id=run.id)
            session.add(idx)
            session.flush()
            pkt = DatasetResearchPacket(
                index_id=idx.id,
                usefulness_state=state,
                created_at=now, updated_at=now,
            )
            session.add(pkt)
            session.flush()
            from neurodb.db.topic_store import link_dataset_topic
            link_dataset_topic(session, idx.id, topic.id)
        session.commit()
        topic_id = topic.id

    request: ContextRequest = {
        "mode": "grounded",
        "agent_mode": "neuro_research",
        "user_message": "usefulness test",
        "active_focus": {"focus_type": "topic", "focus_id": topic_id},
    }
    bundle = build_context_bundle(engine, request=request)
    event = context_summary_event(bundle)

    assert event is not None
    assert "dataset_usefulness" in event
    du = event["dataset_usefulness"]
    assert du["sparse"] == 2
    assert du["partial"] == 1
    assert du["research_context_ready"] == 1
    assert du.get("analysis_ready", 0) == 0


def test_context_summary_event_omits_dataset_usefulness_when_no_datasets(engine):
    bundle = build_context_bundle(engine, request={
        "mode": "general",
        "agent_mode": "neuro_tutor",
        "user_message": "hello",
    })
    event = context_summary_event(bundle)
    # general mode with no active focus may return None or a bundle with 0 datasets
    if event is not None:
        assert "dataset_usefulness" not in event
```

- [ ] **Step 2: Run tests to verify they fail**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_context_orchestrator.py -v -k "dataset_usefulness"
```

Expected: FAIL — `dataset_usefulness` not in event output yet.

- [ ] **Step 3: Update `context_summary_event` to add `dataset_usefulness` breakdown**

In `context_orchestrator.py`, update `context_summary_event`:

```python
def context_summary_event(bundle: dict | None) -> dict | None:
    """Return the SSE context_summary event for a context bundle."""
    if not bundle:
        return None
    sc = bundle.get("source_counts", empty_source_counts())
    event: dict = {
        "type": "context_summary",
        "context_mode": bundle.get("mode", DEFAULT_CONTEXT_MODE),
        "active_focus": bundle.get("active_focus"),
        "source_counts": sc,
        "papers_count": sc.get("papers", 0),
        "notes_count": sc.get("study_notes", 0),
        "claims_count": sc.get("claims", 0),
        "datasets_count": sc.get("dataset_packets", 0),
        "gaps_count": sc.get("gaps", 0),
        "warnings": bundle.get("warnings", []),
    }
    if sc.get("dataset_packets", 0) > 0:
        event["dataset_usefulness"] = _dataset_usefulness_breakdown(bundle)
    return event


def _dataset_usefulness_breakdown(bundle: dict) -> dict:
    """Count dataset packets by usefulness_state from the bundle."""
    counts: dict[str, int] = {
        "sparse": 0,
        "partial": 0,
        "research_context_ready": 0,
        "analysis_ready": 0,
    }
    topic_bundle = bundle.get("topic_bundle") or {}
    question_bundle = bundle.get("question_bundle") or {}
    packets = (
        topic_bundle.get("dataset_packets", [])
        + question_bundle.get("dataset_packets", [])
    )
    for pkt in packets:
        state = pkt.get("usefulness_state") if isinstance(pkt, dict) else getattr(pkt, "usefulness_state", None)
        if state in counts:
            counts[state] += 1
        elif state is not None:
            counts[state] = counts.get(state, 0) + 1
    return counts
```

Note: `dataset_packets` in `topic_bundle` are the raw objects or dicts returned by `get_topic_bundle`. Check what form they take in the actual bundle before committing — if they are ORM objects, use `getattr`; if they are dicts, use `.get()`. The code above handles both.

- [ ] **Step 4: Run tests to verify they pass**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/unit/test_context_orchestrator.py -v -k "dataset_usefulness"
```

Expected: PASS.

- [ ] **Step 5: Add prompt directives to tutor and research agents**

In `tutor_agent.py`, add to `_TUTOR_SYSTEM_PROMPT` (append before the closing `)`):

```python
    "When local context includes datasets, check each dataset's usefulness state. "
    "If a dataset is 'sparse', note the evidence gap rather than presenting the record "
    "as a learning resource; suggest the user request enrichment if the topic is relevant. "
    "Treat 'research_context_ready' and 'analysis_ready' datasets as suitable learning "
    "resources and cite them with confidence. "
```

In `research_agent.py`, add to `_RESEARCH_SYSTEM_PROMPT` (append before the closing `)`):

```python
    "When local context includes datasets, treat only 'research_context_ready' or "
    "'analysis_ready' datasets as supporting evidence for claims. Label 'sparse' and "
    "'partial' datasets as insufficient for claims and record them as evidence gaps "
    "using add_gap rather than citing them as support. "
```

- [ ] **Step 6: Run full suite**

```
cd /home/oldha/projects/neuroDb && uv run pytest tests/ -q
```

Expected: no new failures.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/context_orchestrator.py \
        src/neurodb/agents/tutor_agent.py \
        src/neurodb/agents/research_agent.py \
        tests/unit/test_context_orchestrator.py
git commit -m "feat(LOG-054): surface dataset usefulness in context bundle and evidence lens"
```

---

## Task 9: Docs + Project Status Update

**Files:**
- Modify: `docs/projectStatus.md`
- Create: `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md`:

```markdown
# Manual Test Plan — Memory Refocus Completion

**Phase:** Learning and Research Memory Refocus — Completion Phase
**Status:** Complete - T1-T5 passed and signed off 2026-05-24
**Covers:** LOG-059 study log outer join, context budgets, retrieval telemetry CLI,
             dataset usefulness in agents

---

## Prerequisites

1. Run automated tests and verify no new failures:
   ```
   cd /home/oldha/projects/neuroDb && uv run pytest tests/ -q
   ```
   Pass criteria: no failures beyond those tracked in `docs/testLog.md`.

2. Start the API server:
   ```
   cd /home/oldha/projects/neuroDb && uv run uvicorn neurodb.api.app:app --reload
   ```

3. Start the frontend:
   ```
   cd /home/oldha/projects/neuroDb/frontend && npm run dev
   ```

---

## T1 — Study Log Shows Topic/Concept/Paper-Anchored Notes Under "All Sources"

**Setup:** Add a study note anchored to a topic (not a dataset) using the CLI or API.

```bash
# Add a topic-anchored note via the API
curl -s -X POST http://localhost:8000/api/study-log \
  -H "Content-Type: application/json" \
  -d '{"topic_id": 1, "concept_tag": "LTP", "note_text": "test topic note"}'
```

**Steps:**
1. Open the Study Log panel in the frontend.
2. Verify the note appears in the list with source displayed as "topic".
3. Verify the "All Sources" filter includes the note.

**Pass:** Note visible under "All sources". Source shown as "topic".

---

## T2 — Source Filter Excludes Non-Dataset Notes

**Setup:** Same note from T1 present. At least one dataset-anchored note present.

**Steps:**
1. In the Study Log panel, select a specific dataset source (e.g., "openneuro") from the source filter.
2. Verify the topic-anchored note does NOT appear.
3. Verify dataset-anchored notes still appear.

**Pass:** Non-dataset notes hidden when a specific source is selected.

---

## T3 — `neurodb-telemetry` Context Usage Section Appears After Agent Turn with Context

**Setup:** Run a grounded-mode research agent turn with an active focus set.

**Steps:**
1. In the frontend, start a research agent chat with grounded mode and an active topic focus.
2. Send a message that triggers context retrieval (e.g., "What do we know about plasticity?").
3. Wait for the response to complete.
4. Run `neurodb-telemetry` in the terminal:
   ```
   cd /home/oldha/projects/neuroDb && uv run neurodb-telemetry
   ```

**Pass:** Output includes "Context Usage" section. Line shows counts in format `Np / Nn / Nc / Nd`.

---

## T4 — Grounded Agent Labels `sparse` Dataset as Insufficient

**Setup:** Have at least one dataset with `usefulness_state = "sparse"` in the local DB.
Use `inspect_external_dataset` or direct DB inspection to confirm.

**Steps:**
1. Start a research agent chat in grounded mode.
2. Set the active focus to a topic that has the sparse dataset linked.
3. Ask: "What datasets support this topic?"
4. Observe the agent response.

**Pass:** Agent response notes the sparse dataset as insufficient / evidence gap, not as supporting evidence. It does not present the sparse dataset as a research-ready resource.

---

## T5 — Context Budget Limits Visible in Telemetry Counts

**Setup:** `neurodb_models.toml` has `[context_budgets.grounded]` with `datasets = 5`.

**Steps:**
1. Run a grounded mode turn as in T3.
2. Check telemetry output: datasets count should not exceed 5.
   ```
   uv run neurodb-telemetry
   ```

**Pass:** Context Usage line shows dataset count ≤ 5 for grounded turns.
```

- [ ] **Step 2: Update `docs/projectStatus.md`**

Update the "Active focus" line, "Next" line, add the plan and completed test plan to the reference table, and update the open issues list to note LOG-059 and LOG-054 are resolved.

Specific changes:
- Active focus: `Tech Debt epoch (TD-1 CLI argument normalization, TD-2 keyword-only helper APIs)`
- Next: `Tech Debt sprint planning and implementation`
- Add to Open Issues list: remove LOG-059 and LOG-054 from open items (resolved)
- Add to Key References table:
  - `docs/superpowers/specs/2026-05-23-memory-refocus-completion-design.md` — Completion phase spec: context budgets, retrieval telemetry, task-type defaults, study log outer join, dataset usefulness
  - `docs/superpowers/plans/2026-05-23-memory-refocus-completion.md` — Completion phase implementation plan
  - `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md` — Completion phase manual test plan — T1-T5 passed and signed off 2026-05-24

- [ ] **Step 3: Commit docs**

```bash
git add docs/projectStatus.md docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_memory_refocus_completion.md \
        docs/superpowers/plans/2026-05-23-memory-refocus-completion.md
git commit -m "docs: memory refocus completion plan, manual test plan, project status update"
```
