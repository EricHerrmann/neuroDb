import ast
import pathlib


def _source() -> str:
    return pathlib.Path("src/neurodb/ui/pages/research.py").read_text()


def test_research_page_defines_render():
    tree = ast.parse(_source())
    names = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    assert "render" in names
    assert "_render_metrics" in names
    assert "_render_questions" in names
    assert "_render_hypotheses" in names


def test_research_page_renders_metrics_and_snapshot_action():
    source = _source()
    assert "get_knowledge_growth_metrics" in source
    assert "Snapshot metrics" in source
    assert "Approved sources" in source
    assert "Literature searches" in source


def test_research_page_lists_questions_and_hypotheses_with_status_filters():
    source = _source()
    assert "Research Questions" in source
    assert "Draft Hypotheses" in source
    assert "Question status" in source
    assert "Hypothesis status" in source


def test_app_defines_research_tab():
    source = pathlib.Path("src/neurodb/ui/app.py").read_text()
    assert '"Research"' in source
    assert "neurodb.ui.pages.research" in source
