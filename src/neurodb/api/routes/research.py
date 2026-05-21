"""FastAPI routes for research metrics, questions, hypotheses, and reviews."""
from __future__ import annotations

import json
import threading
import uuid
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import Engine

from neurodb.api.deps import get_engine, get_research_stores, get_task_store
from neurodb.api.schemas.research import (
    ClaimItem,
    EvidenceLinkItem,
    Hypothesis,
    HypothesisReviewItem,
    ResearchGapItem,
    ResearchQuestion,
)
from neurodb.api.tasks import TaskRecord
from neurodb.db import get_session
from neurodb.research_tools import (
    get_knowledge_growth_metrics,
    list_hypotheses,
    list_hypothesis_reviews,
    list_research_questions,
    update_hypothesis_review_status,
)
from neurodb.schema import Claim, EvidenceLink, HypothesisReview, ResearchGap, ResearchHypothesis

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
    status: list[str] | None = Query(default=None),
) -> list[ResearchQuestion]:
    """Return research questions, optionally filtered by status."""
    questions = list_research_questions(engine, status or "all")
    return [ResearchQuestion.model_validate(q) for q in questions]


@router.get("/claims", response_model=list[ClaimItem])
def get_claims(
    engine: Engine = Depends(get_engine),
) -> list[ClaimItem]:
    """Return all claims."""
    with get_session(engine) as session:
        rows = session.query(Claim).order_by(Claim.created_at.desc()).all()
        return [ClaimItem.model_validate(row) for row in rows]


@router.get("/gaps", response_model=list[ResearchGapItem])
def get_gaps(
    engine: Engine = Depends(get_engine),
) -> list[ResearchGapItem]:
    """Return all research gaps."""
    with get_session(engine) as session:
        rows = session.query(ResearchGap).order_by(ResearchGap.created_at.desc()).all()
        return [ResearchGapItem.model_validate(row) for row in rows]


@router.get("/hypotheses")
def get_hypotheses(
    engine: Engine = Depends(get_engine),
    status: list[str] | None = Query(default=None),
) -> list[Hypothesis]:
    """Return research hypotheses, optionally filtered by status."""
    hypotheses = list_hypotheses(engine, status or "all")
    return [_hypothesis_item(h) for h in hypotheses]


@router.get("/hypotheses/{hypothesis_id}/evidence-links", response_model=list[EvidenceLinkItem])
def get_evidence_links(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
) -> list[EvidenceLinkItem]:
    """Return evidence links for a hypothesis."""
    with get_session(engine) as session:
        hypothesis = session.get(ResearchHypothesis, hypothesis_id)
        if hypothesis is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found",
            )
        rows = (
            session.query(EvidenceLink)
            .filter(EvidenceLink.hypothesis_id == hypothesis_id)
            .order_by(EvidenceLink.created_at.desc())
            .all()
        )
        return [EvidenceLinkItem.model_validate(row) for row in rows]


@router.get("/hypotheses/{hypothesis_id}/reviews", response_model=list[HypothesisReviewItem])
def get_hypothesis_reviews(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
) -> list[HypothesisReviewItem]:
    """Return persisted review artifacts for a hypothesis."""
    with get_session(engine) as session:
        hypothesis = session.get(ResearchHypothesis, hypothesis_id)
        if hypothesis is None:
            raise HTTPException(
                status_code=404,
                detail=f"Hypothesis {hypothesis_id} not found",
            )
    reviews = list_hypothesis_reviews(engine, hypothesis_id)
    return [HypothesisReviewItem.model_validate(review) for review in reviews]


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


@router.post("/reviews/{review_id}/accept", response_model=HypothesisReviewItem)
def accept_hypothesis_review(
    review_id: int,
    engine: Engine = Depends(get_engine),
) -> HypothesisReviewItem:
    result = update_hypothesis_review_status(engine, review_id, "accepted")
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return _review_item(engine, review_id)


@router.post("/reviews/{review_id}/dismiss", response_model=HypothesisReviewItem)
def dismiss_hypothesis_review(
    review_id: int,
    engine: Engine = Depends(get_engine),
) -> HypothesisReviewItem:
    result = update_hypothesis_review_status(engine, review_id, "dismissed")
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return _review_item(engine, review_id)


def _json_list(value: str | None) -> list[object]:
    if not value:
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def _hypothesis_item(row: ResearchHypothesis) -> Hypothesis:
    return Hypothesis(
        id=row.id,
        title=row.title,
        mechanism=row.mechanism,
        evidence_json=_json_list(row.evidence_json),
        predictions_json=_json_list(row.predictions_json),
        datasets_json=_json_list(row.datasets_json),
        confounds_json=_json_list(row.confounds_json),
        limitations=row.limitations,
        status=row.status,
        created_at=row.created_at,
    )


def _review_item(engine: Engine, review_id: int) -> HypothesisReviewItem:
    with get_session(engine) as session:
        row = session.get(HypothesisReview, review_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"review {review_id} not found")
        return HypothesisReviewItem(
            id=row.id,
            hypothesis_id=row.hypothesis_id,
            model=row.model,
            critique_text=row.critique_text,
            unsupported_claims=_json_list(row.unsupported_claims_json),
            missing_confounds=_json_list(row.missing_confounds_json),
            suggested_revisions=row.suggested_revisions,
            status=row.status,
            created_at=row.created_at,
        )
