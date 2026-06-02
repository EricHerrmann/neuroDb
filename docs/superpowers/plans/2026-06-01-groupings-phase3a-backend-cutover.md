# Groupings Phase 3a — Backend Cutover + Semantic/Proposal Matcher Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close LOG-062 server-side: replace the substring `extract_question_topics` with an LLM-based `suggest_groupings` matcher (with new-grouping proposals and child→parent rollup), cut the question read/filter/link paths over to the unified `grouping_store` engine, add `/api/research/groupings` routes and the proposal lifecycle, and seed the `plasticity`/`stroke` hierarchy — all behind stable API contracts so the existing UI keeps working.

**Architecture:** The matcher (`research/grouping_matcher.py`) mirrors `research/hypothesis_review.py`: one forced tool call via an injected `ModelClient`, telemetry via `record_model_call`, fail-closed via `record_system_warning`. Contract stability is achieved by making `topic_id`/`concept_id` in the existing API shapes carry **grouping ids**, so `_question_detail`, the per-question routes, and the React chips operate on `grouping_links` unchanged except for one additive `proposed` field. Full cutover: legacy `question_*` tables are no longer written or read (they keep their Phase-1 backfill as a dormant fallback until Phase 5).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0, FastAPI, DuckDB (runtime) / SQLite in-memory (tests), pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-06-01-groupings-phase3-question-cutover-design.md` (Phase 3a sections).

**Prerequisites:** Phase 1 (tables + backfill, `b9bb250`) and Phase 2 (`src/neurodb/db/grouping_store.py`, `grouping_types.py`) are implemented.

**Conventions (follow exactly):**
- The matcher template is `src/neurodb/research/hypothesis_review.py` (system prompt + single forced tool + `record_model_call` + tool-input parse). Read it before Task 3.
- Routing pattern: `TaskRouter(build_provider_clients()).route(task_type, engine=engine)` → `ModelRoute(model_client, model_id, provider, max_tokens)` (see `research.py:393`).
- Telemetry: `record_model_call(engine, task_type=, provider=, model=, mode=, response=, iteration=, elapsed_ms=)`; `record_system_warning(engine, warning_type=, severity=, task_type=, message=, requested_provider=None, selected_provider=None)` (both in `src/neurodb/model_telemetry.py`).
- Store unit tests: in-memory SQLite, `Base.metadata.create_all`, `Session(engine)` fixture (see `tests/unit/test_grouping_store.py`).
- API tests: build a bare `FastAPI()`, `app.state.engine = engine` (+ null `vector_store`/`knowledge_store`/`context_store`), `app.include_router(router, prefix="/api/research")`, `TestClient(app)`; suppress the create-question background thread with `with patch("threading.Thread"):` (see `tests/integration/test_question_phase1.py`).
- Migrations: `_migration_NNN_name(conn)` in `src/neurodb/db.py`, registered in `_MIGRATIONS` (latest is `17`; this adds `18`). `datetime`/`timezone` are already imported in `db.py`.
- Run the suite: `uv run pytest tests/ -q`. Single test: `uv run pytest path::test -v`.

---

### Task 1: Register the `agent.extract.groupings` task type

**Files:**
- Modify: `neurodb_models.toml` (append a task entry)
- Test: `tests/unit/test_grouping_matcher_routing.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_grouping_matcher_routing.py`:

```python
"""The grouping matcher task type must be routable (Groupings Phase 3a)."""
from neurodb.config.model_config import get_task_config


def test_agent_extract_groupings_task_configured():
    tier, max_tokens = get_task_config("agent.extract.groupings")
    assert tier == "standard"
    assert max_tokens == 1024
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_matcher_routing.py -v`
Expected: FAIL — `get_task_config` raises/returns a default for the unknown task type.

- [ ] **Step 3: Add the task entry**

In `neurodb_models.toml`, after the `[tasks."agent.grounded_review"]` block, add:

```toml
[tasks."agent.extract.groupings"]
tier = "standard"
max_tokens = 1024
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_grouping_matcher_routing.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add neurodb_models.toml tests/unit/test_grouping_matcher_routing.py
git commit -m "feat(groupings): add agent.extract.groupings task type (standard tier)"
```

---

### Task 2: Surface the grouping's own status in `get_groupings_for_anchor`

The detail builder needs each grouping's `status` (to set `proposed`). Phase 2's helper returns only `link_status`; add `grouping_status`.

**Files:**
- Modify: `src/neurodb/db/grouping_store.py` (`get_groupings_for_anchor`)
- Test: `tests/unit/test_grouping_store.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_grouping_store.py`:

```python
def test_get_groupings_for_anchor_includes_grouping_status(session):
    from neurodb.db.grouping_store import link_grouping
    g = get_or_create_grouping(session, "topic", "plasticity", status="proposed")
    link_grouping(session, g.id, "question", 5, status="pending")
    rows = get_groupings_for_anchor(session, "question", 5)
    assert rows[0]["grouping_status"] == "proposed"
    assert rows[0]["link_status"] == "pending"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_store.py::test_get_groupings_for_anchor_includes_grouping_status -v`
Expected: FAIL — `KeyError: 'grouping_status'`.

- [ ] **Step 3: Extend the function**

In `src/neurodb/db/grouping_store.py`, replace the body of `get_groupings_for_anchor` with:

```python
def get_groupings_for_anchor(
    session: Session, anchor_type: str, anchor_id: int, *, status: str | None = None
) -> list[dict]:
    """Groupings linked to an anchor, each carrying its link status and the
    grouping's own status."""
    stmt = (
        select(Grouping, GroupingLink.status)
        .join(GroupingLink, GroupingLink.grouping_id == Grouping.id)
        .where(GroupingLink.anchor_type == anchor_type, GroupingLink.anchor_id == anchor_id)
    )
    if status is not None:
        stmt = stmt.where(GroupingLink.status == status)
    rows = session.execute(stmt).all()
    return [
        {"id": g.id, "type": g.type, "name": g.name, "parent_id": g.parent_id,
         "grouping_status": g.status, "link_status": link_status}
        for g, link_status in rows
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_grouping_store.py -v`
Expected: PASS (all prior tests + the new one).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_store.py tests/unit/test_grouping_store.py
git commit -m "feat(groupings): surface grouping_status in get_groupings_for_anchor"
```

---

### Task 3: The semantic/proposal matcher `suggest_groupings`

**Files:**
- Create: `src/neurodb/research/grouping_matcher.py`
- Test: `tests/unit/test_grouping_matcher.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_grouping_matcher.py`:

```python
"""Unit tests for suggest_groupings with a fake ModelClient (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.config.model_client import ContentBlock, ModelResponse
from neurodb.db.grouping_store import get_or_create_grouping, set_parent
from neurodb.research.grouping_matcher import suggest_groupings


def _now():
    return datetime.now(timezone.utc).isoformat()


class FakeClient:
    """Duck-typed ModelClient returning a single submit_groupings tool call."""

    def __init__(self, tool_input):
        self._tool_input = tool_input
        self.calls = []

    def format_tool(self, tool_definition):
        return tool_definition

    def create_message(self, *, model, messages, system, tools, max_tokens, tool_choice=None):
        self.calls.append({"model": model, "tool_choice": tool_choice})
        return ModelResponse(
            stop_reason="tool_use",
            content=[ContentBlock(type="tool_use", tool_name="submit_groupings",
                                  tool_input=self._tool_input)],
            input_tokens=12, output_tokens=8,
        )


@pytest.fixture
def engine():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _run(engine, client, gtype="topic"):
    return suggest_groupings(
        engine, anchor_type="question", anchor_id=1, anchor_text="some text",
        gtype=gtype, model_client=client, model="fake-model",
        model_provider="anthropic", max_tokens=1024,
    )


def _links(engine):
    with engine.connect() as conn:
        return conn.execute(text(
            "SELECT grouping_id, anchor_type, anchor_id, status FROM grouping_links"
        )).fetchall()


def test_relevant_existing_creates_pending_links(engine):
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")
        s.commit()
        gid = g.id
    client = FakeClient({"relevant_existing": [{"id": gid, "reason": "match"}], "proposed_new": []})
    out = _run(engine, client)
    assert out["suggested"] == ["stroke"]
    assert (gid, "question", 1, "pending") in _links(engine)


def test_child_match_rolls_up_to_parent(engine):
    with Session(engine) as s:
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        set_parent(s, child.id, parent.id)
        s.commit()
        parent_id, child_id = parent.id, child.id
    client = FakeClient({"relevant_existing": [{"id": child_id, "reason": "m"}], "proposed_new": []})
    out = _run(engine, client)
    rows = {(r[0], r[3]) for r in _links(engine)}
    assert (child_id, "pending") in rows
    assert (parent_id, "pending") in rows  # rolled up
    assert "plasticity" in out["suggested"]


def test_proposed_new_creates_proposed_grouping(engine):
    client = FakeClient({"relevant_existing": [],
                         "proposed_new": [{"name": "plasticity", "parent_name": None}]})
    out = _run(engine, client)
    assert out["proposed"] == ["plasticity"]
    with engine.connect() as conn:
        row = conn.execute(text(
            "SELECT status FROM groupings WHERE type='topic' AND name='plasticity'"
        )).fetchone()
    assert row[0] == "proposed"
    assert len(_links(engine)) == 1


def test_proposed_name_matching_existing_active_links_instead_of_duplicating(engine):
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")  # active
        s.commit()
        gid = g.id
    client = FakeClient({"relevant_existing": [],
                         "proposed_new": [{"name": "stroke", "parent_name": None}]})
    out = _run(engine, client)
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE name='stroke'")).fetchone()[0]
    assert n == 1                      # no duplicate
    assert out["proposed"] == []       # treated as existing
    assert (gid, "question", 1, "pending") in _links(engine)


def test_invalid_existing_id_is_ignored(engine):
    client = FakeClient({"relevant_existing": [{"id": 99999, "reason": "ghost"}], "proposed_new": []})
    out = _run(engine, client)
    assert out["suggested"] == []
    assert _links(engine) == []
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_matcher.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.research.grouping_matcher'`.

- [ ] **Step 3: Create the matcher module**

Create `src/neurodb/research/grouping_matcher.py`:

```python
"""Research epoch — LLM-based grouping suggestion with new-grouping proposals.

Replaces substring matching (LOG-062). Modeled on hypothesis_review.py: one
forced tool call, telemetry via record_model_call, fail-closed via the
run_suggest_groupings wrapper.
"""
from __future__ import annotations

import json
import time

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.db.grouping_store import (
    get_grouping,
    get_or_create_grouping,
    link_grouping,
    list_groupings,
)
from neurodb.db.grouping_types import GROUPING_TYPES
from neurodb.model_telemetry import record_model_call, record_system_warning


_SYSTEM_PROMPT = """You categorize neuroscience research text.
You are given a piece of text and a list of existing groupings of one kind.
Identify which existing groupings are genuinely relevant to the text, and propose
any clearly warranted new groupings of the same kind that are not already in the list.
Be conservative: only include groupings the text is actually about.
Call submit_groupings exactly once with your structured answer."""

_SUBMIT_GROUPINGS_TOOL = {
    "name": "submit_groupings",
    "description": (
        "Record which existing groupings are relevant to the text and propose any "
        "new ones. Call exactly once."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "relevant_existing": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "id": {"type": "integer"},
                        "reason": {"type": "string"},
                    },
                    "required": ["id", "reason"],
                },
            },
            "proposed_new": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string"},
                        "parent_name": {"type": ["string", "null"]},
                    },
                    "required": ["name", "parent_name"],
                },
            },
        },
        "required": ["relevant_existing", "proposed_new"],
    },
}


def _build_prompt(anchor_text: str, gtype: str, candidates: list[dict]) -> str:
    return json.dumps({
        "instruction": (
            f"Classify the text against existing '{gtype}' groupings. Return relevant "
            "existing ones by id, and propose clearly warranted new ones. "
            "Call submit_groupings once."
        ),
        "grouping_kind": gtype,
        "text": anchor_text,
        "existing_groupings": [
            {"id": c["id"], "name": c["name"], "parent_id": c.get("parent_id")}
            for c in candidates
        ],
    }, indent=2)


def _as_list(value) -> list:
    return value if isinstance(value, list) else []


def _parse_response(response) -> dict:
    from neurodb.config.model_client import ModelResponse
    if isinstance(response, ModelResponse):
        for block in response.content:
            if block.type == "tool_use" and block.tool_name == "submit_groupings":
                inputs = block.tool_input or {}
                return {
                    "relevant_existing": _as_list(inputs.get("relevant_existing")),
                    "proposed_new": _as_list(inputs.get("proposed_new")),
                }
    return {"relevant_existing": [], "proposed_new": []}


def suggest_groupings(
    engine: Engine,
    *,
    anchor_type: str,
    anchor_id: int,
    anchor_text: str,
    gtype: str,
    model_client,
    model: str,
    model_provider: str,
    max_tokens: int,
) -> dict:
    """Match anchor_text against existing groupings of gtype and propose new ones.

    Persists pending grouping_links for matches (with parent rollup) and proposed
    groupings for new items. Returns a summary dict.
    """
    with get_session(engine) as session:
        candidates = list_groupings(session, gtype=gtype, status="active")

    started = time.monotonic()
    response = model_client.create_message(
        model=model,
        max_tokens=max_tokens,
        system=_SYSTEM_PROMPT,
        tools=[model_client.format_tool(_SUBMIT_GROUPINGS_TOOL)],
        messages=[{"role": "user", "content": _build_prompt(anchor_text, gtype, candidates)}],
        tool_choice="required",
    )
    elapsed_ms = int((time.monotonic() - started) * 1000)
    record_model_call(
        engine,
        task_type="agent.extract.groupings",
        provider=model_provider,
        model=model,
        mode="neuro_research",
        response=response,
        iteration=1,
        elapsed_ms=elapsed_ms,
    )

    parsed = _parse_response(response)
    allow_proposal = GROUPING_TYPES[gtype].allow_agent_proposal
    suggested: list[str] = []
    proposed: list[str] = []

    with get_session(engine) as session:
        for item in parsed["relevant_existing"]:
            gid = item.get("id") if isinstance(item, dict) else None
            if not isinstance(gid, int):
                continue
            g = get_grouping(session, gid)
            if g is None or g.type != gtype or g.status != "active":
                continue
            link_grouping(session, g.id, anchor_type, anchor_id, status="pending")
            suggested.append(g.name)
            if g.parent_id is not None:
                link_grouping(session, g.parent_id, anchor_type, anchor_id, status="pending")
                parent = get_grouping(session, g.parent_id)
                if parent is not None:
                    suggested.append(parent.name)

        if allow_proposal:
            for item in parsed["proposed_new"]:
                name = str((item or {}).get("name") or "").strip()
                if not name:
                    continue
                g = get_or_create_grouping(session, gtype, name, status="proposed")
                link_grouping(session, g.id, anchor_type, anchor_id, status="pending")
                if g.status == "proposed":
                    proposed.append(g.name)
                else:
                    suggested.append(g.name)

    return {
        "anchor_type": anchor_type,
        "anchor_id": anchor_id,
        "gtype": gtype,
        "suggested": list(dict.fromkeys(suggested)),
        "proposed": list(dict.fromkeys(proposed)),
    }


def run_suggest_groupings(
    engine: Engine,
    *,
    anchor_type: str,
    anchor_id: int,
    anchor_text: str,
    gtypes: tuple[str, ...] = ("topic", "concept"),
) -> None:
    """Fail-closed wrapper: resolve a route per type and run the matcher.

    On any failure for a type, write a SystemWarning and persist nothing for that
    type. The anchor (e.g. the question) is unaffected.
    """
    from neurodb.config.provider_factory import build_provider_clients
    from neurodb.config.task_router import TaskRouter

    for gtype in gtypes:
        try:
            route = TaskRouter(build_provider_clients()).route(
                "agent.extract.groupings", engine=engine
            )
            suggest_groupings(
                engine,
                anchor_type=anchor_type,
                anchor_id=anchor_id,
                anchor_text=anchor_text,
                gtype=gtype,
                model_client=route.model_client,
                model=route.model_id,
                model_provider=route.provider,
                max_tokens=route.max_tokens,
            )
        except Exception as exc:  # noqa: BLE001 — fail closed for any matcher error
            record_system_warning(
                engine,
                warning_type="grouping_match_failed",
                severity="warning",
                task_type="agent.extract.groupings",
                message=f"{gtype}: {str(exc)[:300]}",
            )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_grouping_matcher.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/research/grouping_matcher.py tests/unit/test_grouping_matcher.py
git commit -m "feat(groupings): suggest_groupings matcher with proposals and rollup"
```

---

### Task 4: Fail-closed behavior of `run_suggest_groupings`

**Files:**
- Test: `tests/unit/test_grouping_matcher.py` (append)

This task adds no production code — it verifies the wrapper persists nothing and writes a `SystemWarning` when routing fails.

- [ ] **Step 1: Write the test**

Append to `tests/unit/test_grouping_matcher.py`:

```python
def test_run_suggest_groupings_fails_closed(engine, monkeypatch):
    from sqlalchemy import text as _text
    from neurodb.research import grouping_matcher
    import neurodb.config.provider_factory as pf

    # No providers configured → TaskRouter.route raises RoutingError.
    monkeypatch.setattr(pf, "build_provider_clients", lambda: {})

    grouping_matcher.run_suggest_groupings(
        engine, anchor_type="question", anchor_id=1, anchor_text="x", gtypes=("topic",)
    )

    with engine.connect() as conn:
        links = conn.execute(_text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
        warnings = conn.execute(_text(
            "SELECT COUNT(*) FROM system_warnings WHERE warning_type='grouping_match_failed'"
        )).fetchone()[0]
    assert links == 0
    assert warnings >= 1
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/unit/test_grouping_matcher.py::test_run_suggest_groupings_fails_closed -v`
Expected: PASS. (If `system_warnings` is absent, the engine fixture only ran `create_all`; the table exists from the schema model `SystemWarning`. If the count query errors, confirm the table name via `SELECT name FROM sqlite_master`.)

- [ ] **Step 3: Commit**

```bash
git add tests/unit/test_grouping_matcher.py
git commit -m "test(groupings): run_suggest_groupings fails closed with a SystemWarning"
```

---

### Task 5: `/api/research/groupings` routes + schemas

**Files:**
- Modify: `src/neurodb/api/schemas/research.py` (add three models; add `proposed` to the two link models)
- Modify: `src/neurodb/api/routes/research.py` (add three routes + a `_now_iso` helper)
- Test: `tests/integration/test_groupings_routes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_groupings_routes.py`:

```python
"""API tests for /api/research/groupings (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base
from neurodb.db.grouping_store import get_or_create_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_create_list_and_patch_status(client_engine):
    client, engine = client_engine
    r = client.post("/api/research/groupings",
                    json={"type": "topic", "name": "plasticity"})
    assert r.status_code == 200
    gid = r.json()["id"]
    assert r.json()["status"] == "active"

    listed = client.get("/api/research/groupings?type=topic&status=active").json()
    assert [g["name"] for g in listed] == ["plasticity"]

    # archive via status patch
    patched = client.patch(f"/api/research/groupings/{gid}", json={"status": "archived"})
    assert patched.status_code == 200
    assert patched.json()["status"] == "archived"


def test_reparent_and_invariant_422(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        concept = get_or_create_grouping(s, "concept", "LTP")
        s.commit()
        parent_id, child_id, concept_id = parent.id, child.id, concept.id

    ok = client.patch(f"/api/research/groupings/{child_id}", json={"parent_id": parent_id})
    assert ok.status_code == 200
    assert ok.json()["parent_id"] == parent_id

    # cross-type parent is rejected
    bad = client.patch(f"/api/research/groupings/{concept_id}", json={"parent_id": parent_id})
    assert bad.status_code == 422


def test_unknown_type_422(client_engine):
    client, _ = client_engine
    r = client.post("/api/research/groupings", json={"type": "method", "name": "fMRI"})
    assert r.status_code == 422
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_groupings_routes.py -v`
Expected: FAIL — routes return 404/422 for missing endpoints or schemas don't exist.

- [ ] **Step 3: Add the schemas**

In `src/neurodb/api/schemas/research.py`, add `proposed` to the two link models and append three new models:

```python
class QuestionTopicLink(BaseModel):
    topic_id: int
    topic_name: str
    status: str
    proposed: bool = False


class QuestionConceptLink(BaseModel):
    concept_id: int
    concept_name: str
    status: str
    proposed: bool = False
```

(Replace the existing two class bodies above; the only change is the added `proposed` field.) Then append:

```python
class GroupingItem(BaseModel):
    id: int
    type: str
    name: str
    parent_id: int | None = None
    status: str
    description: str | None = None


class CreateGroupingRequest(BaseModel):
    type: str
    name: str
    parent_id: int | None = None
    description: str | None = None


class PatchGroupingRequest(BaseModel):
    parent_id: int | None = None
    status: str | None = None
```

- [ ] **Step 4: Add the routes + helper**

In `src/neurodb/api/routes/research.py`, add the import to the existing `from neurodb.api.schemas.research import (...)` block:

```python
    CreateGroupingRequest,
    GroupingItem,
    PatchGroupingRequest,
```

Add a module-level helper just below `router = APIRouter()`:

```python
def _now_iso() -> str:
    return datetime.now(UTC).isoformat()
```

Append these routes at the end of the file:

```python
@router.get("/groupings", response_model=list[GroupingItem])
def list_groupings_route(
    type: str | None = Query(default=None),
    status: str | None = Query(default=None),
    engine: Engine = Depends(get_engine),
) -> list[GroupingItem]:
    from neurodb.db.grouping_store import list_groupings
    with get_session(engine) as session:
        return [GroupingItem(**g) for g in list_groupings(session, gtype=type, status=status)]


@router.post("/groupings", response_model=GroupingItem)
def create_grouping_route(
    body: CreateGroupingRequest,
    engine: Engine = Depends(get_engine),
) -> GroupingItem:
    from neurodb.db.grouping_store import get_or_create_grouping, set_parent, get_grouping
    from neurodb.db.grouping_types import GroupingHierarchyError, UnknownGroupingType
    with get_session(engine) as session:
        try:
            g = get_or_create_grouping(session, body.type, body.name, description=body.description)
            if body.parent_id is not None:
                set_parent(session, g.id, body.parent_id)
            session.flush()
            g = get_grouping(session, g.id)
            return GroupingItem(id=g.id, type=g.type, name=g.name,
                                parent_id=g.parent_id, status=g.status, description=g.description)
        except (UnknownGroupingType, GroupingHierarchyError) as exc:
            raise HTTPException(status_code=422, detail=str(exc))


@router.patch("/groupings/{grouping_id}", response_model=GroupingItem)
def patch_grouping_route(
    grouping_id: int,
    body: PatchGroupingRequest,
    engine: Engine = Depends(get_engine),
) -> GroupingItem:
    from neurodb.db.grouping_store import get_grouping, set_parent
    from neurodb.db.grouping_types import GroupingHierarchyError
    fields = body.model_dump(exclude_unset=True)
    with get_session(engine) as session:
        if get_grouping(session, grouping_id) is None:
            raise HTTPException(status_code=404, detail=f"Grouping {grouping_id} not found")
        try:
            if "parent_id" in fields:
                set_parent(session, grouping_id, fields["parent_id"])
            if fields.get("status") is not None:
                g = get_grouping(session, grouping_id)
                g.status = fields["status"]
                g.updated_at = _now_iso()
                session.flush()
        except GroupingHierarchyError as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        g = get_grouping(session, grouping_id)
        return GroupingItem(id=g.id, type=g.type, name=g.name,
                            parent_id=g.parent_id, status=g.status, description=g.description)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_groupings_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/schemas/research.py src/neurodb/api/routes/research.py tests/integration/test_groupings_routes.py
git commit -m "feat(groupings): /api/research/groupings GET/POST/PATCH routes + schemas"
```

---

### Task 6: Cut `_question_detail` over to the engine (with `proposed`)

**Files:**
- Modify: `src/neurodb/api/routes/research.py` (`_question_detail`)
- Test: `tests/integration/test_question_detail_engine.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_question_detail_engine.py`:

```python
"""_question_detail sources topics/concepts from the engine (Groupings Phase 3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, ResearchQuestion
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_detail_reflects_engine_links_and_proposed(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        qid = q.id
        active = get_or_create_grouping(s, "topic", "stroke")            # active
        prop = get_or_create_grouping(s, "concept", "engram", status="proposed")
        link_grouping(s, active.id, "question", qid, status="confirmed")
        link_grouping(s, prop.id, "question", qid, status="pending")
        s.commit()
        active_id, prop_id = active.id, prop.id

    detail = client.get(f"/api/research/questions/{qid}").json()
    topics = {t["topic_id"]: t for t in detail["topics"]}
    concepts = {c["concept_id"]: c for c in detail["concepts"]}
    assert topics[active_id]["status"] == "confirmed"
    assert topics[active_id]["proposed"] is False
    assert concepts[prop_id]["status"] == "pending"
    assert concepts[prop_id]["proposed"] is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_question_detail_engine.py -v`
Expected: FAIL — current `_question_detail` reads `QuestionTopic`/`QuestionConcept`, so the engine links don't appear.

- [ ] **Step 3: Rewrite `_question_detail`**

In `src/neurodb/api/routes/research.py`, replace the entire `_question_detail` function with:

```python
def _question_detail(engine: Engine, question_id: int) -> ResearchQuestionDetail:
    """Build ResearchQuestionDetail from the unified grouping engine."""
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.grouping_store import get_groupings_for_anchor
    from neurodb.api.schemas.research import QuestionConceptLink, QuestionTopicLink
    with get_session(engine) as session:
        q = session.get(ResearchQuestionORM, question_id)
        if q is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        links = get_groupings_for_anchor(session, "question", question_id)
        topics: list[QuestionTopicLink] = []
        concepts: list[QuestionConceptLink] = []
        for g in links:
            is_proposed = g["grouping_status"] == "proposed"
            if g["type"] == "topic":
                topics.append(QuestionTopicLink(
                    topic_id=g["id"], topic_name=g["name"],
                    status=g["link_status"], proposed=is_proposed))
            elif g["type"] == "concept":
                concepts.append(QuestionConceptLink(
                    concept_id=g["id"], concept_name=g["name"],
                    status=g["link_status"], proposed=is_proposed))
        return ResearchQuestionDetail(
            id=q.id,
            question=q.question,
            status=q.status,
            topic_context=q.topic_context,
            origin_session_id=getattr(q, "origin_session_id", None),
            created_at=q.created_at,
            topics=topics,
            concepts=concepts,
        )
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_question_detail_engine.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/research.py tests/integration/test_question_detail_engine.py
git commit -m "feat(groupings): source _question_detail from the grouping engine"
```

---

### Task 7: Cut `create_question` and the `?topic_id=` filter over to the engine

**Files:**
- Modify: `src/neurodb/api/routes/research.py` (`create_question` background thread; `get_questions` filter)
- Test: `tests/integration/test_question_cutover.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_question_cutover.py`:

```python
"""create_question wiring + parent-filter rollup over the engine (Groupings Phase 3a)."""
from datetime import datetime, timezone
from unittest.mock import patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, ResearchQuestion
from neurodb.db.grouping_store import get_or_create_grouping, set_parent, link_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_create_question_invokes_matcher_wrapper(client_engine):
    client, engine = client_engine
    calls = {}

    def fake_run(engine_arg, *, anchor_type, anchor_id, anchor_text, gtypes=("topic", "concept")):
        calls["anchor_type"] = anchor_type
        calls["anchor_text"] = anchor_text
        calls["gtypes"] = gtypes

    # Run the background work synchronously by stubbing the wrapper and the thread.
    with patch("neurodb.research.grouping_matcher.run_suggest_groupings", fake_run), \
         patch("threading.Thread") as thread_cls:
        thread_cls.side_effect = lambda target, daemon=False: type(
            "T", (), {"start": staticmethod(target)})()
        resp = client.post("/api/research/questions",
                           json={"question": "How does plasticity work?", "topic_context": ""})
    assert resp.status_code == 200
    assert calls["anchor_type"] == "question"
    assert calls["anchor_text"] == "How does plasticity work?"
    assert calls["gtypes"] == ("topic", "concept")


def test_parent_filter_returns_child_tagged_question(client_engine):
    client, engine = client_engine
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        qid = q.id
        parent = get_or_create_grouping(s, "topic", "plasticity")
        child = get_or_create_grouping(s, "topic", "neuroplasticity")
        set_parent(s, child.id, parent.id)
        link_grouping(s, child.id, "question", qid, status="confirmed")
        s.commit()
        parent_id, child_id = parent.id, child.id

    by_parent = client.get(f"/api/research/questions?topic_id={parent_id}").json()
    assert [d["id"] for d in by_parent] == [qid]      # rollup includes child
    by_child = client.get(f"/api/research/questions?topic_id={child_id}").json()
    assert [d["id"] for d in by_child] == [qid]       # leaf exact
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_question_cutover.py -v`
Expected: FAIL — `create_question` still calls `extract_question_topics`; the filter still queries `QuestionTopic`.

- [ ] **Step 3: Rewrite the `create_question` background thread**

In `src/neurodb/api/routes/research.py`, replace the `_extract` closure and its thread launch inside `create_question` with:

```python
    def _extract():
        from neurodb.research.grouping_matcher import run_suggest_groupings
        run_suggest_groupings(
            engine,
            anchor_type="question",
            anchor_id=question_id,
            anchor_text=body.question,
            gtypes=("topic", "concept"),
        )

    threading.Thread(target=_extract, daemon=True).start()
    return _question_detail(engine, question_id)
```

- [ ] **Step 4: Rewrite the `?topic_id=` filter in `get_questions`**

In `src/neurodb/api/routes/research.py`, replace the body of `get_questions` with:

```python
    from sqlalchemy import select as _select
    from neurodb.schema import GroupingLink, ResearchQuestion as ResearchQuestionORM
    from neurodb.db.grouping_store import resolve_filter_ids
    with get_session(engine) as session:
        query = _select(ResearchQuestionORM)
        if status:
            query = query.where(ResearchQuestionORM.status.in_(status))
        if topic_id is not None:
            ids = resolve_filter_ids(session, topic_id)
            query = query.where(
                ResearchQuestionORM.id.in_(
                    _select(GroupingLink.anchor_id).where(
                        GroupingLink.anchor_type == "question",
                        GroupingLink.grouping_id.in_(ids),
                        GroupingLink.status == "confirmed",
                    )
                )
            )
        rows = session.execute(
            query.order_by(ResearchQuestionORM.created_at.desc())
        ).scalars().all()
    return [_question_detail(engine, r.id) for r in rows]
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_question_cutover.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/research.py tests/integration/test_question_cutover.py
git commit -m "feat(groupings): cut create_question + topic filter over to the engine"
```

---

### Task 8: Remap per-question topic/concept routes + proposal lifecycle

**Files:**
- Modify: `src/neurodb/api/routes/research.py` (the six per-question topic/concept routes)
- Test: `tests/integration/test_question_link_routes.py`

The path id (`topic_id` / `concept_id`) is now a **grouping id**. Confirm flips a `proposed` grouping to `active`; dismiss deletes an orphaned `proposed` grouping.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_question_link_routes.py`:

```python
"""Per-question link routes operate on grouping_links + proposal lifecycle (3a)."""
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.schema import Base, ResearchQuestion
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def client_engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def _make_question(engine) -> int:
    with Session(engine) as s:
        q = ResearchQuestion(question="Q?", topic_context="", status="open",
                             created_at=_now(), updated_at=_now())
        s.add(q)
        s.flush()
        return q.id


def test_add_then_confirm_proposed_topic_activates_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "plasticity", status="proposed")
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    resp = client.patch(f"/api/research/questions/{qid}/topics/{gid}",
                        json={"status": "confirmed"})
    assert resp.status_code == 200
    with engine.connect() as conn:
        gstatus = conn.execute(text("SELECT status FROM groupings WHERE id=:i"),
                               {"i": gid}).fetchone()[0]
        lstatus = conn.execute(text(
            "SELECT status FROM grouping_links WHERE grouping_id=:i AND anchor_id=:q"),
            {"i": gid, "q": qid}).fetchone()[0]
    assert gstatus == "active"      # proposed -> active on confirm
    assert lstatus == "confirmed"


def test_dismiss_proposed_topic_deletes_orphan_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "plasticity", status="proposed")
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    resp = client.delete(f"/api/research/questions/{qid}/topics/{gid}")
    assert resp.status_code == 204
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                         {"i": gid}).fetchone()[0]
    assert n == 0      # orphaned proposed grouping cleaned up


def test_dismiss_active_topic_keeps_grouping(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "topic", "stroke")  # active
        link_grouping(s, g.id, "question", qid, status="pending")
        s.commit()
        gid = g.id

    client.delete(f"/api/research/questions/{qid}/topics/{gid}")
    with engine.connect() as conn:
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE id=:i"),
                         {"i": gid}).fetchone()[0]
    assert n == 1      # active grouping is never auto-deleted


def test_add_concept_link_via_route(client_engine):
    client, engine = client_engine
    qid = _make_question(engine)
    with Session(engine) as s:
        g = get_or_create_grouping(s, "concept", "LTP")
        s.commit()
        gid = g.id
    resp = client.post(f"/api/research/questions/{qid}/concepts", json={"concept_id": gid})
    assert resp.status_code == 200
    assert any(c["concept_id"] == gid and c["status"] == "confirmed"
               for c in resp.json()["concepts"])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/integration/test_question_link_routes.py -v`
Expected: FAIL — routes still call `topic_store` against legacy tables.

- [ ] **Step 3: Replace the six per-question routes**

In `src/neurodb/api/routes/research.py`, replace the six route functions
(`add_question_topic`, `patch_question_topic`, `remove_question_topic`,
`add_question_concept`, `patch_question_concept`, `remove_question_concept`) with the
engine-backed versions below. They use a shared `_dismiss_question_grouping` helper for the
orphan-proposal cleanup. Add the helper just above `add_question_topic`:

```python
def _confirm_question_grouping(engine: Engine, question_id: int, grouping_id: int, status: str) -> bool:
    """Update a question→grouping link status; activate a proposed grouping on confirm.
    Returns True if a link was found."""
    from neurodb.db.grouping_store import update_link_status, get_grouping
    with get_session(engine) as session:
        found = update_link_status(session, grouping_id, "question", question_id, status)
        if not found:
            return False
        if status == "confirmed":
            g = get_grouping(session, grouping_id)
            if g is not None and g.status == "proposed":
                g.status = "active"
                g.updated_at = _now_iso()
                session.flush()
        return True


def _dismiss_question_grouping(engine: Engine, question_id: int, grouping_id: int) -> bool:
    """Unlink a question→grouping link; delete the grouping if it is an orphan proposal.
    Returns True if a link was found."""
    from sqlalchemy import select as _select
    from neurodb.schema import GroupingLink
    from neurodb.db.grouping_store import unlink_grouping, get_grouping
    with get_session(engine) as session:
        found = unlink_grouping(session, grouping_id, "question", question_id)
        if not found:
            return False
        g = get_grouping(session, grouping_id)
        if g is not None and g.status == "proposed":
            remaining = session.execute(
                _select(GroupingLink).where(GroupingLink.grouping_id == grouping_id)
            ).first()
            if remaining is None:
                session.delete(g)
                session.flush()
        return True


@router.post("/questions/{question_id}/topics", response_model=ResearchQuestionDetail)
def add_question_topic(
    question_id: int,
    body: AddTopicLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.grouping_store import link_grouping
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_grouping(session, body.topic_id, "question", question_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/topics/{topic_id}", response_model=ResearchQuestionDetail)
def patch_question_topic(
    question_id: int,
    topic_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    if not _confirm_question_grouping(engine, question_id, topic_id, body.status):
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/topics/{topic_id}", status_code=204)
def remove_question_topic(
    question_id: int,
    topic_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    if not _dismiss_question_grouping(engine, question_id, topic_id):
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")


@router.post("/questions/{question_id}/concepts", response_model=ResearchQuestionDetail)
def add_question_concept(
    question_id: int,
    body: AddConceptLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.grouping_store import link_grouping
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_grouping(session, body.concept_id, "question", question_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/concepts/{concept_id}", response_model=ResearchQuestionDetail)
def patch_question_concept(
    question_id: int,
    concept_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    if not _confirm_question_grouping(engine, question_id, concept_id, body.status):
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/concepts/{concept_id}", status_code=204)
def remove_question_concept(
    question_id: int,
    concept_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    if not _dismiss_question_grouping(engine, question_id, concept_id):
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/integration/test_question_link_routes.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/research.py tests/integration/test_question_link_routes.py
git commit -m "feat(groupings): remap per-question link routes + proposal lifecycle"
```

---

### Task 9: Hierarchy seed migration `018`

**Files:**
- Modify: `src/neurodb/db.py` (add `_migration_018_seed_grouping_hierarchy`; register `18`)
- Test: `tests/unit/test_migration_018_seed.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_018_seed.py`:

```python
"""Migration 018 seeds the plasticity/stroke hierarchy on groupings (3a)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.db import _migration_018_seed_grouping_hierarchy, _MIGRATIONS


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_engine():
    eng = create_engine("sqlite:///:memory:",
                        connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(eng)
    return eng


def _seed_topics(engine, names):
    with engine.connect() as conn:
        for n in names:
            conn.execute(text(
                "INSERT INTO groupings (type, name, parent_id, status, created_at, updated_at) "
                "VALUES ('topic', :n, NULL, 'active', :now, :now)"
            ), {"n": n, "now": _now()})
        conn.commit()


def test_migration_018_registered():
    assert _MIGRATIONS.get(18) is _migration_018_seed_grouping_hierarchy


def test_creates_plasticity_and_sets_parents():
    engine = _make_engine()
    _seed_topics(engine, ["neuroplasticity", "stroke", "stroke recovery", "unrelated"])
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
    with engine.connect() as conn:
        plasticity_id = conn.execute(text(
            "SELECT id FROM groupings WHERE type='topic' AND name='plasticity'"
        )).fetchone()[0]
        np_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='neuroplasticity'"
        )).fetchone()[0]
        stroke_id = conn.execute(text(
            "SELECT id FROM groupings WHERE name='stroke'"
        )).fetchone()[0]
        sr_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='stroke recovery'"
        )).fetchone()[0]
        unrelated_parent = conn.execute(text(
            "SELECT parent_id FROM groupings WHERE name='unrelated'"
        )).fetchone()[0]
    assert np_parent == plasticity_id
    assert sr_parent == stroke_id
    assert unrelated_parent is None


def test_idempotent():
    engine = _make_engine()
    _seed_topics(engine, ["neuroplasticity"])
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_018_seed_grouping_hierarchy(conn)
        conn.commit()
        n = conn.execute(text(
            "SELECT COUNT(*) FROM groupings WHERE name='plasticity'"
        )).fetchone()[0]
    assert n == 1
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_018_seed.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_018_seed_grouping_hierarchy'`.

- [ ] **Step 3: Add the migration**

In `src/neurodb/db.py`, immediately before the `_MIGRATIONS: dict[int, callable] = {` line, add:

```python
def _migration_018_seed_grouping_hierarchy(conn) -> None:
    """Seed the plasticity/stroke topic hierarchy on the unified groupings table.
    Creates a top-level 'plasticity' topic and sets parent_id on seed children.
    Additive and idempotent."""
    now = datetime.now(timezone.utc).isoformat()
    conn.execute(text("""
        INSERT INTO groupings (type, name, parent_id, status, description, created_at, updated_at)
        SELECT 'topic', 'plasticity', NULL, 'active', NULL, :now, :now
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings WHERE type='topic' AND name='plasticity'
        )
    """), {"now": now})

    seed = {
        "plasticity": [
            "neuroplasticity", "circuit plasticity", "interhemispheric plasticity",
            "cortical remapping", "maladaptive reorganization",
            "interhemispheric competition", "interhemispheric inhibition",
            "transcallosal inhibition",
        ],
        "stroke": [
            "stroke recovery", "stroke rehabilitation", "stroke severity",
            "peri-infarct cortex",
        ],
    }
    for parent_name, children in seed.items():
        prow = conn.execute(text(
            "SELECT id FROM groupings WHERE type='topic' AND name=:n"
        ), {"n": parent_name}).fetchone()
        if prow is None:
            continue
        pid = prow[0]
        for child in children:
            conn.execute(text("""
                UPDATE groupings SET parent_id = :pid, updated_at = :now
                WHERE type='topic' AND name = :child
                  AND (parent_id IS NULL OR parent_id <> :pid)
            """), {"pid": pid, "now": now, "child": child})
```

- [ ] **Step 4: Register the migration**

In `src/neurodb/db.py`, add the `18:` entry as the last item of `_MIGRATIONS`:

```python
    17: _migration_017_groupings,
    18: _migration_018_seed_grouping_hierarchy,
}
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_migration_018_seed.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_018_seed.py
git commit -m "feat(groupings): migration 018 seeds plasticity/stroke hierarchy"
```

---

### Task 10: Manual test plan, full-suite green, status sync

**Files:**
- Create: `docs/testsPlans/manualTestPlan_groupings_phase3a.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_groupings_phase3a.md` covering what automation mocks (a **real** model call + live server/DB):

```markdown
# Manual Test Plan — Groupings Phase 3a (Backend Cutover)

## Prerequisites
- [ ] Run the automated suite: `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
- [ ] A provider API key is configured in `.env` (the matcher makes a real model call).
- [ ] Start the backend: `uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`.

## T1 — Live matcher produces suggestions
- [ ] `POST /api/research/questions` with `{"question": "How does cortical remapping support stroke recovery?"}`.
- [ ] Within a few seconds, `GET /api/research/questions/{id}` shows pending topic/concept links from the live matcher.
- [ ] Expected: relevant existing groupings appear as `pending`; a child match (e.g. `cortical remapping`) also surfaces its parent (`plasticity`) via rollup.
- [ ] Pass: at least one pending suggestion is present and reflects the question's content.

## T2 — Proposal of a new grouping
- [ ] `POST` a question whose key concept has no existing grouping (e.g. a general term not yet in the taxonomy).
- [ ] Expected: a suggestion with `proposed: true` appears (a `proposed` grouping was created).
- [ ] `PATCH /api/research/questions/{id}/topics/{grouping_id}` with `{"status":"confirmed"}`.
- [ ] Pass: the grouping is now `active` (`GET /api/research/groupings?type=topic` lists it) and the link is `confirmed`.

## T3 — Dismiss cleans up an orphan proposal
- [ ] Create a question that yields a proposed grouping; `DELETE` its link before confirming.
- [ ] Pass: the proposed grouping no longer appears in `GET /api/research/groupings`.

## T4 — Parent filter rollup
- [ ] Confirm a question's link to a child topic (e.g. `neuroplasticity`).
- [ ] `GET /api/research/questions?topic_id={plasticity_id}`.
- [ ] Pass: the question is returned via the parent filter.

## T5 — Fail-closed
- [ ] Temporarily remove provider keys from `.env` and restart the backend.
- [ ] `POST` a question.
- [ ] Pass: the question is still created (200); no links are attached; a `grouping_match_failed` row is present in `system_warnings` (e.g. via the telemetry CLI or a SQL read).
```

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those tracked in `docs/testLog.md`. Note: tests that asserted the **old** substring behavior of `extract_question_topics` (e.g. `tests/unit/test_extract_question_topics.py`, and the topic-suggestion parts of `tests/integration/test_question_phase1.py`) are now obsolete because the matcher replaced that path. For each such failure: if it tests the removed substring path, delete or rewrite it against the engine; if it reveals a real regression, fix the code. Record any intentional test removals in the commit message. Do not weaken an assertion to make it pass.

- [ ] **Step 3: Update project status**

In `docs/projectStatus.md`:
- Update **Active focus** to: Groupings Phase 3a complete — question workflow cut over to the unified engine with a semantic/proposal matcher; LOG-062 closed server-side.
- Update **Next** to: Groupings Phase 3b (UI: proposal chips, hierarchy view, filter repoint).
- Update the Research epoch row's "Next" cell accordingly.
- Add the manual test plan to the reference table:
  `| `docs/testsPlans/manualTestPlan_groupings_phase3a.md` | Groupings Phase 3a manual test plan — live matcher, proposal confirm/dismiss, parent-filter rollup, fail-closed |`
- Mark LOG-062 resolved in `docs/testLog.md` (move Open→Resolved with a one-line resolution noting the Phase 3a matcher).

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_groupings_phase3a.md docs/projectStatus.md docs/testLog.md
git commit -m "docs: Groupings Phase 3a manual test plan; status + LOG-062 resolved"
```

---

## Phase 3a Done When

- New questions get LLM-based topic/concept suggestions (with proposals and parent rollup) via `suggest_groupings`; `extract_question_topics` is no longer called.
- The matcher fails closed (a `SystemWarning`, no partial writes) when no provider can serve `agent.extract.groupings`.
- `_question_detail`, the `?topic_id=` filter, and the six per-question link routes operate on `grouping_links`; the response contract is unchanged except for the additive `proposed` field.
- The proposal lifecycle works end-to-end through the existing PATCH/DELETE routes (confirm activates; dismiss cleans up orphan proposals).
- `/api/research/groupings` GET/POST/PATCH exist with 422 on invariant/unknown-type violations.
- Migration `018` seeds the `plasticity`/`stroke` hierarchy idempotently.
- `uv run pytest tests/ -q` is green (obsolete substring-path tests removed/rewritten, no real regressions).

## Out of Scope for 3a (Phase 3b / later)

- UI: proposal "new" chips, hierarchy/curation view, repointing the `executeSQL` filter query → **Phase 3b**.
- Migrating papers/datasets/notes/bundles consumers off legacy tables → **Phase 4**.
- Dropping legacy `topics`/`concepts`/join tables → **Phase 5**.
