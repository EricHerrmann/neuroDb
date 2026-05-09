"""FastAPI routes for research metrics, questions, and hypotheses.

UI-1 Backend API Shell — Task 6.
"""
from fastapi import APIRouter, Depends, Request
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_research_stores
from neurodb.api.schemas.research import Hypothesis, ResearchQuestion
from neurodb.research_tools import (
    get_knowledge_growth_metrics,
    list_hypotheses,
    list_research_questions,
)

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
