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
        plan_id = plan.id
        _add_steps(session, plan_id, steps, start_index=0)
        session.commit()
    return {"id": plan_id, "status": "proposed", "step_count": len(steps)}


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
