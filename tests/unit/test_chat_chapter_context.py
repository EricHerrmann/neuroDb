"""
Structural test: the 'Set chapter context' button must only be reachable
when lookup_chapter() returned a truthy result. If lookup returns None,
the button must not be rendered and context must not be set.
"""
import ast
import pathlib


def _get_chat_source() -> str:
    return pathlib.Path("src/neurodb/ui/sidebar.py").read_text()


def test_set_chapter_button_is_guarded_by_lookup_result():
    """
    'Set chapter context' button must appear inside the block where info
    is truthy, not in the fallback (plain-text) branch.
    """
    source = _get_chat_source()
    lines = source.splitlines()

    # Find the line where "Set chapter context" button appears
    btn_line = None
    for i, line in enumerate(lines, start=1):
        if "Set chapter context" in line and "st.button" in line:
            btn_line = i
            break

    assert btn_line is not None, "Could not find 'Set chapter context' button in chat.py"

    # Find the nearest preceding 'if info:' line
    info_guard_line = None
    for i in range(btn_line - 1, 0, -1):
        stripped = lines[i - 1].strip()
        if stripped.startswith("if info") or stripped == "if info:":
            info_guard_line = i
            break

    assert info_guard_line is not None, (
        f"'Set chapter context' button (line {btn_line}) must be inside an 'if info:' guard, "
        "but no such guard was found preceding it."
    )

    # Confirm no fallback warning ("using as plain text") sits between the guard and the button
    for i in range(info_guard_line + 1, btn_line):
        line_text = lines[i - 1]
        assert "using as plain text" not in line_text, (
            f"Fallback warning at line {i} sits between 'if info:' guard and "
            f"'Set chapter context' button — button is not guarded by lookup result."
        )
