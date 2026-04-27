import os

import streamlit as st
from sqlalchemy import Engine


def render(engine: Engine) -> None:
    st.header("Agent Chat")
    st.caption("Ask questions about your datasets. The agent queries the database to ground its answers.")

    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    if "neuro_agent" not in st.session_state:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            st.error(
                "ANTHROPIC_API_KEY environment variable is not set. "
                "Set it before starting the server to enable Agent Chat."
            )
            return
        import anthropic
        from neurodb.agent import NeuroAgent
        client = anthropic.Anthropic(api_key=api_key)
        vs = st.session_state.get("vector_store")
        st.session_state["neuro_agent"] = NeuroAgent(client, engine, vector_store=vs)

    agent = st.session_state["neuro_agent"]

    for msg in st.session_state["chat_history"]:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask about your datasets…")
    if user_input:
        st.session_state["chat_history"].append({"role": "user", "content": user_input})
        with st.chat_message("user"):
            st.markdown(user_input)

        api_history = _to_api_history(st.session_state["chat_history"][:-1])

        with st.chat_message("assistant"):
            with st.spinner("Thinking…"):
                chunks = list(agent.chat(user_input, api_history))
            response_text = "".join(chunks)
            st.markdown(response_text)

        st.session_state["chat_history"].append({"role": "assistant", "content": response_text})


def _to_api_history(history: list[dict]) -> list[dict]:
    """Convert display history (role+content str) to API message format."""
    api = []
    for msg in history:
        if msg["role"] == "user":
            api.append({"role": "user", "content": msg["content"]})
        elif msg["role"] == "assistant":
            api.append({"role": "assistant", "content": [{"type": "text", "text": msg["content"]}]})
    return api
