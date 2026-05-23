"""Research workspace for Neuro-Research artifacts and metrics."""
import json

import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.research.hypothesis_review import run_hypothesis_review
from neurodb.research_tools import (
    get_knowledge_growth_metrics,
    list_hypotheses,
    list_research_questions,
    update_hypothesis_review_status,
)
from neurodb.schema import HypothesisReview


def render(engine: Engine) -> None:
    st.subheader("Research")
    _render_metrics(engine)
    st.divider()
    _render_questions(engine)
    st.divider()
    _render_hypotheses(engine)


def _render_metrics(engine: Engine) -> None:
    manager = st.session_state.get("session_manager")
    metrics = get_knowledge_growth_metrics(
        engine,
        vector_store=st.session_state.get("vector_store"),
        knowledge_store=st.session_state.get("knowledge_store"),
        context_store=getattr(manager, "_store", None),
    )
    cols = st.columns(4)
    cols[0].metric("Approved sources", metrics["approved_sources_count"])
    cols[1].metric("Sessions", metrics["chat_sessions_count"])
    cols[2].metric("Literature searches", metrics["literature_searches_count"])
    cols[3].metric("Draft hypotheses", metrics["research_hypotheses_count"])

    with st.expander("Metric caveats", expanded=False):
        for caveat in metrics["caveats"]:
            st.caption(caveat)

    if st.button("Snapshot metrics", width="stretch"):
        snapshot = get_knowledge_growth_metrics(
            engine,
            vector_store=st.session_state.get("vector_store"),
            knowledge_store=st.session_state.get("knowledge_store"),
            context_store=getattr(manager, "_store", None),
            persist=True,
        )
        st.success(f"Saved metrics snapshot #{snapshot['snapshot_id']}.")


def _render_questions(engine: Engine) -> None:
    st.markdown("**Research Questions**")
    status = st.selectbox(
        "Question status",
        options=["all", "open", "parked", "converted_to_hypothesis"],
        key="research_question_status",
    )
    rows = _list_questions(engine, status)
    if not rows:
        st.caption("No research questions yet.")
        return
    for row in rows:
        st.markdown(f"**{row.question}**")
        st.caption(f"{row.status} | created {row.created_at[:10]}")
        st.caption(row.topic_context[:240])


def _render_hypotheses(engine: Engine) -> None:
    st.markdown("**Draft Hypotheses**")
    status = st.selectbox(
        "Hypothesis status",
        options=["all", "draft", "needs_evidence", "ready_for_plan", "archived"],
        key="research_hypothesis_status",
    )
    rows = _list_hypotheses(engine, status)
    if not rows:
        st.caption("No draft hypotheses yet.")
        return
    for row in rows:
        title_col, action_col = st.columns([4, 1])
        title_col.markdown(f"**{row.title}**")
        if action_col.button("Review Hypothesis", key=f"review_hypothesis_{row.id}"):
            _run_review_action(engine, row.id)
        st.caption(f"{row.status} | created {row.created_at[:10]}")
        st.markdown(row.mechanism)
        with st.expander("Evidence, predictions, datasets, confounds"):
            st.json({
                "evidence": _load_json(row.evidence_json),
                "predictions": _load_json(row.predictions_json),
                "datasets": _load_json(row.datasets_json),
                "confounds": _load_json(row.confounds_json),
                "limitations": row.limitations,
            })
        _render_hypothesis_reviews(engine, row.id)


def _run_review_action(engine: Engine, hypothesis_id: int) -> None:
    from neurodb.config.provider_factory import build_provider_clients
    from neurodb.config.task_router import TaskRouter

    providers = build_provider_clients()
    if not providers:
        st.error("A configured model provider API key is required to review a hypothesis.")
        return
    try:
        route = TaskRouter(providers).route("research.hypothesis_review", engine=engine)
        result = run_hypothesis_review(
            hypothesis_id,
            engine,
            model=route.model_id,
            model_client=route.model_client,
            model_provider=route.provider,
            max_tokens=route.max_tokens,
        )
    except Exception as exc:
        st.error(f"Hypothesis review failed: {exc}")
        return
    if "error" in result:
        st.error(result["error"])
        return
    st.success("Hypothesis review saved.")
    st.rerun()


def _render_hypothesis_reviews(engine: Engine, hypothesis_id: int) -> None:
    reviews = _list_hypothesis_reviews(engine, hypothesis_id)
    if not reviews:
        return
    st.markdown("**Hypothesis Reviews**")
    for review in reviews:
        st.caption(f"{review.status} | {review.model} | created {review.created_at[:10]}")
        st.markdown(review.critique_text)
        review_payload = {
            "unsupported_claims": _load_json(review.unsupported_claims_json),
            "missing_confounds": _load_json(review.missing_confounds_json),
            "suggested_revisions": review.suggested_revisions,
        }
        st.json(review_payload)
        accept_col, dismiss_col = st.columns(2)
        if accept_col.button("Accept revisions", key=f"accept_review_{review.id}"):
            update_hypothesis_review_status(engine, review.id, "accepted")
            st.rerun()
        if dismiss_col.button("Dismiss review", key=f"dismiss_review_{review.id}"):
            update_hypothesis_review_status(engine, review.id, "dismissed")
            st.rerun()


def _list_questions(engine: Engine, status: str):
    return list_research_questions(engine, status=status)


def _list_hypotheses(engine: Engine, status: str):
    return list_hypotheses(engine, status=status)


def _list_hypothesis_reviews(engine: Engine, hypothesis_id: int):
    with get_session(engine) as session:
        return (
            session.query(HypothesisReview)
            .filter_by(hypothesis_id=hypothesis_id)
            .filter(HypothesisReview.status != "dismissed")
            .order_by(HypothesisReview.created_at.desc())
            .all()
        )


def _load_json(value: str):
    try:
        return json.loads(value)
    except json.JSONDecodeError:
        return []
