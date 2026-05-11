"""FastAPI routes for research metrics, questions, hypotheses, and reviews."""
from __future__ import annotations

import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_research_stores, get_task_store
from neurodb.api.schemas.research import Hypothesis, ResearchQuestion
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.research_tools import (
    get_knowledge_growth_metrics,
    list_hypotheses,
    list_research_questions,
)
from neurodb.schema import ResearchHypothesis

router = APIRouter()


@router.get("/metrics")
def get_metrics(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> dict:
    """Return current knowledge-growth metrics without persisting a snapshot."""
    stores = get_research_stores(request)
    return get_knowledge_growth_metrics(
        engine,
        vector_store=stores["vector_store"],
        knowledge_store=stores["knowledge_store"],
        context_store=stores["context_store"],
        persist=False,
    )


@router.post("/metrics/snapshot")
def post_metrics_snapshot(
    request: Request,
    engine: Engine = Depends(get_engine),
) -> dict:
    """Persist a knowledge-growth snapshot and return the dict with snapshot_id."""
    stores = get_research_stores(request)
    return get_knowledge_growth_metrics(
        engine,
        vector_store=stores["vector_store"],
        knowledge_store=stores["knowledge_store"],
        context_store=stores["context_store"],
        persist=True,
    )


@router.get("/questions")
def get_questions(
    engine: Engine = Depends(get_engine),
    status: str = "all",
) -> list[ResearchQuestion]:
    """Return research questions, optionally filtered by status."""
    questions = list_research_questions(engine, status)
    return [ResearchQuestion.model_validate(q) for q in questions]


@router.get("/hypotheses")
def get_hypotheses(
    engine: Engine = Depends(get_engine),
    status: str = "all",
) -> list[Hypothesis]:
    """Return research hypotheses, optionally filtered by status."""
    hypotheses = list_hypotheses(engine, status)
    return [Hypothesis.model_validate(h) for h in hypotheses]


@router.post("/hypotheses/{hypothesis_id}/review")
def review_hypothesis(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
    tasks: dict[str, TaskRecord] = Depends(get_task_store),
) -> dict[str, str]:
    with get_session(engine) as session:
        hyp = session.get(ResearchHypothesis, hypothesis_id)
        if hyp is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found",
            )

    task_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    tasks[task_id] = TaskRecord(
        task_id=task_id,
        status="running",
        result=None,
        error=None,
        started_at=now.isoformat(),
        timeout_at=(now + timedelta(seconds=180)).isoformat(),
    )

    def run() -> None:
        try:
            from neurodb.config.provider_factory import build_provider_clients
            from neurodb.config.task_router import TaskRouter
            from neurodb.research.hypothesis_review import run_hypothesis_review

            route = TaskRouter(build_provider_clients()).route("research.hypothesis_review")
            result = run_hypothesis_review(
                hypothesis_id=hypothesis_id,
                engine=engine,
                model_client=route.model_client,
                model_provider=route.provider,
                model=route.model_id,
                max_tokens=route.max_tokens,
            )
            tasks[task_id].status = "done"
            tasks[task_id].result = result
        except Exception as exc:
            tasks[task_id].status = "failed"
            tasks[task_id].error = str(exc)[:400]

    threading.Thread(target=run, daemon=True).start()
    return {"task_id": task_id}
