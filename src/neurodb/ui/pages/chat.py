import os

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    _init_agent(engine)

    agent = st.session_state.get("neuro_agent")
    session_active = "session_id" in st.session_state

    if not session_active:
        _render_start_session()
        return

    if agent is None:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable chat during a session.")
        _render_end_session_button(engine)
        return
    _render_chat(agent)
    _render_end_session_button(engine)


def _init_agent(engine: Engine) -> None:
    if "neuro_agent" in st.session_state:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable the Research Assistant.")
        return
    import anthropic
    from neurodb.agent import NeuroAgent
    client = anthropic.Anthropic(api_key=api_key)
    vs = st.session_state.get("vector_store")
    st.session_state["neuro_agent"] = NeuroAgent(client, engine, vector_store=vs)


def _render_start_session() -> None:
    from neurodb.prefs import load_prefs, save_prefs

    if "relevance_threshold" not in st.session_state:
        st.session_state["relevance_threshold"] = load_prefs()["relevance_threshold"]

    topic = st.text_input("Topic (optional)", placeholder="e.g. hippocampus place cells")

    threshold = st.slider(
        "Context relevance",
        min_value=0.1,
        max_value=1.0,
        value=st.session_state["relevance_threshold"],
        step=0.1,
        help="Lower = stricter topic match only; Higher = broader, more loosely related sessions included",
        key="relevance_threshold",
    )

    if st.button("Start Session", use_container_width=True):
        save_prefs({"relevance_threshold": threshold})

        manager = st.session_state.get("session_manager")
        if manager:
            session_id, context = manager.start_session(topic.strip(), threshold=threshold)
        else:
            import uuid
            session_id, context = str(uuid.uuid4()), ""
        st.session_state["session_id"] = session_id
        st.session_state["session_topic"] = topic.strip()
        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.prior_context = context
        if context:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": f"**Prior context loaded:**\n\n{context}",
                "_system": True,
            })
        else:
            st.session_state["chat_history"].append({
                "role": "assistant",
                "content": "No prior context found for this topic.",
                "_system": True,
            })
        st.rerun()
    st.caption("The agent will retrieve prior context for your topic.")


def _render_end_session_button(engine: Engine) -> None:
    topic = st.session_state.get("session_topic", "")
    label = f"Session: {topic}" if topic else "Session active"
    st.caption(label)
    if st.button("End Session", use_container_width=True):
        manager = st.session_state.get("session_manager")
        session_id = st.session_state.pop("session_id", None)
        if manager and session_id:
            api_history = _to_api_history(st.session_state["chat_history"])
            with st.spinner("Saving session summary…"):
                manager.end_session(session_id, api_history)
        for key in ("session_topic", "chat_history"):
            st.session_state.pop(key, None)
        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.prior_context = ""
        st.rerun()


def _render_chat(agent) -> None:
    with st.container(height=200):
        for msg in st.session_state["chat_history"]:
            if msg.get("_system"):
                continue
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.form("agent_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="Ask about your datasets…",
            label_visibility="collapsed",
        )
        col_clear, col_send = st.columns([1, 2])
        with col_clear:
            clear_clicked = st.form_submit_button("Clear", use_container_width=True)
        with col_send:
            submitted = st.form_submit_button("Send", use_container_width=True)

    if clear_clicked:
        st.session_state["chat_history"] = []
        st.rerun()
    elif submitted and user_input.strip():
        message = user_input.strip()
        st.session_state["chat_history"].append({"role": "user", "content": message})
        api_history = _to_api_history(st.session_state["chat_history"][:-1])
        with st.spinner("Thinking…"):
            chunks = list(agent.chat(message, api_history))
        response_text = "".join(chunks)
        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.rerun()

    last_response = next(
        (msg["content"] for msg in reversed(st.session_state["chat_history"])
         if msg["role"] == "assistant"),
        None,
    )
    if last_response:
        st.divider()
        st.markdown(last_response)


def _to_api_history(history: list[dict]) -> list[dict]:
    """Convert display history to API message format, skipping system-injected messages."""
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and not msg.get("_system"):
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api
