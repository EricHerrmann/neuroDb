# Learning Plans Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let either agent propose a multi-step study plan that, once user-approved, becomes a tracked, grouping-linked item in the Study Log with per-step progress and agent-proposed updates.

**Architecture:** Two new tables (`learning_plans`, `plan_steps`) in the Research epoch, with state-on-rows lifecycle (`proposed`/`confirmed`/`proposed_removal`). A pure store module drives creation, the proposed→confirmed gate, read-step paper resolution (on confirm), and progress. Topic/concept cross-reference reuses the existing grouping engine via `anchor_type='learning_plan'`. Two shared agent tools register on both the tutor and research agents; a research-router API surface backs a new Study Log "Plans" section.

**Tech Stack:** Python, SQLAlchemy (DuckDB runtime / SQLite in-memory tests), FastAPI, pytest, ruff; React + Vitest frontend.

**Spec:** `docs/superpowers/specs/2026-06-05-learning-plans-design.md`

---

## File Structure

- `src/neurodb/schema.py` — add `LearningPlan` + `PlanStep` ORM models.
- `src/neurodb/db.py` — add `_migration_022_learning_plans`; register `22`.
- `src/neurodb/db/__init__.py` — re-export `_migration_022_learning_plans`.
- `src/neurodb/research/learning_plans.py` — **new** store module (all plan logic + read-paper resolution helper).
- `src/neurodb/agents/learning_plan_tools.py` — **new** shared tool schemas + executors used by both agents.
- `src/neurodb/agents/tutor_agent.py`, `src/neurodb/agents/research_agent.py` — register the two tools + dispatch.
- `src/neurodb/api/routes/research.py` — add the `/plans` routes.
- `src/neurodb/api/schemas/research.py` — add plan request/response models.
- `frontend/src/api/client.ts`, `frontend/src/api/types.ts` — plan API client + types.
- `frontend/src/pages/StudyLogPanel.tsx` — add the Plans section.
- `frontend/src/components/PlanCard.tsx`, `frontend/src/components/PlanDetail.tsx` — **new** plan UI units.
- Tests alongside each (paths in tasks).

Conventions to follow (verified in-repo): no FK constraints on new tables (DuckDB-safe; see `_migration_021`); migrations use `CREATE TABLE IF NOT EXISTS`; store functions take a `Session` and live behind `get_session(engine)`; `link_grouping(session, grouping_id, anchor_type, anchor_id, status=)` with free-text `anchor_type`; agent tools run in-process via `get_session(self._engine)`.

---

## Task 1: Schema models + migration 022

**Files:**
- Modify: `src/neurodb/schema.py`
- Modify: `src/neurodb/db.py` (after `_migration_021_drop_legacy_groupings_tables`; register `22`)
- Modify: `src/neurodb/db/__init__.py` (re-export)
- Test: `tests/unit/test_migration_022_learning_plans.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_022_learning_plans.py`:

```python
"""Unit tests for migration 022: learning_plans + plan_steps tables."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_022_learning_plans
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_022_registered():
    assert _MIGRATIONS.get(22) is _migration_022_learning_plans


def test_creates_tables_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        _migration_022_learning_plans(conn)
        _migration_022_learning_plans(conn)  # second run must not raise
        conn.commit()
    names = set(inspect(eng).get_table_names())
    assert {"learning_plans", "plan_steps"} <= names


def test_full_migration_chain_includes_022():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 22
    names = set(inspect(eng).get_table_names())
    assert {"learning_plans", "plan_steps"} <= names
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_022_learning_plans.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_022_learning_plans'`.

- [ ] **Step 3: Add ORM models to `src/neurodb/schema.py`**

Append near the other Research-epoch models (match the file's `Mapped`/`mapped_column` style):

```python
class LearningPlan(Base):
    __tablename__ = "learning_plans"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    origin_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    origin_agent: Mapped[str] = mapped_column(String(16), nullable=False)  # 'tutor' | 'research'
    origin_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    research_question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class PlanStep(Base):
    __tablename__ = "plan_steps"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    plan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    order_index: Mapped[int] = mapped_column(Integer, nullable=False)
    step_type: Mapped[str] = mapped_column(String(16), nullable=False)  # 'read' | 'action'
    paper_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    source_ref: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON for proposed read steps
    action_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    lifecycle: Mapped[str] = mapped_column(String(16), nullable=False, default="proposed")
    progress: Mapped[str] = mapped_column(String(16), nullable=False, default="todo")
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

Confirm `Integer`, `String`, `Text`, `Mapped`, `mapped_column` are already imported at the top of `schema.py` (they are, used by existing models); do not add duplicate imports.

- [ ] **Step 4: Add the migration in `src/neurodb/db.py`** (immediately after `_migration_021_drop_legacy_groupings_tables`):

```python
def _migration_022_learning_plans(conn) -> None:
    """Create learning_plans and plan_steps tables (Learning Plans feature)."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS learning_plans (
            id INTEGER PRIMARY KEY,
            title TEXT NOT NULL,
            origin_prompt TEXT NOT NULL,
            origin_agent VARCHAR(16) NOT NULL,
            origin_session_id INTEGER,
            research_question_id INTEGER,
            status VARCHAR(16) NOT NULL DEFAULT 'proposed',
            created_at VARCHAR(32) NOT NULL,
            updated_at VARCHAR(32) NOT NULL
        )
    """))
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_learning_plans_status ON learning_plans (status)"
    ))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS plan_steps (
            id INTEGER PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            order_index INTEGER NOT NULL,
            step_type VARCHAR(16) NOT NULL,
            paper_id INTEGER,
            source_ref TEXT,
            action_text TEXT,
            lifecycle VARCHAR(16) NOT NULL DEFAULT 'proposed',
            progress VARCHAR(16) NOT NULL DEFAULT 'todo',
            note TEXT,
            created_at VARCHAR(32) NOT NULL,
            updated_at VARCHAR(32) NOT NULL
        )
    """))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_plan_steps_plan_id ON plan_steps (plan_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_plan_steps_lifecycle ON plan_steps (lifecycle)"))
```

Register it in the `_MIGRATIONS` dict (after the `21:` line):

```python
    22: _migration_022_learning_plans,
```

- [ ] **Step 5: Re-export in `src/neurodb/db/__init__.py`** — add a line mirroring the existing migration re-exports:

```python
_migration_022_learning_plans = _db_legacy._migration_022_learning_plans
```

(Use the exact alias prefix already used in that file for the other `_migration_0XX` re-exports.)

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_migration_022_learning_plans.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py src/neurodb/db/__init__.py tests/unit/test_migration_022_learning_plans.py
git commit -m "feat(db): learning_plans + plan_steps tables (migration 022)"
```

---

## Task 2: Store — propose, get, list

**Files:**
- Create: `src/neurodb/research/learning_plans.py`
- Test: `tests/unit/test_learning_plans_store.py`

The store uses `get_session(engine)` internally and returns plain dicts. `source_ref` holds JSON for proposed read steps.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_learning_plans_store.py`:

```python
import json
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.research.learning_plans import propose_plan, get_plan, list_plans


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def _steps():
    return [
        {"type": "read", "source": {"title": "LTP Review", "source_type": "paper", "topic_context": "plasticity"}},
        {"type": "action", "action_text": "Summarize the mechanism"},
    ]


def test_propose_persists_proposed_plan_and_steps():
    eng = _engine()
    out = propose_plan(eng, title="Plasticity primer", origin_prompt="explain plasticity",
                       origin_agent="tutor", steps=_steps())
    plan = get_plan(eng, out["id"])
    assert plan["status"] == "proposed"
    assert len(plan["steps"]) == 2
    assert all(s["lifecycle"] == "proposed" for s in plan["steps"])
    read = next(s for s in plan["steps"] if s["step_type"] == "read")
    assert read["paper_id"] is None
    assert json.loads(read["source_ref"])["title"] == "LTP Review"
    assert plan["steps"][0]["order_index"] == 0 and plan["steps"][1]["order_index"] == 1


def test_list_plans_filters_by_status():
    eng = _engine()
    propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor", steps=_steps())
    assert len(list_plans(eng, status="proposed")) == 1
    assert list_plans(eng, status="active") == []


def test_percent_complete_zero_for_new_plan():
    eng = _engine()
    out = propose_plan(eng, title="A", origin_prompt="a", origin_agent="research", steps=_steps())
    assert get_plan(eng, out["id"])["percent_complete"] == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_learning_plans_store.py -v`
Expected: FAIL — module/function not found.

- [ ] **Step 3: Implement `src/neurodb/research/learning_plans.py`** (this task's functions only):

```python
"""Learning Plans store: proposed->confirmed plans with per-step progress.

State lives on the rows (learning_plans.status, plan_steps.lifecycle); there is
no separate proposals table. No FK constraints (DuckDB-safe); integrity is
enforced here.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from neurodb.db import get_session
from neurodb.schema import LearningPlan, PlanStep


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _step_dict(s: PlanStep) -> dict:
    return {
        "id": s.id, "plan_id": s.plan_id, "order_index": s.order_index,
        "step_type": s.step_type, "paper_id": s.paper_id, "source_ref": s.source_ref,
        "action_text": s.action_text, "lifecycle": s.lifecycle, "progress": s.progress,
        "note": s.note,
    }


def _percent_complete(steps: list[PlanStep]) -> int:
    confirmed = [s for s in steps if s.lifecycle == "confirmed"]
    denom = [s for s in confirmed if s.progress != "skipped"]
    if not denom:
        return 0
    done = [s for s in denom if s.progress == "done"]
    return round(100 * len(done) / len(denom))


def _add_steps(session: Session, plan_id: int, steps: list[dict], start_index: int) -> None:
    for offset, step in enumerate(steps):
        stype = step["type"]
        source_ref = json.dumps(step["source"]) if stype == "read" else None
        session.add(PlanStep(
            plan_id=plan_id, order_index=start_index + offset, step_type=stype,
            paper_id=None, source_ref=source_ref,
            action_text=step.get("action_text") if stype == "action" else None,
            lifecycle="proposed", progress="todo", note=None,
            created_at=_now(), updated_at=_now(),
        ))


def propose_plan(engine: Engine, *, title: str, origin_prompt: str, origin_agent: str,
                 steps: list[dict], origin_session_id: int | None = None,
                 research_question_id: int | None = None) -> dict:
    with get_session(engine) as session:
        plan = LearningPlan(
            title=title, origin_prompt=origin_prompt, origin_agent=origin_agent,
            origin_session_id=origin_session_id, research_question_id=research_question_id,
            status="proposed", created_at=_now(), updated_at=_now(),
        )
        session.add(plan)
        session.flush()
        _add_steps(session, plan.id, steps, start_index=0)
        session.commit()
        return {"id": plan.id, "status": "proposed", "step_count": len(steps)}


def get_plan(engine: Engine, plan_id: int) -> dict | None:
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            return None
        steps = session.execute(
            select(PlanStep).where(PlanStep.plan_id == plan_id).order_by(PlanStep.order_index)
        ).scalars().all()
        return {
            "id": plan.id, "title": plan.title, "origin_prompt": plan.origin_prompt,
            "origin_agent": plan.origin_agent, "research_question_id": plan.research_question_id,
            "status": plan.status, "created_at": plan.created_at, "updated_at": plan.updated_at,
            "percent_complete": _percent_complete(steps),
            "pending_change_count": sum(1 for s in steps if s.lifecycle in ("proposed", "proposed_removal")),
            "steps": [_step_dict(s) for s in steps],
        }


def list_plans(engine: Engine, status: str | None = None) -> list[dict]:
    with get_session(engine) as session:
        stmt = select(LearningPlan)
        if status is not None:
            stmt = stmt.where(LearningPlan.status == status)
        plans = session.execute(stmt.order_by(LearningPlan.created_at.desc())).scalars().all()
        out = []
        for plan in plans:
            steps = session.execute(
                select(PlanStep).where(PlanStep.plan_id == plan.id)
            ).scalars().all()
            out.append({
                "id": plan.id, "title": plan.title, "status": plan.status,
                "origin_agent": plan.origin_agent, "created_at": plan.created_at,
                "percent_complete": _percent_complete(steps),
                "step_count": sum(1 for s in steps if s.lifecycle == "confirmed"),
                "pending_change_count": sum(1 for s in steps if s.lifecycle in ("proposed", "proposed_removal")),
            })
        return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_learning_plans_store.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/research/learning_plans.py tests/unit/test_learning_plans_store.py
git commit -m "feat(research): learning-plans store — propose, get, list"
```

---

## Task 3: Store — confirm/dismiss plan + read-paper resolution

**Files:**
- Modify: `src/neurodb/research/learning_plans.py`
- Test: `tests/unit/test_learning_plans_confirm.py`

Read steps resolve to a `papers` row on confirm via a local dedup helper that mirrors the tutor's `_execute_queue_source` logic (`normalize_title` + dedup by `doi`/`normalized_title`, else create `status='pending'`). This keeps a dismissed plan free of Knowledge Library artifacts.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_learning_plans_confirm.py`:

```python
from sqlalchemy import create_engine, func, select
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db, get_session
from neurodb.schema import Paper
from neurodb.research.learning_plans import propose_plan, confirm_plan, dismiss_plan, get_plan


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def _steps():
    return [
        {"type": "read", "source": {"title": "LTP Review", "source_type": "paper", "topic_context": "plasticity"}},
        {"type": "action", "action_text": "Summarize"},
    ]


def _paper_count(eng):
    with get_session(eng) as s:
        return s.execute(select(func.count()).select_from(Paper)).scalar_one()


def test_confirm_activates_and_resolves_read_paper():
    eng = _engine()
    pid = propose_plan(eng, title="P", origin_prompt="p", origin_agent="tutor", steps=_steps())["id"]
    assert _paper_count(eng) == 0  # nothing queued at propose time
    confirm_plan(eng, pid)
    plan = get_plan(eng, pid)
    assert plan["status"] == "active"
    assert all(s["lifecycle"] == "confirmed" for s in plan["steps"])
    read = next(s for s in plan["steps"] if s["step_type"] == "read")
    assert read["paper_id"] is not None and read["source_ref"] is None
    assert _paper_count(eng) == 1


def test_confirm_dedups_existing_paper():
    eng = _engine()
    # Two plans referencing the same source title -> one paper.
    p1 = propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor", steps=_steps())["id"]
    p2 = propose_plan(eng, title="B", origin_prompt="b", origin_agent="tutor", steps=_steps())["id"]
    confirm_plan(eng, p1)
    confirm_plan(eng, p2)
    assert _paper_count(eng) == 1


def test_dismiss_proposed_plan_leaves_no_papers():
    eng = _engine()
    pid = propose_plan(eng, title="P", origin_prompt="p", origin_agent="tutor", steps=_steps())["id"]
    assert dismiss_plan(eng, pid) is True
    assert get_plan(eng, pid) is None
    assert _paper_count(eng) == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_learning_plans_confirm.py -v`
Expected: FAIL — `confirm_plan`/`dismiss_plan` not defined.

- [ ] **Step 3: Add to `src/neurodb/research/learning_plans.py`**:

```python
from neurodb.literature_client import normalize_title  # used for read-step dedup
from neurodb.schema import Paper


def _resolve_read_paper(session: Session, source: dict) -> int:
    """Dedup a read-step source into papers; return paper_id. Mirrors queue_source."""
    title = (source.get("title") or "").strip()
    normalized = normalize_title(title)
    existing = session.execute(
        select(Paper).where(Paper.normalized_title == normalized)
    ).scalar_one_or_none()
    if existing is not None:
        return existing.id
    row = Paper(
        title=title, normalized_title=normalized, doi=None, url=None,
        source_type=source.get("source_type") or "paper",
        topic_context=source.get("topic_context") or "",
        status="pending", queued_at=_now(),
    )
    session.add(row)
    session.flush()
    return row.id


def _confirm_step_rows(session: Session, steps: list[PlanStep]) -> None:
    """Activate proposed steps in place, resolving read papers; delete proposed_removal."""
    for s in steps:
        if s.lifecycle == "proposed":
            if s.step_type == "read" and s.paper_id is None and s.source_ref:
                s.paper_id = _resolve_read_paper(session, json.loads(s.source_ref))
                s.source_ref = None
            s.lifecycle = "confirmed"
            s.updated_at = _now()
        elif s.lifecycle == "proposed_removal":
            session.delete(s)


def confirm_plan(engine: Engine, plan_id: int) -> dict:
    """Confirm a proposed plan: status->active, all proposed steps->confirmed."""
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None or plan.status != "proposed":
            raise ValueError(f"Plan {plan_id} is not in 'proposed' state")
        steps = session.execute(select(PlanStep).where(PlanStep.plan_id == plan_id)).scalars().all()
        _confirm_step_rows(session, steps)
        plan.status = "active"
        plan.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def dismiss_plan(engine: Engine, plan_id: int) -> bool:
    """Delete a proposed plan and its steps. No Knowledge Library side effects."""
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            return False
        for s in session.execute(select(PlanStep).where(PlanStep.plan_id == plan_id)).scalars().all():
            session.delete(s)
        session.delete(plan)
        session.commit()
        return True
```

> Verify `normalize_title` is importable from `neurodb.literature_client` (it is used by `tutor_agent.py`); if its module path differs, import it from the same module `tutor_agent.py` imports it from.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_learning_plans_confirm.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/research/learning_plans.py tests/unit/test_learning_plans_confirm.py
git commit -m "feat(research): confirm/dismiss plan with read-paper resolution on confirm"
```

---

## Task 4: Store — updates, pending changes, step ops, edit/delete

**Files:**
- Modify: `src/neurodb/research/learning_plans.py`
- Test: `tests/unit/test_learning_plans_updates.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_learning_plans_updates.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.research.learning_plans import (
    propose_plan, confirm_plan, get_plan, propose_plan_update,
    confirm_pending_changes, dismiss_pending_changes, set_step_progress,
    update_plan, delete_plan,
)


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def _active_plan(eng):
    pid = propose_plan(eng, title="P", origin_prompt="p", origin_agent="research",
                       steps=[{"type": "action", "action_text": "first"}])["id"]
    confirm_plan(eng, pid)
    return pid


def test_propose_update_adds_proposed_step_without_touching_active():
    eng = _engine()
    pid = _active_plan(eng)
    propose_plan_update(eng, plan_id=pid, add_steps=[{"type": "action", "action_text": "second"}])
    plan = get_plan(eng, pid)
    assert plan["pending_change_count"] == 1
    confirmed = [s for s in plan["steps"] if s["lifecycle"] == "confirmed"]
    proposed = [s for s in plan["steps"] if s["lifecycle"] == "proposed"]
    assert len(confirmed) == 1 and len(proposed) == 1


def test_propose_removal_then_confirm_changes_deletes_step():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    propose_plan_update(eng, plan_id=pid, remove_step_ids=[step_id])
    assert get_plan(eng, pid)["steps"][0]["lifecycle"] == "proposed_removal"
    confirm_pending_changes(eng, pid)
    assert get_plan(eng, pid)["steps"] == []


def test_dismiss_changes_reverts_removal_and_drops_additions():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    propose_plan_update(eng, plan_id=pid, add_steps=[{"type": "action", "action_text": "x"}],
                        remove_step_ids=[step_id])
    dismiss_pending_changes(eng, pid)
    plan = get_plan(eng, pid)
    assert len(plan["steps"]) == 1 and plan["steps"][0]["lifecycle"] == "confirmed"


def test_step_progress_drives_percent_complete():
    eng = _engine()
    pid = _active_plan(eng)
    step_id = get_plan(eng, pid)["steps"][0]["id"]
    set_step_progress(eng, step_id, "done")
    assert get_plan(eng, pid)["percent_complete"] == 100


def test_update_and_delete_plan():
    eng = _engine()
    pid = _active_plan(eng)
    update_plan(eng, pid, title="Renamed", status="paused")
    plan = get_plan(eng, pid)
    assert plan["title"] == "Renamed" and plan["status"] == "paused"
    assert delete_plan(eng, pid) is True
    assert get_plan(eng, pid) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_learning_plans_updates.py -v`
Expected: FAIL — new functions not defined.

- [ ] **Step 3: Add to `src/neurodb/research/learning_plans.py`**:

```python
def _max_order_index(session: Session, plan_id: int) -> int:
    rows = session.execute(select(PlanStep.order_index).where(PlanStep.plan_id == plan_id)).scalars().all()
    return max(rows) if rows else -1


def propose_plan_update(engine: Engine, *, plan_id: int, add_steps: list[dict] | None = None,
                        remove_step_ids: list[int] | None = None) -> dict:
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        if add_steps:
            _add_steps(session, plan_id, add_steps, start_index=_max_order_index(session, plan_id) + 1)
        for step_id in (remove_step_ids or []):
            step = session.get(PlanStep, step_id)
            if step is not None and step.plan_id == plan_id and step.lifecycle == "confirmed":
                step.lifecycle = "proposed_removal"
                step.updated_at = _now()
        plan.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def confirm_pending_changes(engine: Engine, plan_id: int) -> dict:
    with get_session(engine) as session:
        steps = session.execute(select(PlanStep).where(PlanStep.plan_id == plan_id)).scalars().all()
        _confirm_step_rows(session, steps)
        plan = session.get(LearningPlan, plan_id)
        if plan is not None:
            plan.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def dismiss_pending_changes(engine: Engine, plan_id: int) -> dict:
    with get_session(engine) as session:
        steps = session.execute(select(PlanStep).where(PlanStep.plan_id == plan_id)).scalars().all()
        for s in steps:
            if s.lifecycle == "proposed":
                session.delete(s)
            elif s.lifecycle == "proposed_removal":
                s.lifecycle = "confirmed"
                s.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def set_step_progress(engine: Engine, step_id: int, progress: str, note: str | None = None) -> bool:
    if progress not in ("todo", "in_progress", "done", "skipped"):
        raise ValueError(f"Invalid progress: {progress!r}")
    with get_session(engine) as session:
        step = session.get(PlanStep, step_id)
        if step is None:
            return False
        step.progress = progress
        if note is not None:
            step.note = note
        step.updated_at = _now()
        session.commit()
        return True


def confirm_step(engine: Engine, step_id: int) -> bool:
    with get_session(engine) as session:
        step = session.get(PlanStep, step_id)
        if step is None or step.lifecycle not in ("proposed", "proposed_removal"):
            return False
        _confirm_step_rows(session, [step])
        session.commit()
        return True


def dismiss_step(engine: Engine, step_id: int) -> bool:
    with get_session(engine) as session:
        step = session.get(PlanStep, step_id)
        if step is None:
            return False
        if step.lifecycle == "proposed":
            session.delete(step)
        elif step.lifecycle == "proposed_removal":
            step.lifecycle = "confirmed"
            step.updated_at = _now()
        else:
            return False
        session.commit()
        return True


def update_plan(engine: Engine, plan_id: int, *, title: str | None = None,
                status: str | None = None, step_order: list[int] | None = None) -> dict | None:
    if status is not None and status not in ("active", "paused", "done"):
        raise ValueError(f"Invalid status: {status!r}")
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            return None
        if title is not None:
            plan.title = title
        if status is not None:
            plan.status = status
        if step_order:
            for index, sid in enumerate(step_order):
                step = session.get(PlanStep, sid)
                if step is not None and step.plan_id == plan_id:
                    step.order_index = index
        plan.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def delete_plan(engine: Engine, plan_id: int) -> bool:
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            return False
        for s in session.execute(select(PlanStep).where(PlanStep.plan_id == plan_id)).scalars().all():
            session.delete(s)
        session.delete(plan)
        session.commit()
        return True
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_learning_plans_updates.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/research/learning_plans.py tests/unit/test_learning_plans_updates.py
git commit -m "feat(research): plan updates, pending-change confirm/dismiss, step ops"
```

---

## Task 5: Grouping integration — topic suggestions + cross-reference

**Files:**
- Modify: `src/neurodb/research/learning_plans.py`
- Test: `tests/unit/test_learning_plans_groupings.py`

`propose_plan` triggers the matcher (fail-closed wrapper, mocked in tests); `get_plan` includes confirmed grouping links and an `appears_in_n_plans` count for shared topics.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_learning_plans_groupings.py`:

```python
from unittest.mock import patch
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db, get_session
from neurodb.db.grouping_store import get_or_create_grouping, link_grouping
from neurodb.research.learning_plans import propose_plan, get_plan, plans_sharing_grouping


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def test_propose_runs_grouping_matcher():
    eng = _engine()
    with patch("neurodb.research.learning_plans.run_suggest_groupings") as mock_run:
        out = propose_plan(eng, title="Plasticity", origin_prompt="explain plasticity",
                           origin_agent="tutor", steps=[{"type": "action", "action_text": "x"}])
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["anchor_type"] == "learning_plan"
    assert kwargs["anchor_id"] == out["id"]
    assert kwargs["gtypes"] == ("topic", "concept")


def test_get_plan_includes_confirmed_groupings_and_cross_ref():
    eng = _engine()
    with patch("neurodb.research.learning_plans.run_suggest_groupings"):
        p1 = propose_plan(eng, title="A", origin_prompt="a", origin_agent="tutor",
                          steps=[{"type": "action", "action_text": "x"}])["id"]
        p2 = propose_plan(eng, title="B", origin_prompt="b", origin_agent="tutor",
                          steps=[{"type": "action", "action_text": "y"}])["id"]
    with get_session(eng) as s:
        g = get_or_create_grouping(s, "topic", "plasticity")
        link_grouping(s, g.id, "learning_plan", p1, status="confirmed")
        link_grouping(s, g.id, "learning_plan", p2, status="confirmed")
        s.commit()
        gid = g.id
    plan = get_plan(eng, p1)
    names = [grp["name"] for grp in plan["groupings"]]
    assert "plasticity" in names
    assert plans_sharing_grouping(eng, gid) == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_learning_plans_groupings.py -v`
Expected: FAIL — `run_suggest_groupings` not wired / `groupings` key absent / `plans_sharing_grouping` undefined.

- [ ] **Step 3: Implement**

Add the import and matcher call to `propose_plan`, extend `get_plan`, and add the cross-ref query in `src/neurodb/research/learning_plans.py`:

```python
from neurodb.research.grouping_matcher import run_suggest_groupings
from neurodb.db.grouping_store import get_groupings_for_anchor
from neurodb.schema import GroupingLink
```

In `propose_plan`, after `session.commit()` and before `return`, add (outside the session block):

```python
    run_suggest_groupings(
        engine, anchor_type="learning_plan", anchor_id=plan_id,
        anchor_text=f"{title}\n{origin_prompt}", gtypes=("topic", "concept"),
    )
```

To make `plan_id` available outside the `with`, capture it inside: assign `plan_id = plan.id` before the commit and return using it. (Adjust `propose_plan` to store `plan_id` and return `{"id": plan_id, ...}`.)

In `get_plan`, before the return dict, add grouping links:

```python
        groupings = get_groupings_for_anchor(session, "learning_plan", plan_id)
```
and include `"groupings": groupings,` in the returned dict.

Add the cross-reference helper:

```python
def plans_sharing_grouping(engine: Engine, grouping_id: int) -> int:
    """Count distinct learning plans linked (confirmed) to a grouping."""
    with get_session(engine) as session:
        rows = session.execute(
            select(GroupingLink.anchor_id).where(
                GroupingLink.grouping_id == grouping_id,
                GroupingLink.anchor_type == "learning_plan",
                GroupingLink.status == "confirmed",
            )
        ).scalars().all()
        return len(set(rows))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_learning_plans_groupings.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Run the full store suite to catch regressions from the `propose_plan` refactor**

Run: `uv run pytest tests/unit/test_learning_plans_store.py tests/unit/test_learning_plans_confirm.py tests/unit/test_learning_plans_updates.py -v`
Expected: PASS. (The earlier store tests don't mock `run_suggest_groupings`; it is fail-closed, so with no providers configured it writes a SystemWarning and returns — verify those tests still pass; if the unmocked call slows tests, add `@patch` to the propose-based tests in those files.)

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/research/learning_plans.py tests/unit/test_learning_plans_groupings.py
git commit -m "feat(research): plan topic suggestions + shared-grouping cross-reference"
```

---

## Task 6: Shared agent tools on both agents

**Files:**
- Create: `src/neurodb/agents/learning_plan_tools.py`
- Modify: `src/neurodb/agents/tutor_agent.py`, `src/neurodb/agents/research_agent.py`
- Test: `tests/unit/test_learning_plan_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_learning_plan_tools.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import init_db
from neurodb.agents.learning_plan_tools import (
    LEARNING_PLAN_TOOLS, execute_propose_learning_plan, execute_update_learning_plan,
)
from neurodb.research.learning_plans import get_plan


def _engine():
    eng = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(eng)
    return eng


def test_tool_schemas_present_and_groq_safe():
    names = {t["name"] for t in LEARNING_PLAN_TOOLS}
    assert names == {"propose_learning_plan", "update_learning_plan"}
    for tool in LEARNING_PLAN_TOOLS:
        schema = tool["input_schema"]
        assert schema["type"] == "object"
        assert "properties" in schema and "required" in schema


def test_execute_propose_persists_proposed_plan():
    import json
    eng = _engine()
    out = json.loads(execute_propose_learning_plan(eng, {
        "title": "P", "origin_prompt": "p", "origin_agent": "tutor",
        "steps": [{"type": "action", "action_text": "x"}],
    }))
    assert get_plan(eng, out["id"])["status"] == "proposed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_learning_plan_tools.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Implement `src/neurodb/agents/learning_plan_tools.py`**

```python
"""Shared Learning Plans agent tools (registered on tutor + research agents)."""
from __future__ import annotations

import json

from sqlalchemy.engine import Engine

from neurodb.research.learning_plans import propose_plan, propose_plan_update

_STEP_ITEM = {
    "type": "object",
    "properties": {
        "type": {"type": "string", "enum": ["read", "action"]},
        "source": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "source_type": {"type": "string"},
                "topic_context": {"type": "string"},
            },
            "required": ["title"],
        },
        "action_text": {"type": "string"},
    },
    "required": ["type"],
}

LEARNING_PLAN_TOOLS = [
    {
        "name": "propose_learning_plan",
        "description": (
            "Propose a multi-step study plan for the user to review. Steps are ordered; "
            "each is a 'read' (a source to read) or an 'action' (a task). The plan is saved "
            "as 'proposed' until the user approves it in the Study Log."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "origin_prompt": {"type": "string"},
                "steps": {"type": "array", "items": _STEP_ITEM},
            },
            "required": ["title", "origin_prompt", "steps"],
        },
    },
    {
        "name": "update_learning_plan",
        "description": (
            "Propose changes to an existing plan: add steps and/or mark confirmed steps for "
            "removal. Changes are pending until the user confirms them."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "integer"},
                "add_steps": {"type": "array", "items": _STEP_ITEM},
                "remove_step_ids": {"type": "array", "items": {"type": "integer"}},
            },
            "required": ["plan_id"],
        },
    },
]


def execute_propose_learning_plan(engine: Engine, inputs: dict, *, origin_agent: str = "tutor",
                                  origin_session_id: int | None = None) -> str:
    agent = inputs.get("origin_agent", origin_agent)
    out = propose_plan(
        engine, title=inputs["title"], origin_prompt=inputs["origin_prompt"],
        origin_agent=agent, steps=inputs["steps"], origin_session_id=origin_session_id,
    )
    return json.dumps(out)


def execute_update_learning_plan(engine: Engine, inputs: dict) -> str:
    out = propose_plan_update(
        engine, plan_id=inputs["plan_id"],
        add_steps=inputs.get("add_steps"), remove_step_ids=inputs.get("remove_step_ids"),
    )
    return json.dumps({"id": out["id"], "pending_change_count": out["pending_change_count"]})
```

- [ ] **Step 4: Register on both agents**

In `src/neurodb/agents/research_agent.py`: add `from neurodb.agents.learning_plan_tools import LEARNING_PLAN_TOOLS, execute_propose_learning_plan, execute_update_learning_plan`; extend the module-level tool list with `*LEARNING_PLAN_TOOLS`; and in `_execute_tool_block` add:

```python
        if block.tool_name == "propose_learning_plan":
            return execute_propose_learning_plan(self._engine, block.tool_input, origin_agent="research")
        if block.tool_name == "update_learning_plan":
            return execute_update_learning_plan(self._engine, block.tool_input)
```

In `src/neurodb/agents/tutor_agent.py`: add the same import; append `*LEARNING_PLAN_TOOLS` to the tutor's tool list; and in the tutor's tool dispatch (where `queue_source` is handled, ~line 291) add:

```python
        if block.tool_name == "propose_learning_plan":
            return execute_propose_learning_plan(self._engine, block.tool_input, origin_agent="tutor")
        if block.tool_name == "update_learning_plan":
            return execute_update_learning_plan(self._engine, block.tool_input)
```

Match each agent's existing dispatch idiom (how `block.tool_name`/`block.tool_input` are accessed) exactly.

- [ ] **Step 5: Run tests + agent suites**

Run: `uv run pytest tests/unit/test_learning_plan_tools.py tests/unit/test_research_agent.py tests/unit/test_tutor_agent.py -v`
Expected: PASS (existing agent tests unaffected; new tool test passes).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/agents/learning_plan_tools.py src/neurodb/agents/tutor_agent.py src/neurodb/agents/research_agent.py tests/unit/test_learning_plan_tools.py
git commit -m "feat(agents): propose/update learning-plan tools on tutor + research agents"
```

---

## Task 7: API routes

**Files:**
- Modify: `src/neurodb/api/routes/research.py`, `src/neurodb/api/schemas/research.py`
- Test: `tests/integration/test_plan_routes.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_plan_routes.py`:

```python
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.research import router
from neurodb.db import init_db
from neurodb.research.learning_plans import propose_plan


def _client():
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    init_db(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = None
    app.state.context_store = None
    app.include_router(router, prefix="/api/research")
    return TestClient(app), engine


def test_list_and_get_and_confirm_plan():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    assert any(p["id"] == pid for p in client.get("/api/research/plans?status=proposed").json())
    assert client.get(f"/api/research/plans/{pid}").json()["status"] == "proposed"
    assert client.post(f"/api/research/plans/{pid}/confirm").status_code == 200
    assert client.get(f"/api/research/plans/{pid}").json()["status"] == "active"


def test_confirm_rejects_non_proposed_plan():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    client.post(f"/api/research/plans/{pid}/confirm")
    assert client.post(f"/api/research/plans/{pid}/confirm").status_code == 422


def test_step_progress_and_delete():
    client, engine = _client()
    pid = propose_plan(engine, title="P", origin_prompt="p", origin_agent="tutor",
                       steps=[{"type": "action", "action_text": "x"}])["id"]
    client.post(f"/api/research/plans/{pid}/confirm")
    step_id = client.get(f"/api/research/plans/{pid}").json()["steps"][0]["id"]
    assert client.patch(f"/api/research/plans/{pid}/steps/{step_id}", json={"progress": "done"}).status_code == 200
    assert client.get(f"/api/research/plans/{pid}").json()["percent_complete"] == 100
    assert client.delete(f"/api/research/plans/{pid}").status_code == 200
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/integration/test_plan_routes.py -v`
Expected: FAIL — routes return 404.

- [ ] **Step 3: Add request models to `src/neurodb/api/schemas/research.py`**

```python
class StepProgressUpdate(BaseModel):
    progress: str | None = None
    note: str | None = None
    lifecycle_action: str | None = None  # 'confirm' | 'dismiss' for a single proposed step


class PlanPatch(BaseModel):
    title: str | None = None
    status: str | None = None
    step_order: list[int] | None = None
```

- [ ] **Step 4: Add routes to `src/neurodb/api/routes/research.py`**

Use the existing engine accessor in that file (the question routes read `request.app.state.engine` — match that exact idiom). Map each route to the store:

```python
from neurodb.research import learning_plans as lp

@router.get("/plans")
def list_plans_route(request: Request, status: str | None = None):
    return lp.list_plans(request.app.state.engine, status=status)

@router.get("/plans/{plan_id}")
def get_plan_route(request: Request, plan_id: int):
    plan = lp.get_plan(request.app.state.engine, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.post("/plans/{plan_id}/confirm")
def confirm_plan_route(request: Request, plan_id: int):
    try:
        return lp.confirm_plan(request.app.state.engine, plan_id)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

@router.post("/plans/{plan_id}/confirm-changes")
def confirm_changes_route(request: Request, plan_id: int):
    return lp.confirm_pending_changes(request.app.state.engine, plan_id)

@router.post("/plans/{plan_id}/dismiss-changes")
def dismiss_changes_route(request: Request, plan_id: int):
    return lp.dismiss_pending_changes(request.app.state.engine, plan_id)

@router.patch("/plans/{plan_id}")
def patch_plan_route(request: Request, plan_id: int, body: PlanPatch):
    plan = lp.update_plan(request.app.state.engine, plan_id, title=body.title,
                          status=body.status, step_order=body.step_order)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.patch("/plans/{plan_id}/steps/{step_id}")
def patch_step_route(request: Request, plan_id: int, step_id: int, body: StepProgressUpdate):
    engine = request.app.state.engine
    if body.lifecycle_action == "confirm":
        lp.confirm_step(engine, step_id)
    elif body.lifecycle_action == "dismiss":
        lp.dismiss_step(engine, step_id)
    if body.progress is not None or body.note is not None:
        lp.set_step_progress(engine, step_id, body.progress or "todo", note=body.note)
    plan = lp.get_plan(engine, plan_id)
    if plan is None:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan

@router.delete("/plans/{plan_id}")
def delete_plan_route(request: Request, plan_id: int):
    if not lp.delete_plan(request.app.state.engine, plan_id):
        raise HTTPException(status_code=404, detail="Plan not found")
    return {"status": "deleted", "id": plan_id}
```

Ensure `Request`, `HTTPException`, and the `PlanPatch`/`StepProgressUpdate` imports are present in `research.py`. The `set_step_progress` call validates `progress`; guard it so a pure `lifecycle_action` call without `progress` does not reset progress (the `if body.progress is not None` check above handles this).

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/integration/test_plan_routes.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/research.py src/neurodb/api/schemas/research.py tests/integration/test_plan_routes.py
git commit -m "feat(api): learning-plan routes on the research router"
```

---

## Task 8: Frontend — Study Log Plans section

**Files:**
- Modify: `frontend/src/api/types.ts`, `frontend/src/api/client.ts`
- Create: `frontend/src/components/PlanCard.tsx`, `frontend/src/components/PlanDetail.tsx`
- Modify: `frontend/src/pages/StudyLogPanel.tsx`
- Test: `frontend/src/pages/StudyLogPanel.plans.test.tsx`

- [ ] **Step 1: Add types** to `frontend/src/api/types.ts` (match existing interface style):

```ts
export interface PlanStep {
  id: number; plan_id: number; order_index: number;
  step_type: "read" | "action"; paper_id: number | null;
  source_ref: string | null; action_text: string | null;
  lifecycle: "proposed" | "confirmed" | "proposed_removal";
  progress: "todo" | "in_progress" | "done" | "skipped"; note: string | null;
}
export interface PlanSummary {
  id: number; title: string; status: string; origin_agent: string;
  percent_complete: number; step_count: number; pending_change_count: number;
}
export interface PlanDetail extends PlanSummary {
  origin_prompt: string; steps: PlanStep[]; groupings: { id: number; type: string; name: string; link_status: string }[];
}
```

- [ ] **Step 2: Add API client functions** to `frontend/src/api/client.ts` (match the existing `fetch` wrapper / base path used by the other research calls):

```ts
export const listPlans = (status?: string) =>
  apiGet<PlanSummary[]>(`/api/research/plans${status ? `?status=${status}` : ""}`);
export const getPlan = (id: number) => apiGet<PlanDetail>(`/api/research/plans/${id}`);
export const confirmPlan = (id: number) => apiPost(`/api/research/plans/${id}/confirm`);
export const confirmPlanChanges = (id: number) => apiPost(`/api/research/plans/${id}/confirm-changes`);
export const dismissPlanChanges = (id: number) => apiPost(`/api/research/plans/${id}/dismiss-changes`);
export const patchPlan = (id: number, body: object) => apiPatch(`/api/research/plans/${id}`, body);
export const patchPlanStep = (id: number, stepId: number, body: object) =>
  apiPatch(`/api/research/plans/${id}/steps/${stepId}`, body);
export const deletePlan = (id: number) => apiDelete(`/api/research/plans/${id}`);
```

Use the actual helper names in `client.ts` (`apiGet`/`apiPost`/`apiPatch`/`apiDelete` or their real equivalents — check the file first and match).

- [ ] **Step 3: Write the failing test**

Create `frontend/src/pages/StudyLogPanel.plans.test.tsx` (mirror the render/mock style of `StudyLogPanel.test.tsx`):

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import { describe, it, expect, vi, beforeEach } from "vitest";
import StudyLogPanel from "./StudyLogPanel";
import * as client from "../api/client";

describe("StudyLogPanel — Plans section", () => {
  beforeEach(() => {
    vi.spyOn(client, "listPlans").mockResolvedValue([
      { id: 1, title: "Plasticity primer", status: "proposed", origin_agent: "tutor",
        percent_complete: 0, step_count: 0, pending_change_count: 0 },
    ] as any);
  });

  it("renders a proposed plan card with title and status", async () => {
    render(<StudyLogPanel />);
    await waitFor(() => expect(screen.getByText("Plasticity primer")).toBeInTheDocument());
    expect(screen.getByText(/proposed/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 4: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/pages/StudyLogPanel.plans.test.tsx`
Expected: FAIL — no Plans section / `listPlans` not used.

- [ ] **Step 5: Implement the components and wire the section**

`frontend/src/components/PlanCard.tsx`: render title, status badge, `percent_complete` bar, `step_count`, and a "N pending changes" badge when `pending_change_count > 0`; for `status === "proposed"` show Confirm/Dismiss buttons calling `confirmPlan`/`deletePlan`. `frontend/src/components/PlanDetail.tsx`: render ordered steps (read→KL link, action→text), per-confirmed-step progress control (calls `patchPlanStep`), proposed steps with Confirm/Dismiss, `proposed_removal` struck-through with Keep/Remove, and topic chips from `groupings`. In `StudyLogPanel.tsx`, add a "Plans" section that calls `listPlans()` on mount and lists `PlanCard`s; selecting one loads `getPlan` into `PlanDetail`. Follow the panel's existing data-loading and section-layout patterns.

- [ ] **Step 6: Run frontend tests + build**

Run: `cd frontend && npx vitest run src/pages/StudyLogPanel.plans.test.tsx && npm run build`
Expected: test PASS; TypeScript + Vite build clean.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/api/types.ts frontend/src/api/client.ts frontend/src/components/PlanCard.tsx frontend/src/components/PlanDetail.tsx frontend/src/pages/StudyLogPanel.tsx frontend/src/pages/StudyLogPanel.plans.test.tsx
git commit -m "feat(ui): Study Log Plans section — list, detail, confirm/dismiss, progress"
```

---

## Task 9: Manual test plan, gate, and status sync

**Files:**
- Create: `docs/testsPlans/manualTestPlan_learning_plans.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan** at `docs/testsPlans/manualTestPlan_learning_plans.md`. Prerequisites (first item): `uv run pytest tests/ -q` (no new failures beyond `docs/testLog.md`), then `cd frontend && npm test`, then `npm run build`, then start backend (`uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`) and frontend (`cd frontend && npm run dev`). Cases (browser/live, not duplicating unit tests):
  - **T1** (tutor): in a tutor chat, explore a topic and ask for a study plan; a "Proposed — needs review" plan appears in the Study Log Plans section. Pass: plan visible with proposed steps and suggested topic chips.
  - **T2** (research agent): same from a research-agent chat. Pass: plan appears with `origin_agent` = research.
  - **T3** (confirm): confirm a proposed plan. Pass: status→Active; read-step sources now appear in Knowledge Library; topic chips confirmable.
  - **T4** (dismiss leaves no artifacts): dismiss a different proposed plan. Pass: plan gone; its read sources did **not** appear in Knowledge Library.
  - **T5** (progress): set step statuses; the % complete bar and "where am I" update; skipped steps excluded.
  - **T6** (agent update): ask an agent to add/remove steps on an active plan; pending changes show; confirm applies, dismiss reverts.
  - **T7** (cross-ref): a topic shared by two plans shows "appears in 2 plans."
  - **T8** (edit/remove): rename, pause, and delete a plan from the panel.
- [ ] **Step 2: Run the full automated gate**

Run: `uv run pytest tests/ -q` then `uv run ruff check src/ tests/` then `cd frontend && npm test && npm run build`
Expected: backend all green (no new failures); ruff introduces no new violations; frontend green; build clean.

- [ ] **Step 3: Status-doc sync** — in `docs/projectStatus.md`: set Active focus to "Learning Plans — implementation complete; manual verification pending"; update the Research epoch row; add the design spec, this plan, and the manual test plan to the reference table; remove the "learning plans" entry from **Deferred / Upcoming**; update the backend test count.

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_learning_plans.md docs/projectStatus.md
git commit -m "docs: Learning Plans manual test plan + status sync"
```

---

## Self-Review Notes

- **Spec coverage:** data model → Task 1; propose→confirm lifecycle (create) → Tasks 2–3; agent-update propose→confirm + step ops + % complete → Task 4; grouping anchor + cross-ref → Task 5; both-agent tools → Task 6; two distinct confirm endpoints + full API → Task 7; Study Log Plans section + chips → Task 8; manual plan + scope gate + status sync → Task 9. Deferred items are intentionally not built.
- **Read-paper-on-confirm** is enforced in Task 3 (`_resolve_read_paper` runs only inside `_confirm_step_rows`) and asserted by `test_dismiss_proposed_plan_leaves_no_papers`.
- **Type/name consistency:** store function names are reused verbatim across Tasks 2–7 (`propose_plan`, `confirm_plan`, `dismiss_plan`, `propose_plan_update`, `confirm_pending_changes`, `dismiss_pending_changes`, `set_step_progress`, `confirm_step`, `dismiss_step`, `update_plan`, `delete_plan`, `get_plan`, `list_plans`, `plans_sharing_grouping`); the `propose_plan` refactor in Task 5 (capturing `plan_id` for the post-commit matcher call) is called out so later tasks see the final signature.
- **Lint caveat:** the repo carries pre-existing ruff debt; the gate checks for *no new* violations, not a clean tree.
