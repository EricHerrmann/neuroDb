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


def test_render_chat_shows_session_start_response_after_form(monkeypatch):
    events: list[tuple[str, str]] = []
    ctx = _ContextRecorder(events)

    monkeypatch.setattr(
        chat.st,
        "session_state",
        {
            "chat_history": [
                {
                    "role": "assistant",
                    "content": "No prior context found for this topic.",
                    "_system": True,
                }
            ]
        },
    )
    monkeypatch.setattr(chat.st, "container", lambda **kwargs: ctx("container"))
    monkeypatch.setattr(chat.st, "chat_message", lambda role: ctx(f"chat_message:{role}"))
    monkeypatch.setattr(chat.st, "form", lambda name, clear_on_submit=True: ctx(f"form:{name}"))
    monkeypatch.setattr(chat.st, "columns", lambda spec: [ctx("column:clear"), ctx("column:send")])
    monkeypatch.setattr(chat.st, "text_input", lambda *args, **kwargs: "")
    monkeypatch.setattr(chat.st, "form_submit_button", lambda *args, **kwargs: False)
    monkeypatch.setattr(chat.st, "markdown", lambda content: events.append(("markdown", content)))
    monkeypatch.setattr(chat.st, "divider", lambda: events.append(("divider", "")))
    monkeypatch.setattr(
        chat.st,
        "rerun",
        lambda: (_ for _ in ()).throw(AssertionError("rerun should not be called")),
    )

    chat._render_chat(agent=MagicMock())

    assert events.count(("markdown", "No prior context found for this topic.")) == 1
    assert ("enter", "chat_message:assistant") not in events
    assert events.index(("markdown", "No prior context found for this topic.")) > events.index(
        ("exit", "form:agent_form")
    )
