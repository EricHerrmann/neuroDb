import json
import os
import uuid
from datetime import date, datetime, timezone

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

    prior_topic = st.session_state.get("active_prior_topic", "")
    if prior_topic:
        st.markdown(
            f'<div style="background:#1e3a8a;color:#f8fafc;padding:0.3rem 0.75rem;'
            f'border-radius:0.5rem;font-size:0.85rem;margin-bottom:0.4rem;">'
            f'Prior context: {prior_topic[:80]}</div>',
            unsafe_allow_html=True,
        )

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
    from neurodb.config.providers.anthropic_client import AnthropicModelClient
    from neurodb.config.task_router import TaskRouter

    sdk_client = anthropic.Anthropic(api_key=api_key)
    model_client = AnthropicModelClient(sdk_client)
    router = TaskRouter({"anthropic": model_client})

    vector_store = st.session_state.get("vector_store")
    mode = st.session_state.get("agent_mode", "local_db")

    if mode == "neuro_tutor":
        from neurodb.agents.tutor_agent import NeuroTutorAgent

        mc, model_id, max_tok = router.route("agent.loop.neuro_tutor")
        st.session_state["neuro_agent"] = NeuroTutorAgent(
            model_client=mc,
            model=model_id,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=st.session_state.get("knowledge_store"),
            prior_context=st.session_state.get("active_prior_context", ""),
        )
        return

    if mode == "neuro_research":
        from neurodb.agents.research_agent import NeuroResearchAgent

        manager = st.session_state.get("session_manager")
        mc, model_id, max_tok = router.route("agent.loop.neuro_research")
        st.session_state["neuro_agent"] = NeuroResearchAgent(
            model_client=mc,
            model=model_id,
            max_tokens=max_tok,
            engine=engine,
            vector_store=vector_store,
            knowledge_store=st.session_state.get("knowledge_store"),
            prior_context=st.session_state.get("active_prior_context", ""),
            context_store=getattr(manager, "_store", None),
            current_date=date.today().isoformat(),
        )
        return

    from neurodb.agents.db_agent import NeuroDbAgent

    task_type = f"agent.loop.{mode}" if mode in {"local_db", "external_db"} else "agent.loop.local_db"
    mc, model_id, max_tok = router.route(task_type)
    st.session_state["neuro_agent"] = NeuroDbAgent(
        model_client=mc,
        model=model_id,
        max_tokens=max_tok,
        engine=engine,
        vector_store=vector_store,
        mode=mode,
        chapter_context=st.session_state.get("chapter_context", ""),
        prior_context=st.session_state.get("active_prior_context", ""),
    )


def _auto_start_session(first_message: str) -> None:
    session_id = str(uuid.uuid4())
    st.session_state["session_id"] = session_id
    st.session_state["session_started_at"] = datetime.now(timezone.utc).isoformat()

    engine = st.session_state.get("engine")
    if engine is not None:
        _write_chat_session_draft(engine, session_id, first_message)

    manager = st.session_state.get("session_manager")
    context = st.session_state.get("active_prior_context", "")
    if not context:
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


def clear_chat_state_for_context_switch() -> None:
    """Clear transient chat state before loading a different prior-context session."""
    st.session_state["chat_history"] = []
    st.session_state["api_messages"] = []
    st.session_state["pending_user_message"] = None
    st.session_state.pop("session_id", None)
    st.session_state.pop("session_started_at", None)
    st.session_state.pop("neuro_agent", None)


def _write_chat_session_draft(engine, session_id: str, first_message: str) -> None:
    from neurodb.db import get_session
    from neurodb.schema import ChatSession

    with get_session(engine) as session:
        existing = session.query(ChatSession).filter_by(session_id=session_id).one_or_none()
        if existing is None:
            session.add(ChatSession(
                session_id=session_id,
                inferred_topic=first_message[:200],
                agent_mode=st.session_state.get("agent_mode", "local_db"),
                started_at=datetime.now(timezone.utc).isoformat(),
                ended_at=None,
                summary_preview=None,
                message_count=0,
            ))


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
    ended_at = datetime.now(timezone.utc).isoformat()
    with get_session(engine) as session:
        row = session.query(ChatSession).filter_by(session_id=session_id).one_or_none()
        if row is not None:
            row.inferred_topic = first_user[:200]
            row.ended_at = ended_at
            row.summary_preview = summary[:200]
            row.message_count = user_turns
        else:
            session.add(ChatSession(
                session_id=session_id,
                inferred_topic=first_user[:200],
                agent_mode=st.session_state.get("agent_mode", "local_db"),
                started_at=st.session_state.get(
                    "session_started_at",
                    datetime.now(timezone.utc).isoformat(),
                ),
                ended_at=ended_at,
                summary_preview=summary[:200],
                message_count=user_turns,
            ))


def _render_chat(agent, transcript_height: int = 420) -> None:
    transcript_container = st.container(height=transcript_height, border=False)
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
        clear_chat_state_for_context_switch()
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
                            activity_log.append(_format_tool_start(
                                event["tool_name"],
                                event["tool_input"],
                                event.get("iteration"),
                                event.get("limit"),
                            ))
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
        st.markdown(
            """
            <script>
            (function() {
              const wrappers = window.parent.document.querySelectorAll(
                '[data-testid="stVerticalBlockBorderWrapper"]'
              );
              const el = wrappers[wrappers.length - 1];
              if (el) { el.scrollTop = el.scrollHeight; }
            })();
            </script>
            """,
            unsafe_allow_html=True,
        )
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


def _format_tool_start(
    tool_name: str,
    tool_input: dict,
    iteration: int | None = None,
    limit: int | None = None,
) -> str:
    prefix = f"Step {iteration}/{limit}: " if iteration and limit else ""
    return f"{prefix}Running `{tool_name}` with `{json.dumps(tool_input, sort_keys=True)}`"


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
