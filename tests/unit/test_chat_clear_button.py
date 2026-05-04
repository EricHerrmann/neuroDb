"""
Structural tests confirming the Clear button in chat.py:
- Is NOT nested inside the st.form("agent_form") block
- Uses st.button(), not st.form_submit_button()
- Is checked independently from the form's submitted variable
"""
import ast
import pathlib


def _get_chat_source() -> str:
    return (pathlib.Path("src/neurodb/ui/pages/chat.py")).read_text()


def _find_form_blocks(tree: ast.AST) -> list[tuple[int, int]]:
    """Return (start_line, end_line) for every `with st.form(...)` block."""
    blocks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if (
                    isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Attribute)
                    and expr.func.attr == "form"
                ):
                    blocks.append((node.lineno, node.end_lineno))
    return blocks


def _find_clear_button_line(tree: ast.AST) -> int | None:
    """Return the line number of st.button("Clear", ...) — matched by exact label."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "button"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).lower() == "clear"
        ):
            return node.lineno
    return None


def test_clear_button_is_outside_agent_form():
    """Clear button must not be nested inside any st.form(...) block."""
    source = _get_chat_source()
    tree = ast.parse(source)

    form_blocks = _find_form_blocks(tree)
    assert form_blocks, "No st.form(...) block found in chat.py — test assumptions broken"

    clear_btn_line = _find_clear_button_line(tree)
    assert clear_btn_line is not None, (
        'No st.button("Clear", ...) found in chat.py'
    )

    for form_start, form_end in form_blocks:
        assert not (form_start <= clear_btn_line <= form_end), (
            f"Clear button (line {clear_btn_line}) is inside a st.form block "
            f"(lines {form_start}–{form_end}). It must be outside the form."
        )


def test_clear_button_uses_st_button_not_form_submit():
    """Clear action must use st.button(), not st.form_submit_button()."""
    source = _get_chat_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "form_submit_button"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and "clear" in str(node.args[0].value).lower()
        ):
            raise AssertionError(
                f"Line {node.lineno}: Clear is implemented as st.form_submit_button — "
                "it will fire on Enter. Use st.button() outside the form instead."
            )

    clear_btn_line = _find_clear_button_line(tree)
    assert clear_btn_line is not None, (
        'No st.button("Clear", ...) found — Clear button may be missing or mislabeled.'
    )


def test_submit_and_clear_are_separate_variables():
    """submitted (form) and clear_clicked (button) must be separate, not OR-combined."""
    source = _get_chat_source()

    assert "clear_clicked" in source, "Expected variable 'clear_clicked' in chat.py"
    assert "submitted" in source, "Expected variable 'submitted' in chat.py"

    for line in source.splitlines():
        if "submitted" in line and "clear_clicked" in line and " or " in line:
            raise AssertionError(
                f"submitted and clear_clicked are combined with 'or': {line!r}. "
                "They must be checked independently."
            )
