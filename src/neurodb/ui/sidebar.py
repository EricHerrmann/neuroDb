import streamlit as st


def render_sidebar(engine=None) -> None:
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    with st.sidebar:
        with st.expander("Agent", expanded=True):
            mode_labels = {
                "local_db": "Local DB",
                "external_db": "External DB",
                "neuro_tutor": "Neuro-Tutor",
                "neuro_research": "Neuro-Research",
            }
            mode_options = list(mode_labels)
            current_mode = st.session_state.get("agent_mode", "local_db")
            selected_mode = st.radio(
                "Mode",
                options=mode_options,
                index=mode_options.index(current_mode) if current_mode in mode_options else 0,
                format_func=lambda m: mode_labels[m],
                label_visibility="collapsed",
            )
            if selected_mode != current_mode:
                from neurodb.research_tools import save_app_preference

                st.session_state["agent_mode"] = selected_mode
                st.session_state["chapter_context"] = ""
                if engine is not None:
                    save_app_preference(engine, "agent_mode", selected_mode)
                st.session_state.pop("neuro_agent", None)
                st.rerun()

        if st.session_state.get("agent_mode", "local_db") not in {"neuro_tutor", "neuro_research"}:
            with st.expander("Context", expanded=True):
                book_options = {key: value["display_name"] for key, value in REGISTRY.items()}
                st.selectbox(
                    "Textbook",
                    options=list(book_options.keys()),
                    format_func=lambda key: book_options[key],
                    key="selected_book_key",
                )

                chapter_input = st.text_input(
                    "Current chapter (optional)",
                    placeholder="e.g. Ch12",
                    key="chapter_input_raw",
                )

                if chapter_input.strip():
                    raw = chapter_input.strip().lstrip("Cc").lstrip("hH").strip()
                    try:
                        chapter_num = int(raw)
                    except ValueError:
                        chapter_num = None

                    if chapter_num is not None:
                        book_key = st.session_state.get("selected_book_key", "")
                        info = lookup_chapter(book_key, chapter_num)
                        if info:
                            st.success(
                                f"**Ch{chapter_num} — {info['title']}**\n"
                                f"Topics: {', '.join(info['topics'])}"
                            )
                            context_str = (
                                f"Ch{chapter_num} — {info['title']}\n"
                                f"Topics: {', '.join(info['topics'])}"
                            )
                            if st.button("Set chapter context", key="set_chapter_btn"):
                                st.session_state["chapter_context"] = context_str
                                agent = st.session_state.get("neuro_agent")
                                if agent:
                                    agent.chapter_context = context_str
                                st.rerun()
                        else:
                            st.warning(
                                f"Ch{chapter_num} not yet in registry — context not set."
                            )
                    else:
                        st.warning("Could not parse chapter number — context not set.")

                current_context = st.session_state.get("chapter_context", "")
                if current_context:
                    st.caption(f"Active: {current_context[:60]}")
                    if st.button("Clear chapter context", key="clear_chapter_btn"):
                        st.session_state["chapter_context"] = ""
                        agent = st.session_state.get("neuro_agent")
                        if agent:
                            agent.chapter_context = ""
                        st.rerun()

        _render_previous_topics(engine)
        _render_connections(engine)

        db_path = st.session_state.get("db_path", "neurodb.duckdb")
        st.divider()
        st.caption(f"DB: `{db_path}`")
        st.caption(f"Session: `{'active' if 'session_id' in st.session_state else 'none'}`")


def _render_previous_topics(engine=None) -> None:
    engine = engine or st.session_state.get("engine")
    with st.expander("Previous Topics", expanded=True):
        active_topic = st.session_state.get("active_prior_topic", "")
        if active_topic:
            st.caption(f"Active: {active_topic[:60]}")

        if engine is None:
            st.caption("No previous topics.")
            return

        rows = _list_chat_sessions(engine)
        if not rows:
            st.caption("No previous topics.")
            return

        _render_topic_rows(engine, rows[:10])
        if len(rows) > 10:
            with st.expander("Show all"):
                _render_topic_rows(engine, rows[10:])


def _render_topic_rows(engine, rows) -> None:
    active_session_id = st.session_state.get("active_session_id")
    for row in rows:
        is_active = active_session_id and row.session_id == active_session_id
        label = ("▸ " if is_active else "") + _format_topic_label(row)
        if st.button(label, key=f"load_topic_{row.id}", width="stretch"):
            _load_previous_topic(engine, row.session_id, row.inferred_topic)

        edited = st.text_input(
            "Edit topic label",
            value=row.inferred_topic,
            key=f"edit_topic_{row.id}",
            label_visibility="collapsed",
        )
        if edited.strip() and edited.strip() != row.inferred_topic:
            if st.button("Save topic label", key=f"save_topic_{row.id}", width="stretch"):
                _update_topic_label(engine, row.id, edited.strip())
                st.rerun()


def _render_connections(engine=None) -> None:
    import os

    engine = engine or st.session_state.get("engine")
    with st.expander("Connections", expanded=False):
        st.caption(f"NCBI (PubMed): {'present' if os.environ.get('NCBI_API_KEY') else 'not set'}")
        st.caption(
            "Semantic Scholar: "
            f"{'present' if os.environ.get('SEMANTIC_SCHOLAR_API_KEY') else 'not set'}"
        )
        pending = _count_pending_connector_requests(engine) if engine is not None else 0
        st.caption(f"Pending connector requests: {pending} -> see Suggestions tab")


def _list_chat_sessions(engine):
    from neurodb.db import get_session
    from neurodb.schema import ChatSession

    with get_session(engine) as session:
        return (
            session.query(ChatSession)
            .order_by(ChatSession.ended_at.desc().nullslast(), ChatSession.started_at.desc())
            .all()
        )


def _format_topic_label(row) -> str:
    date_text = (row.ended_at or row.started_at or "")[:10] or "unknown"
    mode_label = {
        "local_db": "Local DB",
        "external_db": "External DB",
        "neuro_tutor": "Neuro-Tutor",
        "neuro_research": "Neuro-Research",
    }.get(row.agent_mode, row.agent_mode)
    return f"{row.inferred_topic[:48]} | {date_text} | {mode_label} | {row.message_count} turns"


def _load_previous_topic(engine, session_id: str, inferred_topic: str = "") -> None:
    from neurodb.ui.pages.chat import _auto_summarize_if_sufficient, clear_chat_state_for_context_switch

    _auto_summarize_if_sufficient()
    manager = st.session_state.get("session_manager")
    context = manager.get_context_for_session_id(session_id) if manager is not None else ""
    if not context:
        context = f"Most recent study session: {inferred_topic}" if inferred_topic else ""
    st.session_state["active_prior_context"] = context
    st.session_state["active_prior_topic"] = inferred_topic
    st.session_state["active_session_id"] = session_id
    clear_chat_state_for_context_switch()
    st.rerun()


def _update_topic_label(engine, row_id: int, label: str) -> None:
    from neurodb.db import get_session
    from neurodb.schema import ChatSession

    with get_session(engine) as session:
        row = session.get(ChatSession, row_id)
        if row is not None:
            row.inferred_topic = label


def _count_pending_connector_requests(engine) -> int:
    from neurodb.db import get_session
    from neurodb.schema import SourceSuggestion

    with get_session(engine) as session:
        return (
            session.query(SourceSuggestion)
            .filter_by(status="pending", suggestion_type="new_connector")
            .count()
        )
