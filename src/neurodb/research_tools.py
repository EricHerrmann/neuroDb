"""Research epoch — hypothesis tools, research question persistence,
and evidence tracking helpers.

Migration target: src/neurodb/research/tools.py
"""
import json
from datetime import UTC, datetime
from typing import Any, TypedDict

from sqlalchemy import Engine, func, text

from neurodb.db import get_session
from neurodb.schema import (
    AppPreference,
    ChatSession,
    DatasetIndex,
    HypothesisReview,
    KnowledgeGrowthSnapshot,
    KnowledgeSource,
    LiteratureSearch,
    ResearchHypothesis,
    ResearchQuestion,
    StudyNote,
)


class EvidenceItem(TypedDict):
    source: str
    summary: str


class DatasetItem(TypedDict):
    dataset_id: str
    relevance: str


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def _json_list(value: str) -> list:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return []
    return parsed if isinstance(parsed, list) else []


def load_app_preference(engine: Engine, key: str, default: str = "") -> str:
    """Return a persisted app preference value, or default when absent."""
    with get_session(engine) as session:
        row = session.get(AppPreference, key)
        return row.value if row is not None else default


def save_app_preference(engine: Engine, key: str, value: str, now: str | None = None) -> None:
    """Persist a narrow key/value app preference."""
    timestamp = now or _now_iso()
    with get_session(engine) as session:
        row = session.get(AppPreference, key)
        if row is None:
            session.add(AppPreference(key=key, value=value, updated_at=timestamp))
        else:
            row.value = value
            row.updated_at = timestamp


def record_research_question(
    engine: Engine,
    question: str,
    topic_context: str,
    status: str = "open",
    now: str | None = None,
) -> dict:
    """Persist a candidate research question."""
    cleaned_question = question.strip()
    cleaned_context = topic_context.strip()
    if not cleaned_question:
        return {"error": "question is required"}
    if not cleaned_context:
        return {"error": "topic_context is required"}

    timestamp = now or _now_iso()
    with get_session(engine) as session:
        row = ResearchQuestion(
            question=cleaned_question,
            topic_context=cleaned_context,
            status=status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(row)
        session.flush()
        return {
            "status": "recorded",
            "id": row.id,
            "question": row.question,
            "artifact_status": row.status,
            "created_at": row.created_at,
        }


def draft_hypothesis(
    engine: Engine,
    title: str,
    mechanism: str,
    evidence: list[EvidenceItem],
    predictions: list[str],
    datasets: list[DatasetItem],
    confounds: list[str] | list[dict],
    limitations: str,
    question_id: int | None = None,
    status: str = "draft",
    now: str | None = None,
) -> dict:
    """Persist a structured draft hypothesis."""
    if not title.strip():
        return {"error": "title is required"}
    if not mechanism.strip():
        return {"error": "mechanism is required"}
    if not limitations.strip():
        return {"error": "limitations are required"}
    if not isinstance(confounds, list) or not confounds:
        return {"error": "at least one confound or explicit limitation is required"}

    timestamp = now or _now_iso()
    with get_session(engine) as session:
        row = ResearchHypothesis(
            question_id=question_id,
            title=title.strip(),
            mechanism=mechanism.strip(),
            evidence_json=json.dumps(evidence or []),
            predictions_json=json.dumps(predictions or []),
            datasets_json=json.dumps(datasets or []),
            confounds_json=json.dumps(confounds),
            limitations=limitations.strip(),
            status=status,
            created_at=timestamp,
            updated_at=timestamp,
        )
        session.add(row)
        session.flush()
        return {
            "status": "drafted",
            "id": row.id,
            "title": row.title,
            "artifact_status": row.status,
            "created_at": row.created_at,
        }


def create_hypothesis_review(
    engine: Engine,
    hypothesis_id: int,
    *,
    model: str,
    critique_text: str,
    unsupported_claims: list[str] | list[dict],
    missing_confounds: list[str] | list[dict],
    suggested_revisions: str,
    status: str = "pending",
    now: str | None = None,
) -> dict:
    """Persist a premium-model critique for an existing draft hypothesis."""
    if not model.strip():
        return {"error": "model is required"}
    if not critique_text.strip():
        return {"error": "critique_text is required"}
    if not suggested_revisions.strip():
        return {"error": "suggested_revisions is required"}
    if status not in {"pending", "accepted", "dismissed"}:
        return {"error": "status must be pending, accepted, or dismissed"}

    timestamp = now or _now_iso()
    with get_session(engine) as session:
        hypothesis = session.get(ResearchHypothesis, hypothesis_id)
        if hypothesis is None:
            return {"error": f"hypothesis {hypothesis_id} not found"}
        row = HypothesisReview(
            hypothesis_id=hypothesis.id,
            created_at=timestamp,
            model=model.strip(),
            critique_text=critique_text.strip(),
            unsupported_claims_json=json.dumps(unsupported_claims or []),
            missing_confounds_json=json.dumps(missing_confounds or []),
            suggested_revisions=suggested_revisions.strip(),
            status=status,
        )
        session.add(row)
        session.flush()
        return {
            "status": "reviewed",
            "id": row.id,
            "hypothesis_id": row.hypothesis_id,
            "model": row.model,
            "critique_text": row.critique_text,
            "unsupported_claims": unsupported_claims or [],
            "missing_confounds": missing_confounds or [],
            "suggested_revisions": row.suggested_revisions,
            "artifact_status": row.status,
            "created_at": row.created_at,
        }


def update_hypothesis_review_status(
    engine: Engine,
    review_id: int,
    status: str,
) -> dict:
    """Update a hypothesis review decision status."""
    if status not in {"pending", "accepted", "dismissed"}:
        return {"error": "status must be pending, accepted, or dismissed"}
    with get_session(engine) as session:
        row = session.get(HypothesisReview, review_id)
        if row is None:
            return {"error": f"review {review_id} not found"}
        row.status = status
        return {"status": "updated", "id": row.id, "artifact_status": row.status}


def list_hypothesis_reviews(
    engine: Engine,
    hypothesis_id: int,
    *,
    include_dismissed: bool = False,
) -> list[dict]:
    """Return review artifacts for a hypothesis, newest first."""
    with get_session(engine) as session:
        query = session.query(HypothesisReview).filter_by(hypothesis_id=hypothesis_id)
        if not include_dismissed:
            query = query.filter(HypothesisReview.status != "dismissed")
        rows = query.order_by(HypothesisReview.created_at.desc()).all()
        return [
            {
                "id": row.id,
                "hypothesis_id": row.hypothesis_id,
                "model": row.model,
                "critique_text": row.critique_text,
                "unsupported_claims": _json_list(row.unsupported_claims_json),
                "missing_confounds": _json_list(row.missing_confounds_json),
                "suggested_revisions": row.suggested_revisions,
                "status": row.status,
                "created_at": row.created_at,
            }
            for row in rows
        ]


def get_knowledge_growth_metrics(
    engine: Engine,
    *,
    vector_store=None,
    knowledge_store=None,
    context_store=None,
    persist: bool = False,
    now: str | None = None,
) -> dict:
    """Compute current learning/research growth metrics and optionally snapshot them."""
    timestamp = now or _now_iso()
    with get_session(engine) as session:
        approved_sources = (
            session.query(KnowledgeSource).filter_by(status="approved").count()
        )
        pending_sources = (
            session.query(KnowledgeSource).filter_by(status="pending").count()
        )
        chat_sessions = session.query(ChatSession).count()
        literature_searches = session.query(LiteratureSearch).count()
        study_notes = session.query(StudyNote).count()
        distinct_concepts = len({
            row[0]
            for row in session.query(StudyNote.concept_tag).distinct().all()
            if row[0]
        })
        research_questions = session.query(ResearchQuestion).count()
        research_hypotheses = session.query(ResearchHypothesis).count()
        source_type_counts = dict(
            session.query(KnowledgeSource.source_type, func.count())
            .group_by(KnowledgeSource.source_type)
            .all()
        )

        metrics: dict[str, Any] = {
            "snapshot_at": timestamp,
            "approved_sources_count": approved_sources,
            "pending_sources_count": pending_sources,
            "chat_sessions_count": chat_sessions,
            "literature_searches_count": literature_searches,
            "study_notes_count": study_notes,
            "distinct_concept_tags_count": distinct_concepts,
            "research_questions_count": research_questions,
            "research_hypotheses_count": research_hypotheses,
            "source_type_counts": source_type_counts,
            "chroma_counts": {
                "dataset_embeddings": _collection_count(vector_store, "_collection"),
                "knowledge_library": _collection_count(knowledge_store, "_collection"),
                "agent_context": _collection_count(context_store, "_col"),
            },
            "caveats": [
                "Chroma collection counts can diverge from DuckDB rows after partial writes.",
                "literature_searches counts searches, not quality-reviewed papers.",
                "study_notes count is not a measure of evidence strength.",
            ],
        }

        if persist:
            snapshot = KnowledgeGrowthSnapshot(
                snapshot_at=timestamp,
                approved_sources_count=approved_sources,
                pending_sources_count=pending_sources,
                chat_sessions_count=chat_sessions,
                literature_searches_count=literature_searches,
                study_notes_count=study_notes,
                research_questions_count=research_questions,
                research_hypotheses_count=research_hypotheses,
                metrics_json=json.dumps(metrics),
            )
            session.add(snapshot)
            session.flush()
            metrics["snapshot_id"] = snapshot.id

        return metrics


def cross_reference_datasets(
    engine: Engine,
    query: str,
    *,
    vector_store=None,
    concept_tags: list[str] | None = None,
    sources: list[str] | None = None,
    n_results: int = 5,
) -> dict:
    """Return local dataset candidates related to a research topic."""
    cleaned_query = query.strip()
    if not cleaned_query:
        return {"query": query, "candidates": [], "limitations": ["query is required"]}

    semantic_results = _safe_semantic_search(vector_store, cleaned_query, n_results)
    semantic_by_dataset = {
        (
            result.get("metadata", {}).get("source"),
            result.get("metadata", {}).get("source_id"),
        ): result
        for result in semantic_results
        if result.get("metadata", {}).get("source")
        and result.get("metadata", {}).get("source_id")
    }

    source_filter = {s.lower() for s in sources or []}
    concept_filter = [tag.lower() for tag in concept_tags or []]
    query_terms = [
        term
        for term in cleaned_query.lower().replace(",", " ").split()
        if len(term) > 2
    ]
    limitations: list[str] = []
    if vector_store is None:
        limitations.append("semantic search unavailable; using DB metadata and study notes only")

    with get_session(engine) as session:
        metadata_by_key, metadata_limitations = _load_dataset_metadata(session)
        limitations.extend(metadata_limitations)
        candidates = []
        for dataset in session.query(DatasetIndex).all():
            if source_filter and dataset.source.lower() not in source_filter:
                continue
            key = (dataset.source, dataset.source_id)
            metadata = metadata_by_key.get(key, {})
            notes = _matched_notes(session, dataset.id, concept_filter, query_terms)
            semantic = semantic_by_dataset.get(key)
            metadata_hit = _metadata_matches(metadata, query_terms)
            if not notes and semantic is None and not metadata_hit:
                continue
            candidates.append({
                "source": dataset.source,
                "source_id": dataset.source_id,
                "title": metadata.get("title"),
                "modality": metadata.get("modality"),
                "matched_notes": notes,
                "semantic_distance": semantic.get("distance") if semantic else None,
                "reason": _candidate_reason(notes, semantic, metadata_hit),
            })

    candidates.sort(key=lambda row: (
        row["semantic_distance"] is None,
        row["semantic_distance"] if row["semantic_distance"] is not None else 999,
        row["source"],
        row["source_id"],
    ))
    if not candidates:
        limitations.append("no local datasets matched the query")
    return {
        "query": cleaned_query,
        "candidates": candidates[:n_results],
        "limitations": limitations,
    }


def _normalize_status_filter(status: str | list[str] | tuple[str, ...] | None) -> list[str]:
    if status is None or status == "all" or status == ["all"]:
        return []
    if isinstance(status, str):
        raw_values = status.split(",")
    else:
        raw_values = []
        for item in status:
            raw_values.extend(str(item).split(","))
    return [value.strip() for value in raw_values if value.strip() and value.strip() != "all"]


def list_research_questions(engine: Engine, status: str | list[str] = "all") -> list:
    """Return persisted research questions, optionally filtered by status."""
    with get_session(engine) as session:
        query = session.query(ResearchQuestion)
        statuses = _normalize_status_filter(status)
        if statuses:
            query = query.filter(ResearchQuestion.status.in_(statuses))
        return query.order_by(ResearchQuestion.created_at.desc()).all()


def list_hypotheses(engine: Engine, status: str | list[str] = "all") -> list:
    """Return persisted draft hypotheses, optionally filtered by status."""
    with get_session(engine) as session:
        query = session.query(ResearchHypothesis)
        statuses = _normalize_status_filter(status)
        if statuses:
            query = query.filter(ResearchHypothesis.status.in_(statuses))
        return query.order_by(ResearchHypothesis.created_at.desc()).all()


def _collection_count(owner, attr: str) -> int | None:
    collection = getattr(owner, attr, None) if owner is not None else None
    if collection is None:
        return None
    try:
        return collection.count()
    except Exception:
        return None


def _safe_semantic_search(vector_store, query: str, n_results: int) -> list[dict]:
    if vector_store is None:
        return []
    try:
        return vector_store.search(query, n_results=n_results)
    except Exception:
        return []


def _load_dataset_metadata(session) -> tuple[dict[tuple[str, str], dict], list[str]]:
    try:
        rows = session.execute(text(
            "SELECT source, source_id, title, modality, description FROM v_all_datasets"
        )).mappings()
        return {
            (row["source"], row["source_id"]): {
                "title": row["title"],
                "modality": row["modality"],
                "description": row["description"],
            }
            for row in rows
        }, []
    except Exception:
        return {}, [
            "v_all_datasets unavailable; returning source/source_id plus study-note matches"
        ]


def _matched_notes(
    session,
    index_id: int,
    concept_filter: list[str],
    query_terms: list[str],
) -> list[dict]:
    rows = session.query(StudyNote).filter_by(index_id=index_id).all()
    matches = []
    for row in rows:
        haystack = " ".join(
            value for value in [row.concept_tag, row.section_ref or "", row.note_text or ""]
        ).lower()
        if concept_filter:
            matched = any(tag in haystack for tag in concept_filter)
        else:
            matched = any(term in haystack for term in query_terms)
        if matched:
            matches.append({
                "id": row.id,
                "concept_tag": row.concept_tag,
                "section_ref": row.section_ref,
                "note_text": row.note_text,
            })
    return matches


def _metadata_matches(metadata: dict, query_terms: list[str]) -> bool:
    if not metadata:
        return False
    haystack = " ".join(
        str(metadata.get(key) or "")
        for key in ["title", "modality", "description"]
    ).lower()
    return any(term in haystack for term in query_terms)


def _candidate_reason(notes: list[dict], semantic: dict | None, metadata_hit: bool) -> str:
    reasons = []
    if semantic is not None:
        reasons.append("semantic search match")
    if notes:
        reasons.append("study-note match")
    if metadata_hit:
        reasons.append("metadata keyword match")
    return "; ".join(reasons)
