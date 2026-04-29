import os

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine) -> None:
    st.subheader("Research Assistant")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    _init_agent(engine)

    agent = st.session_state.get("neuro_agent")
    if agent is None:
        return

    session_active = "session_id" in st.session_state

    if not session_active:
        _render_start_session()
        return

    _render_end_session_button(engine)
    _render_chat(agent)


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
    st.caption("Start a session to begin chatting. The agent will retrieve prior context for your topic.")
    topic = st.text_input("Topic (optional)", placeholder="e.g. hippocampus place cells")
    if st.button("Start Session", use_container_width=True):
        manager = st.session_state.get("session_manager")
        if manager:
            session_id, context = manager.start_session(topic.strip())
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
            })
        st.rerun()


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
        # Reset for next session
        for key in ("session_topic", "chat_history"):
            st.session_state.pop(key, None)
        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.prior_context = ""
        st.rerun()


def _render_chat(agent) -> None:
    with st.container(height=460):
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    with st.form("agent_form", clear_on_submit=True):
        user_input = st.text_input(
            "Message",
            placeholder="Ask about your datasets…",
            label_visibility="collapsed",
        )
        submitted = st.form_submit_button("Send", use_container_width=True)

    if submitted and user_input.strip():
        message = user_input.strip()
        st.session_state["chat_history"].append({"role": "user", "content": message})
        api_history = _to_api_history(st.session_state["chat_history"][:-1])
        with st.spinner("Thinking…"):
            chunks = list(agent.chat(message, api_history))
        response_text = "".join(chunks)
        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})
        st.rerun()


def _to_api_history(history: list[dict]) -> list[dict]:
    """Convert display history to API message format, skipping context-injection messages."""
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant" and not msg["content"].startswith("**Prior context loaded"):
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api
