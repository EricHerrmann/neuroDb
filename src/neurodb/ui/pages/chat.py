import os

import streamlit as st
from sqlalchemy import Engine


def render_panel(engine: Engine) -> None:
    st.subheader("Research Assistant")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if "neuro_agent" not in st.session_state:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.warning(
                "ANTHROPIC_API_KEY not found in `.env`. "
                "Add it to enable the Research Assistant."
            )
            return
        import anthropic
        from neurodb.agent import NeuroAgent
        client = anthropic.Anthropic(api_key=api_key)
        vs = st.session_state.get("vector_store")
        st.session_state["neuro_agent"] = NeuroAgent(client, engine, vector_store=vs)

    agent = st.session_state["neuro_agent"]

    # Scrollable message history
    with st.container(height=500):
        for msg in st.session_state["chat_history"]:
            with st.chat_message(msg["role"]):
                st.markdown(msg["content"])

    # Input form — st.chat_input() is page-fixed and cannot live in a column
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
    """Convert display history (role + content str) to API message format."""
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api
