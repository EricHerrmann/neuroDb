import streamlit as st


def render_sidebar() -> None:
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    with st.sidebar:
        with st.expander("Agent", expanded=True):
            mode_labels = {
                "local_db": "Local DB",
                "external_db": "External DB",
                "neuro_tutor": "Neuro-Tutor",
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
                st.session_state["agent_mode"] = selected_mode
                st.session_state["chapter_context"] = ""
                st.session_state.pop("neuro_agent", None)
                st.rerun()

        if st.session_state.get("agent_mode", "local_db") != "neuro_tutor":
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

        db_path = st.session_state.get("db_path", "neurodb.duckdb")
        st.divider()
        st.caption(f"DB: `{db_path}`")
        st.caption(f"Session: `{'active' if 'session_id' in st.session_state else 'none'}`")
