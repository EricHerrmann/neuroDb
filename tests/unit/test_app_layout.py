import pathlib


APP_SOURCE = pathlib.Path("src/neurodb/ui/app.py")


def test_app_uses_marker_scoped_fixed_pane_layout():
    source = APP_SOURCE.read_text()

    assert "ndb-chat-pane-marker" in source
    assert "ndb-workspace-pane-marker" in source
    assert "div[data-testid=\"stHorizontalBlock\"]:has(.ndb-chat-pane-marker):has(.ndb-workspace-pane-marker)" in source
    assert "div[data-testid=\"stColumn\"]:has(.ndb-chat-pane-marker)" in source
    assert "div[data-testid=\"stColumn\"]:has(.ndb-workspace-pane-marker)" in source
    assert "overflow: hidden !important" in source
    assert "overflow-y: auto" in source


def test_chat_panel_uses_viewport_safe_transcript_height():
    source = APP_SOURCE.read_text()

    assert "render_panel(engine, transcript_height=480)" in source
