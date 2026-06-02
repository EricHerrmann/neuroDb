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
    AddConceptLinkRequest,
    AddTopicLinkRequest,
    ClaimItem,
    CreateGroupingRequest,
    GroupingItem,
    PatchGroupingRequest,
    CreateQuestionRequest,
    EvidenceLinkItem,
    Hypothesis,
    HypothesisReviewItem,
    PatchLinkStatusRequest,
    ResearchGapItem,
    ResearchQuestion,
    ResearchQuestionDetail,
    UpdateQuestionRequest,
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


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


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
    topic_id: int | None = Query(default=None),
) -> list[ResearchQuestionDetail]:
    """Return research questions, optionally filtered by status and/or confirmed topic."""
    from sqlalchemy import select as _select
    from neurodb.schema import QuestionTopic, ResearchQuestion as ResearchQuestionORM
    with get_session(engine) as session:
        query = _select(ResearchQuestionORM)
        if status:
            query = query.where(ResearchQuestionORM.status.in_(status))
        if topic_id is not None:
            query = query.where(
                ResearchQuestionORM.id.in_(
                    _select(QuestionTopic.question_id).where(
                        QuestionTopic.topic_id == topic_id,
                        QuestionTopic.status == "confirmed",
                    )
                )
            )
        rows = session.execute(
            query.order_by(ResearchQuestionORM.created_at.desc())
        ).scalars().all()
    return [_question_detail(engine, r.id) for r in rows]


@router.post("/questions", response_model=ResearchQuestionDetail)
def create_question(
    body: CreateQuestionRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.research_tools import create_research_question
    result = create_research_question(
        engine,
        question=body.question,
        topic_context=body.topic_context,
        origin_session_id=body.origin_session_id,
    )
    if "error" in result:
        raise HTTPException(status_code=422, detail=result["error"])
    question_id = result["id"]

    def _extract():
        from neurodb.db import get_session as _gs
        from neurodb.db.topic_store import extract_question_topics
        with _gs(engine) as session:
            extract_question_topics(session, question_id, body.question)

    threading.Thread(target=_extract, daemon=True).start()
    return _question_detail(engine, question_id)


@router.put("/questions/{question_id}", response_model=ResearchQuestionDetail)
def update_question(
    question_id: int,
    body: UpdateQuestionRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.research_tools import update_research_question
    result = update_research_question(
        engine,
        question_id,
        question=body.question,
        topic_context=body.topic_context,
    )
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}", status_code=204)
def delete_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.research_tools import delete_research_question
    result = delete_research_question(engine, question_id)
    if "error" in result:
        raise HTTPException(status_code=404, detail=result["error"])


@router.get("/questions/{question_id}", response_model=ResearchQuestionDetail)
def get_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    return _question_detail(engine, question_id)


@router.post("/questions/{question_id}/topics", response_model=ResearchQuestionDetail)
def add_question_topic(
    question_id: int,
    body: AddTopicLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.topic_store import link_question_topic
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_question_topic(session, question_id, body.topic_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/topics/{topic_id}", response_model=ResearchQuestionDetail)
def patch_question_topic(
    question_id: int,
    topic_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.db.topic_store import update_question_topic_status
    with get_session(engine) as session:
        found = update_question_topic_status(session, question_id, topic_id, body.status)
    if not found:
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/topics/{topic_id}", status_code=204)
def remove_question_topic(
    question_id: int,
    topic_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.db.topic_store import unlink_question_topic
    with get_session(engine) as session:
        found = unlink_question_topic(session, question_id, topic_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Topic link {question_id}/{topic_id} not found")


@router.post("/questions/{question_id}/concepts", response_model=ResearchQuestionDetail)
def add_question_concept(
    question_id: int,
    body: AddConceptLinkRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    from neurodb.db.topic_store import link_question_concept
    with get_session(engine) as session:
        if session.get(ResearchQuestionORM, question_id) is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        link_question_concept(session, question_id, body.concept_id, status="confirmed")
    return _question_detail(engine, question_id)


@router.patch("/questions/{question_id}/concepts/{concept_id}", response_model=ResearchQuestionDetail)
def patch_question_concept(
    question_id: int,
    concept_id: int,
    body: PatchLinkStatusRequest,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.db.topic_store import update_question_concept_status
    with get_session(engine) as session:
        found = update_question_concept_status(session, question_id, concept_id, body.status)
    if not found:
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")
    return _question_detail(engine, question_id)


@router.delete("/questions/{question_id}/concepts/{concept_id}", status_code=204)
def remove_question_concept(
    question_id: int,
    concept_id: int,
    engine: Engine = Depends(get_engine),
) -> None:
    from neurodb.db.topic_store import unlink_question_concept
    with get_session(engine) as session:
        found = unlink_question_concept(session, question_id, concept_id)
    if not found:
        raise HTTPException(status_code=404, detail=f"Concept link {question_id}/{concept_id} not found")


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

            route = TaskRouter(build_provider_clients()).route(
                "research.hypothesis_review",
                engine=engine,
            )
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


def _update_status(engine: Engine, model_cls, item_id: int, status: str, schema_cls):
    """Generic status update helper. Returns 404 if item not found."""
    with get_session(engine) as session:
        row = session.get(model_cls, item_id)
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=f"{model_cls.__name__} {item_id} not found",
            )
        row.status = status
        session.flush()
        return schema_cls.model_validate(row)


@router.post("/evidence-links/{link_id}/retract", response_model=EvidenceLinkItem)
def retract_evidence_link(
    link_id: int,
    engine: Engine = Depends(get_engine),
) -> EvidenceLinkItem:
    return _update_status(engine, EvidenceLink, link_id, "retracted", EvidenceLinkItem)


@router.post("/hypotheses/{hypothesis_id}/archive", response_model=Hypothesis)
def archive_hypothesis(
    hypothesis_id: int,
    engine: Engine = Depends(get_engine),
) -> Hypothesis:
    with get_session(engine) as session:
        row = session.get(ResearchHypothesis, hypothesis_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Hypothesis {hypothesis_id} not found")
        row.status = "archived"
        session.flush()
        return _hypothesis_item(row)


@router.post("/questions/{question_id}/archive", response_model=ResearchQuestionDetail)
def archive_question(
    question_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchQuestionDetail:
    from neurodb.schema import ResearchQuestion as ResearchQuestionORM
    with get_session(engine) as session:
        row = session.get(ResearchQuestionORM, question_id)
        if row is None:
            raise HTTPException(status_code=404, detail=f"Question {question_id} not found")
        row.status = "archived"
        session.flush()
    return _question_detail(engine, question_id)


@router.post("/claims/{claim_id}/approve", response_model=ClaimItem)
def approve_claim(
    claim_id: int,
    engine: Engine = Depends(get_engine),
) -> ClaimItem:
    return _update_status(engine, Claim, claim_id, "approved", ClaimItem)


@router.post("/claims/{claim_id}/reject", response_model=ClaimItem)
def reject_claim(
    claim_id: int,
    engine: Engine = Depends(get_engine),
) -> ClaimItem:
    return _update_status(engine, Claim, claim_id, "rejected", ClaimItem)


@router.post("/claims/{claim_id}/archive", response_model=ClaimItem)
def archive_claim(
    claim_id: int,
    engine: Engine = Depends(get_engine),
) -> ClaimItem:
    return _update_status(engine, Claim, claim_id, "archived", ClaimItem)


@router.post("/gaps/{gap_id}/resolve", response_model=ResearchGapItem)
def resolve_gap(
    gap_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchGapItem:
    return _update_status(engine, ResearchGap, gap_id, "resolved", ResearchGapItem)


@router.post("/gaps/{gap_id}/archive", response_model=ResearchGapItem)
def archive_gap(
    gap_id: int,
    engine: Engine = Depends(get_engine),
) -> ResearchGapItem:
    return _update_status(engine, ResearchGap, gap_id, "archived", ResearchGapItem)


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
