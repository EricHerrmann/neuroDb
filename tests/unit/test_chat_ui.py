import pathlib
from unittest.mock import MagicMock

from neurodb.ui.pages import chat


class _ContextRecorder:
    def __init__(self, events: list[tuple[str, str]]) -> None:
        self._events = events

    def __call__(self, name: str):
        return _ContextManager(self._events, name)


class _ContextManager:
    def __init__(self, events: list[tuple[str, str]], name: str) -> None:
        self._events = events
        self._name = name

    def __enter__(self):
        self._events.append(("enter", self._name))
        return self

    def __exit__(self, exc_type, exc, tb):
        self._events.append(("exit", self._name))
        return False


def test_render_chat_renders_transcript_container(monkeypatch):
    calls = []
    ctx = _ContextRecorder([])

    monkeypatch.setattr(chat.st, "session_state", {"chat_history": []})
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: calls.append(kwargs) or ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content, **kwargs: None)

    chat._render_chat(agent=MagicMock(), transcript_height=480)

    assert calls[0] == {"height": 480, "border": False}


def test_render_chat_shows_placeholder_when_history_empty(monkeypatch):
    events: list[tuple[str, str]] = []
    ctx = _ContextRecorder(events)

    monkeypatch.setattr(chat.st, "session_state", {"chat_history": [], "api_messages": [], "pending_user_message": None})
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content, **kwargs: events.append(("markdown", content)))

    chat._render_chat(agent=MagicMock())

    assert ("enter", "chat_message:assistant") in events
    assert any("Chat ready" in content for kind, content in events if kind == "markdown")


def test_render_chat_processes_pending_message_inside_transcript(monkeypatch):
    events: list[tuple[str, str]] = []
    ctx = _ContextRecorder(events)

    class _Placeholder:
        def markdown(self, content):
            events.append(("placeholder_markdown", content))

    class _Agent:
        def chat_stream(self, message, api_messages):
            assert message == "How many datasets?"
            yield {"type": "text_delta", "text": "There are "}
            yield {"type": "done", "text": "There are 5 datasets."}

    rerun_called = {"value": False}

    monkeypatch.setattr(
        chat.st,
        "session_state",
        {
            "chat_history": [{"role": "user", "content": "How many datasets?"}],
            "api_messages": [],
            "pending_user_message": "How many datasets?",
        },
    )
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:composer"), ctx("column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content, **kwargs: events.append(("markdown", content)))
    monkeypatch.setattr(chat.st, "empty", lambda: _Placeholder())
    monkeypatch.setattr(chat.st, "rerun", lambda: rerun_called.__setitem__("value", True))

    chat._render_chat(agent=_Agent())

    assert rerun_called["value"] is True
    assert ("enter", "chat_message:user") in events
    assert ("enter", "chat_message:assistant") in events
    assert ("placeholder_markdown", "There are ") in events
    assert chat.st.session_state["chat_history"] == [
        {"role": "user", "content": "How many datasets?"},
        {"role": "assistant", "content": "There are 5 datasets."},
    ]
    assert chat.st.session_state["pending_user_message"] is None


def test_render_chat_enter_submits_send_not_clear(monkeypatch):
    rerun_called = {"value": False}
    submit_labels: list[str] = []
    clear_labels: list[str] = []

    class _Agent:
        prior_context = ""

        def chat_stream(self, message, api_messages):
            assert message == "hi"
            yield {"type": "done", "text": "hello"}

    monkeypatch.setattr(
        chat.st,
        "session_state",
        {"chat_history": [], "api_messages": [], "pending_user_message": None},
    )
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: _ContextManager([], "container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: _ContextManager([], f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: _ContextManager([], f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [_ContextManager([], "column:composer"), _ContextManager([], "column:clear")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "hi")
    monkeypatch.setattr(
        chat.st,
        "form_submit_button",
        lambda label, **kwargs: submit_labels.append(label) or True,
    )
    monkeypatch.setattr(
        chat.st,
        "button",
        lambda label, **kwargs: clear_labels.append(label) or False,
    )
    monkeypatch.setattr(chat.st, "markdown", lambda content, **kwargs: None)
    monkeypatch.setattr(chat.st, "rerun", lambda: rerun_called.__setitem__("value", True))

    chat._render_chat(agent=_Agent())

    assert submit_labels == ["Send"]
    assert clear_labels == ["Clear"]
    assert rerun_called["value"] is True
    assert chat.st.session_state["chat_history"] == [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "content": "hello"},
    ]
    assert chat.st.session_state["pending_user_message"] is None


def test_no_learning_or_discovery_mode_strings_in_chat():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert '"learning"' not in source
    assert '"discovery"' not in source


def test_four_mode_options_present_in_sidebar():
    source = pathlib.Path("src/neurodb/ui/sidebar.py").read_text()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source
    assert "neuro_research" in source


def test_chat_init_knows_research_agent():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert "NeuroResearchAgent" in source
    assert "neuro_research" in source


def test_tool_start_activity_can_show_budget():
    text = chat._format_tool_start("query_db", {"sql": "SELECT 1"}, 3, 25)
    assert text.startswith("Step 3/25")
    assert "query_db" in text


def test_chat_has_no_mode_radio():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert "st.radio" not in source


def test_no_start_or_end_session_buttons_in_chat():
    source = pathlib.Path("src/neurodb/ui/pages/chat.py").read_text()
    assert "Start Session" not in source
    assert "End Session" not in source
