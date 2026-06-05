"""Learning Plans store: proposed->confirmed plans with per-step progress.

State lives on the rows (learning_plans.status, plan_steps.lifecycle); there is
no separate proposals table. No FK constraints (DuckDB-safe); integrity is
enforced here.
"""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from neurodb.db import get_session
from neurodb.db.grouping_store import get_groupings_for_anchor
from neurodb.research.grouping_matcher import run_suggest_groupings
from neurodb.schema import GroupingLink, LearningPlan, Paper, PlanStep


def _now() -> str:
    return datetime.now(UTC).isoformat()


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


def _pending_change_count(steps: list[PlanStep]) -> int:
    return sum(1 for s in steps if s.lifecycle in ("proposed", "proposed_removal"))


def _plan_steps(session: Session, plan_id: int) -> list[PlanStep]:
    return session.execute(
        select(PlanStep).where(PlanStep.plan_id == plan_id)
    ).scalars().all()


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
        plan_id = plan.id
        _add_steps(session, plan_id, steps, start_index=0)
        session.commit()
    run_suggest_groupings(
        engine, anchor_type="learning_plan", anchor_id=plan_id,
        anchor_text=f"{title}\n{origin_prompt}", gtypes=("topic", "concept"),
    )
    return {"id": plan_id, "status": "proposed", "step_count": len(steps)}


def get_plan(engine: Engine, plan_id: int) -> dict | None:
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            return None
        steps = session.execute(
            select(PlanStep).where(PlanStep.plan_id == plan_id).order_by(PlanStep.order_index)
        ).scalars().all()
        groupings = get_groupings_for_anchor(session, "learning_plan", plan_id)
        return {
            "id": plan.id, "title": plan.title, "origin_prompt": plan.origin_prompt,
            "origin_agent": plan.origin_agent, "research_question_id": plan.research_question_id,
            "status": plan.status, "created_at": plan.created_at, "updated_at": plan.updated_at,
            "percent_complete": _percent_complete(steps),
            "pending_change_count": _pending_change_count(steps),
            "groupings": groupings,
            "steps": [_step_dict(s) for s in steps],
        }


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


def _resolve_read_paper(session: Session, source: dict) -> int:
    """Dedup a read-step source into papers; return paper_id. Mirrors queue_source.

    Imported lazily: normalize_title lives in agents.tutor_agent, which (via the
    shared learning-plan tools) imports this module — a top-level import here
    would create a circular import.
    """
    from neurodb.agents.tutor_agent import normalize_title

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
        steps = _plan_steps(session, plan_id)
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
        for s in _plan_steps(session, plan_id):
            session.delete(s)
        session.delete(plan)
        session.commit()
        return True


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
                "pending_change_count": _pending_change_count(steps),
            })
        return out


def _max_order_index(session: Session, plan_id: int) -> int:
    rows = session.execute(
        select(PlanStep.order_index).where(PlanStep.plan_id == plan_id)
    ).scalars().all()
    return max(rows) if rows else -1


def propose_plan_update(engine: Engine, *, plan_id: int, add_steps: list[dict] | None = None,
                        remove_step_ids: list[int] | None = None) -> dict:
    with get_session(engine) as session:
        plan = session.get(LearningPlan, plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        if add_steps:
            next_index = _max_order_index(session, plan_id) + 1
            _add_steps(session, plan_id, add_steps, start_index=next_index)
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
        steps = _plan_steps(session, plan_id)
        _confirm_step_rows(session, steps)
        plan = session.get(LearningPlan, plan_id)
        if plan is not None:
            plan.updated_at = _now()
        session.commit()
    return get_plan(engine, plan_id)


def dismiss_pending_changes(engine: Engine, plan_id: int) -> dict:
    with get_session(engine) as session:
        steps = _plan_steps(session, plan_id)
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
        for s in _plan_steps(session, plan_id):
            session.delete(s)
        session.delete(plan)
        session.commit()
        return True
