# Groupings Phase 2 — Type-Agnostic Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the type-agnostic store engine over the `groupings` / `grouping_links` tables — get/create, link lifecycle, search/list, anchor lookup, single-level hierarchy with invariant guard, and rollup helpers — with **no consumer switched** to it yet.

**Architecture:** A new store module `src/neurodb/db/grouping_store.py` mirroring the conventions of `topic_store.py` (session-first functions, `select()`, `_now()`, idempotent `link_*`, `bool`-returning `update`/`unlink`, dict-returning reads). A tiny `src/neurodb/db/grouping_types.py` holds the in-code type registry and the typed errors. The single-level hierarchy invariant is enforced in Python and raised as `GroupingHierarchyError` (no DB constraint — consistent with the LOG-037 no-FK decision; DuckDB rejects UPDATE on FK-referenced rows and re-parenting needs UPDATE). Routes, `create_question`, and agents are untouched; Phase 3 cuts the question workflow over and maps the typed error to HTTP 422.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 ORM, DuckDB (runtime) / SQLite in-memory (tests), pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` (Phase 2).

**Prerequisite:** Phase 1 is implemented (commit `b9bb250`): `Grouping` / `GroupingLink` ORM models exist in `src/neurodb/schema.py` (lines 591 / 613) and migration `017` is registered in `src/neurodb/db.py`.

**Conventions discovered in this codebase (follow exactly):**
- Store functions live in `src/neurodb/db/*.py`, take `session: Session` first, use `select(...)`, and a module-local `_now()` returning `datetime.now(UTC).isoformat()`.
- `link_*` helpers are idempotent (SELECT-then-insert, no-op if present). `update_*`/`unlink_*` return `bool` (`True` if a row was found).
- Store **unit tests** use an in-memory SQLite engine with a `session` fixture: `create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)`, `Base.metadata.create_all(engine)`, `with Session(engine) as s: yield s`. See `tests/unit/test_topic_store.py` for the template.
- Run the suite with `uv run pytest tests/ -q`. A single test: `uv run pytest tests/unit/test_x.py::test_y -v`.

**Public API delivered by this plan (locked signatures — keep consistent across tasks):**

| Function | Signature |
|---|---|
| `get_or_create_grouping` | `(session, gtype, name, *, description=None, status="active") -> Grouping` |
| `get_grouping` | `(session, grouping_id) -> Grouping \| None` |
| `list_groupings` | `(session, *, gtype=None, status=None) -> list[dict]` |
| `search_groupings` | `(session, gtype, query, limit=10) -> list[dict]` |
| `link_grouping` | `(session, grouping_id, anchor_type, anchor_id, *, status="confirmed") -> None` |
| `update_link_status` | `(session, grouping_id, anchor_type, anchor_id, status) -> bool` |
| `unlink_grouping` | `(session, grouping_id, anchor_type, anchor_id) -> bool` |
| `get_groupings_for_anchor` | `(session, anchor_type, anchor_id, *, status=None) -> list[dict]` |
| `set_parent` | `(session, grouping_id, parent_id) -> Grouping` (raises `GroupingHierarchyError`) |
| `get_children` | `(session, parent_id) -> list[Grouping]` |
| `resolve_filter_ids` | `(session, grouping_id) -> list[int]` |
| `rollup_parents` | `(session, grouping_ids) -> list[int]` |

---

### Task 1: Type registry + typed errors

**Files:**
- Create: `src/neurodb/db/grouping_types.py`
- Test: `tests/unit/test_grouping_types.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_grouping_types.py`:

```python
"""Unit tests for the grouping type registry and typed errors (Groupings Phase 2)."""
import pytest

from neurodb.db.grouping_types import (
    GROUPING_TYPES,
    GroupingHierarchyError,
    UnknownGroupingType,
    require_known_type,
)


def test_registry_has_topic_and_concept():
    assert set(GROUPING_TYPES) >= {"topic", "concept"}
    assert GROUPING_TYPES["topic"].display == "Topic"
    assert GROUPING_TYPES["topic"].allow_agent_proposal is True
    assert GROUPING_TYPES["concept"].display == "Concept"


def test_require_known_type_accepts_registered():
    require_known_type("topic")  # must not raise
    require_known_type("concept")


def test_require_known_type_rejects_unknown():
    with pytest.raises(UnknownGroupingType):
        require_known_type("method")


def test_error_types_are_value_errors():
    assert issubclass(UnknownGroupingType, ValueError)
    assert issubclass(GroupingHierarchyError, ValueError)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_types.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.db.grouping_types'`.

- [ ] **Step 3: Create the module**

Create `src/neurodb/db/grouping_types.py`:

```python
"""Type registry and typed errors for the unified groupings engine.

Valid grouping types live here, not in the DB. Adding a type is one line and
costs zero schema. Per-type policy (e.g. whether the agent may propose new
groupings of this type) travels on the spec.
"""
from dataclasses import dataclass


@dataclass(frozen=True)
class GroupingTypeSpec:
    display: str
    allow_agent_proposal: bool


GROUPING_TYPES: dict[str, GroupingTypeSpec] = {
    "topic": GroupingTypeSpec(display="Topic", allow_agent_proposal=True),
    "concept": GroupingTypeSpec(display="Concept", allow_agent_proposal=True),
    # future: "method", "brain_region", "disease", "question_type" — add a line, no schema change
}


class UnknownGroupingType(ValueError):
    """Raised when a grouping type is not in GROUPING_TYPES."""


class GroupingHierarchyError(ValueError):
    """Raised when a re-parent operation would violate the single-level invariant."""


def require_known_type(gtype: str) -> None:
    if gtype not in GROUPING_TYPES:
        raise UnknownGroupingType(f"Unknown grouping type: {gtype!r}")
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_grouping_types.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_types.py tests/unit/test_grouping_types.py
git commit -m "feat(groupings): type registry and typed errors for the engine"
```

---

### Task 2: Create/read/search groupings

**Files:**
- Create: `src/neurodb/db/grouping_store.py`
- Test: `tests/unit/test_grouping_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_grouping_store.py`:

```python
"""Unit tests for the type-agnostic grouping engine (Groupings Phase 2)."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.db.grouping_types import GroupingHierarchyError, UnknownGroupingType
from neurodb.db.grouping_store import (
    get_or_create_grouping,
    get_grouping,
    list_groupings,
    search_groupings,
)


@pytest.fixture
def session():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def test_get_or_create_creates_then_dedups(session):
    g1 = get_or_create_grouping(session, "topic", "plasticity", description="d")
    g2 = get_or_create_grouping(session, "topic", "plasticity")
    assert g1.id == g2.id
    assert g1.type == "topic"
    assert g1.status == "active"
    assert g1.description == "d"


def test_same_name_different_type_are_distinct(session):
    gt = get_or_create_grouping(session, "topic", "memory")
    gc = get_or_create_grouping(session, "concept", "memory")
    assert gt.id != gc.id


def test_get_or_create_rejects_unknown_type(session):
    with pytest.raises(UnknownGroupingType):
        get_or_create_grouping(session, "method", "fMRI")


def test_get_or_create_strips_name(session):
    g = get_or_create_grouping(session, "topic", "  stroke  ")
    assert g.name == "stroke"


def test_get_grouping(session):
    g = get_or_create_grouping(session, "topic", "stroke")
    assert get_grouping(session, g.id).name == "stroke"
    assert get_grouping(session, 999999) is None


def test_list_groupings_filters(session):
    get_or_create_grouping(session, "topic", "stroke")
    get_or_create_grouping(session, "topic", "plasticity", status="proposed")
    get_or_create_grouping(session, "concept", "LTP")
    topics = list_groupings(session, gtype="topic")
    assert {r["name"] for r in topics} == {"stroke", "plasticity"}
    active_topics = list_groupings(session, gtype="topic", status="active")
    assert {r["name"] for r in active_topics} == {"stroke"}
    assert len(list_groupings(session)) == 3


def test_search_groupings_scoped_to_type(session):
    get_or_create_grouping(session, "topic", "stroke recovery", description="rehab")
    get_or_create_grouping(session, "concept", "stroke marker")
    hits = search_groupings(session, "topic", "stroke")
    assert [h["name"] for h in hits] == ["stroke recovery"]
    by_desc = search_groupings(session, "topic", "rehab")
    assert [h["name"] for h in by_desc] == ["stroke recovery"]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.db.grouping_store'`.

- [ ] **Step 3: Create the module with create/read/search functions**

Create `src/neurodb/db/grouping_store.py`:

```python
"""DB epoch — type-agnostic grouping engine over groupings/grouping_links.

Store layer for the unified taxonomy (Groupings Phase 2). No consumer is
switched to this engine yet; Phase 3 cuts the question workflow over and maps
GroupingHierarchyError to HTTP 422.
"""
from datetime import UTC, datetime

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from neurodb.schema import Grouping, GroupingLink
from neurodb.db.grouping_types import GroupingHierarchyError, require_known_type


def _now() -> str:
    return datetime.now(UTC).isoformat()


def get_or_create_grouping(
    session: Session,
    gtype: str,
    name: str,
    *,
    description: str | None = None,
    status: str = "active",
) -> Grouping:
    """Fetch or create a grouping, deduped by (type, name). Rejects unknown types."""
    require_known_type(gtype)
    name = name.strip()
    existing = session.execute(
        select(Grouping).where(Grouping.type == gtype, Grouping.name == name)
    ).scalar_one_or_none()
    if existing is not None:
        return existing
    now = _now()
    grouping = Grouping(
        type=gtype, name=name, parent_id=None, status=status,
        description=description, created_at=now, updated_at=now,
    )
    session.add(grouping)
    session.flush()
    return grouping


def get_grouping(session: Session, grouping_id: int) -> Grouping | None:
    return session.get(Grouping, grouping_id)


def list_groupings(
    session: Session, *, gtype: str | None = None, status: str | None = None
) -> list[dict]:
    stmt = select(Grouping)
    if gtype is not None:
        stmt = stmt.where(Grouping.type == gtype)
    if status is not None:
        stmt = stmt.where(Grouping.status == status)
    rows = session.execute(stmt.order_by(Grouping.type, Grouping.name)).scalars().all()
    return [
        {"id": g.id, "type": g.type, "name": g.name,
         "parent_id": g.parent_id, "status": g.status, "description": g.description}
        for g in rows
    ]


def search_groupings(session: Session, gtype: str, query: str, limit: int = 10) -> list[dict]:
    q = f"%{query}%"
    rows = session.execute(
        select(Grouping)
        .where(Grouping.type == gtype)
        .where(or_(Grouping.name.ilike(q), Grouping.description.ilike(q)))
        .order_by(Grouping.name)
        .limit(limit)
    ).scalars().all()
    return [
        {"id": g.id, "name": g.name, "description": g.description,
         "status": g.status, "parent_id": g.parent_id}
        for g in rows
    ]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_grouping_store.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_store.py tests/unit/test_grouping_store.py
git commit -m "feat(groupings): get_or_create/get/list/search grouping store functions"
```

---

### Task 3: Link lifecycle + anchor lookup

**Files:**
- Modify: `src/neurodb/db/grouping_store.py` (append)
- Test: `tests/unit/test_grouping_store.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_grouping_store.py` (and extend the import from `grouping_store` at the top to add `link_grouping`, `update_link_status`, `unlink_grouping`, `get_groupings_for_anchor`):

```python
def test_link_grouping_is_idempotent(session):
    from neurodb.db.grouping_store import link_grouping
    g = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, g.id, "question", 7, status="pending")
    link_grouping(session, g.id, "question", 7, status="confirmed")  # no-op insert
    from sqlalchemy import text
    n = session.execute(
        text("SELECT COUNT(*) FROM grouping_links WHERE grouping_id=:g AND anchor_type='question' AND anchor_id=7"),
        {"g": g.id},
    ).scalar()
    assert n == 1
    # status stays as first insert (idempotent link does not overwrite)
    s = session.execute(
        text("SELECT status FROM grouping_links WHERE grouping_id=:g AND anchor_id=7"),
        {"g": g.id},
    ).scalar()
    assert s == "pending"


def test_update_link_status(session):
    from neurodb.db.grouping_store import link_grouping, update_link_status
    g = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, g.id, "question", 7, status="pending")
    assert update_link_status(session, g.id, "question", 7, "confirmed") is True
    assert update_link_status(session, g.id, "question", 999, "confirmed") is False
    rows = get_groupings_for_anchor(session, "question", 7)
    assert rows[0]["link_status"] == "confirmed"


def test_unlink_grouping(session):
    from neurodb.db.grouping_store import link_grouping, unlink_grouping
    g = get_or_create_grouping(session, "topic", "stroke")
    link_grouping(session, g.id, "question", 7)
    assert unlink_grouping(session, g.id, "question", 7) is True
    assert unlink_grouping(session, g.id, "question", 7) is False
    assert get_groupings_for_anchor(session, "question", 7) == []


def test_get_groupings_for_anchor_filters_status(session):
    from neurodb.db.grouping_store import link_grouping
    gt = get_or_create_grouping(session, "topic", "stroke")
    gc = get_or_create_grouping(session, "concept", "LTP")
    link_grouping(session, gt.id, "question", 7, status="confirmed")
    link_grouping(session, gc.id, "question", 7, status="pending")
    all_rows = get_groupings_for_anchor(session, "question", 7)
    assert {r["name"] for r in all_rows} == {"stroke", "LTP"}
    confirmed = get_groupings_for_anchor(session, "question", 7, status="confirmed")
    assert {r["name"] for r in confirmed} == {"stroke"}
```

Also add `get_groupings_for_anchor` to the top-level import line so the helper calls resolve:

```python
from neurodb.db.grouping_store import (
    get_or_create_grouping,
    get_grouping,
    get_groupings_for_anchor,
    list_groupings,
    search_groupings,
)
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_store.py -k "link or anchor" -v`
Expected: FAIL — `ImportError: cannot import name 'link_grouping'` (functions not defined yet).

- [ ] **Step 3: Append the link-lifecycle functions**

Append to `src/neurodb/db/grouping_store.py`:

```python
def link_grouping(
    session: Session,
    grouping_id: int,
    anchor_type: str,
    anchor_id: int,
    *,
    status: str = "confirmed",
) -> None:
    """Create a grouping→anchor link. Idempotent on (grouping_id, anchor_type, anchor_id)."""
    exists = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if exists is None:
        session.add(GroupingLink(
            grouping_id=grouping_id, anchor_type=anchor_type, anchor_id=anchor_id,
            status=status, created_at=_now(),
        ))
        session.flush()


def update_link_status(
    session: Session, grouping_id: int, anchor_type: str, anchor_id: int, status: str
) -> bool:
    """Update status on an existing link. Returns True if a link was found."""
    row = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    row.status = status
    session.flush()
    return True


def unlink_grouping(
    session: Session, grouping_id: int, anchor_type: str, anchor_id: int
) -> bool:
    """Delete a link. Returns True if a link was found."""
    row = session.execute(
        select(GroupingLink).where(
            GroupingLink.grouping_id == grouping_id,
            GroupingLink.anchor_type == anchor_type,
            GroupingLink.anchor_id == anchor_id,
        )
    ).scalar_one_or_none()
    if row is None:
        return False
    session.delete(row)
    session.flush()
    return True


def get_groupings_for_anchor(
    session: Session, anchor_type: str, anchor_id: int, *, status: str | None = None
) -> list[dict]:
    """Groupings linked to an anchor, each carrying its link status."""
    stmt = (
        select(Grouping, GroupingLink.status)
        .join(GroupingLink, GroupingLink.grouping_id == Grouping.id)
        .where(GroupingLink.anchor_type == anchor_type, GroupingLink.anchor_id == anchor_id)
    )
    if status is not None:
        stmt = stmt.where(GroupingLink.status == status)
    rows = session.execute(stmt).all()
    return [
        {"id": g.id, "type": g.type, "name": g.name,
         "parent_id": g.parent_id, "link_status": link_status}
        for g, link_status in rows
    ]
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_grouping_store.py -v`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_store.py tests/unit/test_grouping_store.py
git commit -m "feat(groupings): link lifecycle and anchor lookup in the engine"
```

---

### Task 4: Hierarchy — invariant guard + rollup helpers

**Files:**
- Modify: `src/neurodb/db/grouping_store.py` (append)
- Test: `tests/unit/test_grouping_store.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_grouping_store.py`:

```python
def test_set_parent_happy_path_and_clear(session):
    from neurodb.db.grouping_store import set_parent, get_children
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "topic", "neuroplasticity")
    set_parent(session, child.id, parent.id)
    assert get_grouping(session, child.id).parent_id == parent.id
    assert [g.name for g in get_children(session, parent.id)] == ["neuroplasticity"]
    set_parent(session, child.id, None)
    assert get_grouping(session, child.id).parent_id is None


def test_set_parent_rejects_self(session):
    from neurodb.db.grouping_store import set_parent
    g = get_or_create_grouping(session, "topic", "plasticity")
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, g.id, g.id)


def test_set_parent_rejects_cross_type(session):
    from neurodb.db.grouping_store import set_parent
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "concept", "LTP")
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, child.id, parent.id)


def test_set_parent_rejects_grandchild(session):
    from neurodb.db.grouping_store import set_parent
    top = get_or_create_grouping(session, "topic", "plasticity")
    mid = get_or_create_grouping(session, "topic", "neuroplasticity")
    leaf = get_or_create_grouping(session, "topic", "circuit plasticity")
    set_parent(session, mid.id, top.id)
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, leaf.id, mid.id)  # mid already has a parent


def test_set_parent_rejects_parenting_a_parent(session):
    from neurodb.db.grouping_store import set_parent
    top = get_or_create_grouping(session, "topic", "plasticity")
    mid = get_or_create_grouping(session, "topic", "neuroplasticity")
    other = get_or_create_grouping(session, "topic", "stroke")
    set_parent(session, mid.id, top.id)        # top now has a child
    with pytest.raises(GroupingHierarchyError):
        set_parent(session, top.id, other.id)  # top has children, cannot become a child


def test_resolve_filter_ids(session):
    from neurodb.db.grouping_store import set_parent, resolve_filter_ids
    parent = get_or_create_grouping(session, "topic", "plasticity")
    c1 = get_or_create_grouping(session, "topic", "neuroplasticity")
    c2 = get_or_create_grouping(session, "topic", "circuit plasticity")
    set_parent(session, c1.id, parent.id)
    set_parent(session, c2.id, parent.id)
    assert set(resolve_filter_ids(session, parent.id)) == {parent.id, c1.id, c2.id}
    # a leaf resolves to just itself
    assert resolve_filter_ids(session, c1.id) == [c1.id]


def test_rollup_parents(session):
    from neurodb.db.grouping_store import set_parent, rollup_parents
    parent = get_or_create_grouping(session, "topic", "plasticity")
    child = get_or_create_grouping(session, "topic", "neuroplasticity")
    top_only = get_or_create_grouping(session, "topic", "stroke")
    set_parent(session, child.id, parent.id)
    # child rolls up to include parent
    assert set(rollup_parents(session, [child.id])) == {child.id, parent.id}
    # top-level grouping is unchanged
    assert rollup_parents(session, [top_only.id]) == [top_only.id]
    # parent already present → no duplicate
    assert sorted(rollup_parents(session, [child.id, parent.id])) == sorted([child.id, parent.id])
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_grouping_store.py -k "parent or rollup or filter_ids" -v`
Expected: FAIL — `ImportError: cannot import name 'set_parent'`.

- [ ] **Step 3: Append the hierarchy functions**

Append to `src/neurodb/db/grouping_store.py`:

```python
def get_children(session: Session, parent_id: int) -> list[Grouping]:
    return list(session.execute(
        select(Grouping).where(Grouping.parent_id == parent_id).order_by(Grouping.name)
    ).scalars().all())


def set_parent(session: Session, grouping_id: int, parent_id: int | None) -> Grouping:
    """Set or clear a grouping's parent, enforcing the single-level invariant.

    Raises GroupingHierarchyError when the operation would create a grandchild,
    cross types, parent a grouping that already has children, or self-parent.
    """
    child = session.get(Grouping, grouping_id)
    if child is None:
        raise GroupingHierarchyError(f"Grouping {grouping_id} not found")

    if parent_id is None:
        child.parent_id = None
        child.updated_at = _now()
        session.flush()
        return child

    if parent_id == grouping_id:
        raise GroupingHierarchyError("A grouping cannot be its own parent")

    parent = session.get(Grouping, parent_id)
    if parent is None:
        raise GroupingHierarchyError(f"Parent grouping {parent_id} not found")
    if parent.type != child.type:
        raise GroupingHierarchyError(
            f"Parent type {parent.type!r} != child type {child.type!r}"
        )
    if parent.parent_id is not None:
        raise GroupingHierarchyError("Parent must be top-level (no grandchildren)")
    if get_children(session, grouping_id):
        raise GroupingHierarchyError("Cannot parent a grouping that already has children")

    child.parent_id = parent_id
    child.updated_at = _now()
    session.flush()
    return child


def resolve_filter_ids(session: Session, grouping_id: int) -> list[int]:
    """Return {grouping_id} ∪ direct children — the id set a parent-filter matches."""
    child_ids = [g.id for g in get_children(session, grouping_id)]
    return [grouping_id, *child_ids]


def rollup_parents(session: Session, grouping_ids: list[int]) -> list[int]:
    """Given matched grouping ids, add each one's parent (deduped). Order preserved."""
    result = list(grouping_ids)
    seen = set(grouping_ids)
    for gid in grouping_ids:
        g = session.get(Grouping, gid)
        if g is not None and g.parent_id is not None and g.parent_id not in seen:
            result.append(g.parent_id)
            seen.add(g.parent_id)
    return result
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_grouping_store.py -v`
Expected: PASS (18 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db/grouping_store.py tests/unit/test_grouping_store.py
git commit -m "feat(groupings): single-level hierarchy guard and rollup helpers"
```

---

### Task 5: Full suite green (no regressions)

**Files:** none (verification only).

- [ ] **Step 1: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those already tracked in `docs/testLog.md`. The new files add `4 + 18 = 22` passing tests; nothing else should change because no consumer imports the engine yet.

- [ ] **Step 2: Confirm no consumer was switched**

Run: `git grep -n "grouping_store" -- src/neurodb`
Expected: matches only inside `src/neurodb/db/grouping_store.py` itself (and `grouping_types.py` import). No route, agent, or `create_question` reference — that is Phase 3.

- [ ] **Step 3: Update project status**

Per CLAUDE.md sync rules, this engine landing changes the Research epoch's active focus. In `docs/projectStatus.md`, update the Research epoch row's "Next" cell to reflect Groupings Phase 2 complete and Phase 3 (question cutover + semantic matcher) next. (The reference-table row for this plan was already added when the plan was created.)

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: Groupings Phase 2 engine complete; status + plan reference"
```

---

## Phase 2 Done When

- `grouping_store.py` exposes the full locked API (create/read/search, link lifecycle, anchor lookup, hierarchy guard, rollup helpers) with `GROUPING_TYPES` and typed errors in `grouping_types.py`.
- The single-level invariant is enforced in `set_parent` and raised as `GroupingHierarchyError` (all four violation paths unit-tested).
- No consumer reads the engine yet (verified by `git grep`); legacy tables remain the source of truth.
- `uv run pytest tests/ -q` is green (no new failures vs. `docs/testLog.md`).

## Out of Scope for Phase 2 (later phases)

- The `GET/POST/PATCH /api/research/groupings` routes and the 422 mapping of `GroupingHierarchyError` → **Phase 3** (they ship with the UI repoint that consumes them).
- `suggest_groupings` semantic/agent matcher, the `agent.extract.groupings` task type, the proposal lifecycle, and seeding the `plasticity`/`stroke` hierarchy as data → **Phase 3**.
- Repointing `_question_detail`, the question filter, and `extract_question_topics` → **Phase 3**.
- Migrating papers/datasets/notes/bundles consumers → **Phase 4**; dropping legacy tables → **Phase 5**.
