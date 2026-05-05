import json
import os
import uuid
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine, *, title: str = "", transcript_height: int = 420) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []
    if "api_messages" not in st.session_state:
        st.session_state["api_messages"] = _to_api_history(st.session_state["chat_history"])
    if "pending_user_message" not in st.session_state:
        st.session_state["pending_user_message"] = None

    if title:
        st.subheader(title)

    _init_agent(engine)
    _render_mode_and_chapter()

    agent = st.session_state.get("neuro_agent")
    if agent is None:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable chat.")
    _render_chat(agent, transcript_height=transcript_height)


def _init_agent(engine: Engine) -> None:
    if "neuro_agent" in st.session_state:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    vector_store = st.session_state.get("vector_store")
    mode = st.session_state.get("agent_mode", "local_db")

    if mode == "neuro_tutor":
        from neurodb.agents.tutor_agent import NeuroTutorAgent

        st.session_state["neuro_agent"] = NeuroTutorAgent(
            client=client,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=st.session_state.get("knowledge_store"),
        )
        return

    from neurodb.agents.db_agent import NeuroDbAgent

    st.session_state["neuro_agent"] = NeuroDbAgent(
        client=client,
        engine=engine,
        vector_store=vector_store,
        mode=mode,
        chapter_context=st.session_state.get("chapter_context", ""),
    )


def _render_mode_and_chapter() -> None:
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    st.divider()

    mode_labels = {
        "local_db": "Local DB",
        "external_db": "External DB",
        "neuro_tutor": "Neuro-Tutor",
    }
    mode_options = list(mode_labels)
    current_mode = st.session_state.get("agent_mode", "local_db")
    selected_mode = st.radio(
        "Agent mode",
        options=mode_options,
        index=mode_options.index(current_mode) if current_mode in mode_options else 0,
        format_func=lambda mode: mode_labels[mode],
        horizontal=True,
    )
    if selected_mode != current_mode:
        st.session_state["agent_mode"] = selected_mode
        st.session_state["chapter_context"] = ""
        st.session_state.pop("neuro_agent", None)
        st.rerun()

    if selected_mode == "neuro_tutor":
        st.divider()
        return

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
            info = lookup_chapter(st.session_state["selected_book_key"], chapter_num)
            if info:
                st.success(
                    f"**Ch{chapter_num} — {info['title']}**\nTopics: {', '.join(info['topics'])}"
                )
                context_str = f"Ch{chapter_num} — {info['title']}\nTopics: {', '.join(info['topics'])}"
                if st.button("Set chapter context", key="set_chapter_btn"):
                    st.session_state["chapter_context"] = context_str
                    agent = st.session_state.get("neuro_agent")
                    if agent:
                        agent.chapter_context = context_str
                    st.rerun()
            else:
                st.warning(f"Ch{chapter_num} not yet in registry for this book — context not set.")
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

    st.divider()


def _auto_start_session(first_message: str) -> None:
    st.session_state["session_id"] = str(uuid.uuid4())
    st.session_state["session_started_at"] = datetime.now(timezone.utc).isoformat()

    manager = st.session_state.get("session_manager")
    context = manager.get_context_for_topic(first_message) if manager else ""
    agent = st.session_state.get("neuro_agent")
    if agent:
        agent.prior_context = context


def _auto_summarize_if_sufficient() -> None:
    api_messages = st.session_state.get("api_messages", [])
    user_turns = sum(1 for message in api_messages if message["role"] == "user")
    if user_turns < 3:
        return

    manager = st.session_state.get("session_manager")
    session_id = st.session_state.get("session_id")
    if manager is None or not session_id:
        return

    with st.spinner("Saving session summary..."):
        summary = manager.end_session(session_id, api_messages)

    engine = st.session_state.get("engine")
    if engine is not None and summary:
        _write_chat_session_row(engine, session_id, api_messages, user_turns, summary)


def _write_chat_session_row(
    engine,
    session_id: str,
    api_messages: list[dict],
    user_turns: int,
    summary: str,
) -> None:
    from neurodb.db import get_session
    from neurodb.schema import ChatSession

    first_user = next(
        (
            message["content"]
            for message in api_messages
            if message["role"] == "user" and isinstance(message["content"], str)
        ),
        "unknown",
    )
    with get_session(engine) as session:
        session.add(ChatSession(
            session_id=session_id,
            inferred_topic=first_user[:200],
            agent_mode=st.session_state.get("agent_mode", "local_db"),
            started_at=st.session_state.get(
                "session_started_at",
                datetime.now(timezone.utc).isoformat(),
            ),
            ended_at=datetime.now(timezone.utc).isoformat(),
            summary_preview=summary[:200],
            message_count=user_turns,
        ))


def _render_chat(agent, transcript_height: int = 420) -> None:
    transcript_container = st.container()
    with transcript_container:
        visible_messages = [
            message for message in st.session_state["chat_history"]
            if not message.get("_system")
        ]
        if not visible_messages:
            with st.chat_message("assistant"):
                st.markdown("Chat ready. Ask about your datasets or a neuroscience topic.")

        for message in st.session_state["chat_history"]:
            if message.get("_system"):
                continue
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

    composer_col, clear_col = st.columns([4, 1])
    with composer_col:
        with st.form("agent_form", clear_on_submit=True):
            user_input = st.text_input(
                "Message",
                placeholder="Ask about your datasets or a neuroscience topic...",
                label_visibility="collapsed",
                disabled=agent is None,
            )
            submitted = st.form_submit_button(
                "Send",
                width="stretch",
                disabled=agent is None,
            )
    with clear_col:
        clear_clicked = st.button(
            "Clear",
            width="stretch",
            disabled=not st.session_state["chat_history"],
        )

    if clear_clicked:
        _auto_summarize_if_sufficient()
        st.session_state["chat_history"] = []
        st.session_state["api_messages"] = []
        st.session_state["pending_user_message"] = None
        st.session_state.pop("session_id", None)
        st.session_state.pop("session_started_at", None)
        if agent:
            agent.prior_context = ""
        st.rerun()
    elif submitted and user_input.strip():
        message = user_input.strip()
        if "session_id" not in st.session_state:
            _auto_start_session(message)
        st.session_state["chat_history"].append({"role": "user", "content": message})
        if "api_messages" not in st.session_state:
            st.session_state["api_messages"] = _to_api_history(
                st.session_state["chat_history"][:-1]
            )
        st.session_state["pending_user_message"] = message
        st.rerun()

    pending_message = st.session_state.get("pending_user_message")
    if pending_message and agent is not None:
        response_chunks: list[str] = []
        response_text = ""
        activity_log: list[str] = []
        with transcript_container:
            with st.chat_message("assistant"):
                text_placeholder = st.empty()
                activity_placeholder = st.empty()
                try:
                    for event in agent.chat_stream(pending_message, st.session_state["api_messages"]):
                        if event["type"] == "text_delta":
                            response_chunks.append(event["text"])
                            response_text = "".join(response_chunks)
                            text_placeholder.markdown(response_text)
                            continue

                        if event["type"] == "tool_start":
                            activity_log.append(_format_tool_start(event["tool_name"], event["tool_input"]))
                            activity_placeholder.markdown(_render_activity_log(activity_log))
                            continue

                        if event["type"] == "tool_result":
                            activity_log.append(_format_tool_result(event["tool_name"], event["result"]))
                            activity_placeholder.markdown(_render_activity_log(activity_log))
                            continue

                        if event["type"] == "done":
                            response_text = event["text"] or response_text
                            if response_text:
                                text_placeholder.markdown(response_text)
                            break

                        if event["type"] == "error":
                            error_note = event["text"]
                            response_text = (
                                f"{response_text}\n\n---\n*{error_note}*"
                                if response_text
                                else error_note
                            )
                            text_placeholder.markdown(response_text)
                            break
                except Exception as exc:
                    response_text = f"Error during streaming response: {exc}"
                    text_placeholder.markdown(response_text)

                if not response_text:
                    response_text = "[No text response returned]"
                    text_placeholder.markdown(response_text)

        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.session_state["pending_user_message"] = None
        st.rerun()


def _to_api_history(history: list[dict]) -> list[dict]:
    """Convert display history to API message format, skipping system-injected messages."""
    api = []
    for message in history:
        if message["role"] == "user":
            api.append({"role": "user", "content": message["content"]})
        elif message["role"] == "assistant" and not message.get("_system"):
            api.append({
                "role": "assistant",
                "content": [{"type": "text", "text": message["content"]}],
            })
    return api


def _format_tool_start(tool_name: str, tool_input: dict) -> str:
    return f"Running `{tool_name}` with `{json.dumps(tool_input, sort_keys=True)}`"


def _format_tool_result(tool_name: str, result: str) -> str:
    preview = " ".join(result.split())
    if len(preview) > 140:
        preview = f"{preview[:137]}..."
    return f"Finished `{tool_name}`: `{preview}`"


def _render_activity_log(activity_log: list[str]) -> str:
    lines = ["**Agent activity**"]
    for line in activity_log[-6:]:
        lines.append(f"- {line}")
    return "\n".join(lines)

