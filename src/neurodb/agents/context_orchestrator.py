"""Shared context-mode retrieval and prompt-boundary helpers for agents."""
from __future__ import annotations

from typing import Literal, TypedDict

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from neurodb.schema import ResearchQuestion, Topic

ContextMode = Literal["general", "contextual", "grounded"]
VALID_CONTEXT_MODES: frozenset[str] = frozenset({"general", "contextual", "grounded"})
DEFAULT_CONTEXT_MODE: ContextMode = "contextual"


class ActiveFocus(TypedDict, total=False):
    focus_type: Literal["topic", "research_question"]
    focus_id: int
    label: str


class SourceCounts(TypedDict):
    papers: int
    concepts: int
    study_notes: int
    dataset_packets: int
    claims: int
    evidence_links: int
    gaps: int
    semantic_hits: int


class ContextRequest(TypedDict, total=False):
    mode: ContextMode
    agent_mode: Literal["neuro_tutor", "neuro_research"]
    user_message: str
    active_focus: ActiveFocus | None
    max_papers: int
    max_claims: int
    max_notes: int
    max_datasets: int


class ContextBundle(TypedDict, total=False):
    mode: ContextMode
    agent_mode: str
    active_focus: ActiveFocus | None
    topic_bundle: dict | None
    question_bundle: dict | None
    knowledge_hits: list[dict]
    semantic_hits: list[dict]
    source_counts: SourceCounts
    gap_summaries: list[dict]
    warnings: list[str]
    prompt_block: str


def normalize_context_mode(value: str | None) -> ContextMode:
    """Return a valid context mode, defaulting to contextual."""
    if value is None or value == "":
        return DEFAULT_CONTEXT_MODE
    cleaned = value.strip().lower()
    if cleaned not in VALID_CONTEXT_MODES:
        raise ValueError(
            f"Unknown context mode: {value!r}. Valid: {sorted(VALID_CONTEXT_MODES)}"
        )
    return cleaned  # type: ignore[return-value]


def empty_source_counts() -> SourceCounts:
    return {
        "papers": 0,
        "concepts": 0,
        "study_notes": 0,
        "dataset_packets": 0,
        "claims": 0,
        "evidence_links": 0,
        "gaps": 0,
        "semantic_hits": 0,
    }


def build_context_bundle(
    engine,
    *,
    request: ContextRequest,
    knowledge_store=None,
    vector_store=None,
    context_store=None,
) -> ContextBundle:
    """Build a compact typed context bundle for an agent turn."""
    del context_store  # Reserved for Phase 4+ expansion; prior_context still handles sessions.

    mode = normalize_context_mode(request.get("mode"))
    agent_mode = request.get("agent_mode", "neuro_tutor")
    user_message = request.get("user_message", "")
    active_focus = request.get("active_focus")
    counts = empty_source_counts()
    warnings: list[str] = []
    topic_bundle: dict | None = None
    question_bundle: dict | None = None
    knowledge_hits: list[dict] = []
    semantic_hits: list[dict] = []

    with Session(engine) as session:
        active_focus = _resolve_active_focus(session, active_focus, user_message, mode)
        if _should_retrieve_local_context(mode, active_focus, user_message):
            if active_focus and active_focus.get("focus_type") == "research_question":
                from neurodb.db.claim_store import get_question_bundle

                try:
                    question_bundle = get_question_bundle(session, int(active_focus["focus_id"]))
                    _merge_question_counts(counts, question_bundle)
                except SQLAlchemyError as exc:
                    session.rollback()
                    warnings.append(
                        "Research question context is unavailable; run the Phase 3 "
                        f"claims/evidence migration. Detail: {exc.__class__.__name__}"
                    )
            elif active_focus and active_focus.get("focus_type") == "topic":
                from neurodb.db.topic_store import get_topic_bundle

                try:
                    topic_bundle = get_topic_bundle(session, int(active_focus["focus_id"]))
                    _merge_topic_counts(counts, topic_bundle)
                except SQLAlchemyError as exc:
                    session.rollback()
                    warnings.append(
                        "Topic context is unavailable; run the Phase 2 papers/topics "
                        f"migration. Detail: {exc.__class__.__name__}"
                    )

    if mode in {"contextual", "grounded"} or _message_requests_local_context(user_message):
        knowledge_hits = _safe_store_search(knowledge_store, user_message, n=3)
        semantic_hits = _safe_store_search(vector_store, user_message, n=3)
        counts["papers"] += len(knowledge_hits)
        counts["semantic_hits"] = len(knowledge_hits) + len(semantic_hits)

    if mode == "grounded" and not _has_local_support(counts):
        warnings.append("No approved local support was found for grounded mode.")

    bundle: ContextBundle = {
        "mode": mode,
        "agent_mode": agent_mode,
        "active_focus": active_focus,
        "topic_bundle": topic_bundle,
        "question_bundle": question_bundle,
        "knowledge_hits": knowledge_hits,
        "semantic_hits": semantic_hits,
        "source_counts": counts,
        "gap_summaries": _gap_summaries(question_bundle),
        "warnings": warnings,
    }
    bundle["prompt_block"] = _build_prompt_block(bundle)
    return bundle


def context_summary_event(bundle: dict | None) -> dict | None:
    """Return the SSE context_summary event for a context bundle."""
    if not bundle:
        return None
    sc = bundle.get("source_counts", empty_source_counts())
    return {
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


def _should_retrieve_local_context(
    mode: ContextMode, active_focus: ActiveFocus | None, user_message: str
) -> bool:
    if active_focus is not None:
        return True
    if mode == "general":
        return _message_requests_local_context(user_message)
    return False


def _resolve_active_focus(
    session: Session,
    active_focus: ActiveFocus | None,
    user_message: str,
    mode: ContextMode,
) -> ActiveFocus | None:
    if active_focus and active_focus.get("focus_type") in {"topic", "research_question"}:
        return _add_focus_label(session, active_focus)
    if mode == "general":
        return None
    query = user_message.strip()
    if not query:
        return None

    try:
        question = session.execute(
            select(ResearchQuestion.id, ResearchQuestion.question)
            .where(ResearchQuestion.question.ilike(f"%{query}%"))
            .limit(1)
        ).first()
    except SQLAlchemyError:
        session.rollback()
        question = None
    if question is not None:
        question_id, question_text = question
        return {
            "focus_type": "research_question",
            "focus_id": question_id,
            "label": question_text,
        }

    for token in _candidate_focus_terms(query):
        topic = session.execute(
            select(Topic).where(Topic.name.ilike(f"%{token}%")).limit(1)
        ).scalar_one_or_none()
        if topic is not None:
            return {"focus_type": "topic", "focus_id": topic.id, "label": topic.name}
    return None


def _add_focus_label(session: Session, active_focus: ActiveFocus) -> ActiveFocus:
    if active_focus.get("label"):
        return active_focus
    focus_type = active_focus.get("focus_type")
    focus_id = active_focus.get("focus_id")
    if focus_type == "topic":
        topic = session.get(Topic, focus_id)
        if topic is not None:
            return {**active_focus, "label": topic.name}
    if focus_type == "research_question":
        try:
            question = session.execute(
                select(ResearchQuestion.question).where(ResearchQuestion.id == focus_id)
            ).scalar_one_or_none()
        except SQLAlchemyError:
            session.rollback()
            question = None
        if question is not None:
            return {**active_focus, "label": question}
    return active_focus


def _candidate_focus_terms(query: str) -> list[str]:
    lowered = query.lower()
    terms = [lowered]
    for marker in ["about ", "for ", "on "]:
        if marker in lowered:
            terms.append(lowered.split(marker, 1)[1].strip(" .?"))
    return [term for term in terms if len(term) >= 3]


def _message_requests_local_context(user_message: str) -> bool:
    lowered = user_message.lower()
    return any(
        phrase in lowered
        for phrase in [
            "neurodb",
            "my notes",
            "local evidence",
            "local context",
            "from the db",
            "from my database",
        ]
    )


def _safe_store_search(store, query: str, n: int) -> list[dict]:
    if store is None or not query:
        return []
    search = getattr(store, "search", None)
    if not callable(search):
        return []
    try:
        try:
            return list(search(query, n=n))
        except TypeError:
            return list(search(query, n_results=n))
    except Exception:
        return []


def _merge_topic_counts(counts: SourceCounts, bundle: dict | None) -> None:
    if not bundle:
        return
    counts["papers"] += len(bundle.get("papers", []))
    counts["concepts"] += len(bundle.get("concepts", []))
    counts["study_notes"] += len(bundle.get("study_notes", []))
    counts["dataset_packets"] += len(bundle.get("dataset_packets", []))


def _merge_question_counts(counts: SourceCounts, bundle: dict | None) -> None:
    if not bundle:
        return
    counts["claims"] += len(bundle.get("claims", []))
    counts["gaps"] += len(bundle.get("gaps", []))
    counts["papers"] += _count_unique_claim_papers(bundle.get("claims", []))
    counts["evidence_links"] += sum(
        len(hypothesis.get("evidence_links", []))
        for hypothesis in bundle.get("hypotheses", [])
        if isinstance(hypothesis, dict)
    )


def _count_unique_claim_papers(claims: list[dict]) -> int:
    return len({claim.get("paper_id") for claim in claims if claim.get("paper_id") is not None})


def _has_local_support(counts: SourceCounts) -> bool:
    return any(
        counts[key] > 0
        for key in ["papers", "claims", "study_notes", "dataset_packets", "semantic_hits"]
    )


def _gap_summaries(question_bundle: dict | None) -> list[dict]:
    if not question_bundle:
        return []
    return list(question_bundle.get("gaps", []))


def _build_prompt_block(bundle: ContextBundle) -> str:
    mode = bundle["mode"]
    focus = bundle.get("active_focus")
    focus_line = "none"
    if focus:
        focus_line = f"{focus.get('focus_type')} {focus.get('focus_id')} - {focus.get('label', '')}"
    counts = bundle["source_counts"]
    lines = [
        f"NeuroDb context mode: {mode}",
        f"Active focus: {focus_line}",
        "",
        "Use these source boundaries:",
        _mode_boundary_line(mode),
        (
            "NeuroDb context counts: "
            f"papers={counts['papers']}, concepts={counts['concepts']}, "
            f"notes={counts['study_notes']}, claims={counts['claims']}, "
            f"datasets={counts['dataset_packets']}, gaps={counts['gaps']}, "
            f"semantic_hits={counts['semantic_hits']}."
        ),
        "Dataset caveat: sparse or partial dataset packets are context only, not direct evidence.",
    ]
    compact = _compact_context_lines(bundle)
    if compact:
        lines.extend(["", "Compact local context:", *compact])
    warnings = bundle.get("warnings") or []
    if warnings:
        lines.extend(["", "Context warnings:", *[f"- {warning}" for warning in warnings]])
    return "\n".join(lines)


def _mode_boundary_line(mode: ContextMode) -> str:
    if mode == "general":
        return "- General mode: model neurology knowledge comes first; label local context if used."
    if mode == "contextual":
        return "- Contextual mode: use model knowledge, focused by retrieved NeuroDb context."
    return (
        "- Grounded mode: local approved evidence comes first; model knowledge may explain "
        "but must not be presented as local evidence."
    )


def _compact_context_lines(bundle: ContextBundle) -> list[str]:
    lines: list[str] = []
    topic_bundle = bundle.get("topic_bundle") or {}
    question_bundle = bundle.get("question_bundle") or {}
    if topic_bundle.get("topic"):
        topic = topic_bundle["topic"]
        lines.append(f"- Topic: {topic.get('name')}")
    if question_bundle.get("question"):
        question = question_bundle["question"]
        lines.append(f"- Research question: {question.get('question')}")
    for paper in (topic_bundle.get("papers") or [])[:3]:
        lines.append(f"- Paper: {paper.get('title')} ({paper.get('status')})")
    for claim in (question_bundle.get("claims") or [])[:3]:
        lines.append(f"- Claim: {claim.get('text')}")
    for gap in (question_bundle.get("gaps") or [])[:3]:
        lines.append(f"- Gap: {gap.get('description')} ({gap.get('status')})")
    for hit in (bundle.get("knowledge_hits") or [])[:2]:
        metadata = hit.get("metadata") or {}
        title = metadata.get("title") or hit.get("id")
        lines.append(f"- Knowledge hit: {title}")
    return lines
