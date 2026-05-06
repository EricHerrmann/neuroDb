import ast
import pathlib


def _get_source() -> str:
    return pathlib.Path("src/neurodb/ui/sidebar.py").read_text()


def _get_tree() -> ast.AST:
    return ast.parse(_get_source())


def test_sidebar_module_defines_render_sidebar():
    tree = _get_tree()
    fn_names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert "render_sidebar" in fn_names
    assert "_render_previous_topics" in fn_names
    assert "_render_connections" in fn_names


def test_sidebar_contains_mode_radio():
    source = _get_source()
    assert "st.radio" in source


def test_sidebar_contains_all_four_mode_keys():
    source = _get_source()
    assert "local_db" in source
    assert "external_db" in source
    assert "neuro_tutor" in source
    assert "neuro_research" in source


def test_sidebar_persists_agent_mode_selection():
    source = _get_source()
    assert "save_app_preference" in source
    assert "agent_mode" in source


def test_sidebar_contains_chapter_controls():
    source = _get_source()
    assert "st.selectbox" in source
    assert "st.text_input" in source


def test_set_chapter_button_guarded_by_lookup_result():
    source = _get_source()
    lines = source.splitlines()
    btn_line = None
    for i, line in enumerate(lines, start=1):
        if "Set chapter context" in line and "st.button" in line:
            btn_line = i
            break
    assert btn_line is not None, "Could not find 'Set chapter context' button in sidebar.py"
    info_guard_line = None
    for i in range(btn_line - 1, 0, -1):
        stripped = lines[i - 1].strip()
        if stripped.startswith("if info") or stripped == "if info:":
            info_guard_line = i
            break
    assert info_guard_line is not None, (
        f"'Set chapter context' button (line {btn_line}) must be inside an 'if info:' guard"
    )


def test_sidebar_does_not_contain_form_or_chat_state():
    source = _get_source()
    assert "st.form(" not in source
    assert "pending_user_message" not in source


def test_sidebar_contains_previous_topics_and_connections_sections():
    source = _get_source()
    assert "Previous Topics" in source
    assert "Connections" in source
    assert "NCBI_API_KEY" in source
    assert "SEMANTIC_SCHOLAR_API_KEY" in source
    assert "new_connector" in source
