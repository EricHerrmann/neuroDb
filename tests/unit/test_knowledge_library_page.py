import pathlib


def _source() -> str:
    return pathlib.Path("src/neurodb/ui/pages/knowledge_library.py").read_text()


def test_knowledge_library_page_exists():
    assert pathlib.Path("src/neurodb/ui/pages/knowledge_library.py").exists()


def test_knowledge_library_render_function_exists():
    source = _source()
    assert "def render(" in source


def test_knowledge_library_has_pending_and_library_tabs():
    source = _source()
    assert "Pending" in source
    assert "Library" in source


def test_knowledge_library_has_approve_and_reject_actions():
    source = _source()
    assert "Approve" in source
    assert "Reject" in source


def test_knowledge_library_uses_knowledge_source_model():
    assert "KnowledgeSource" in _source()


def test_knowledge_library_adds_summary_to_knowledge_store():
    source = _source()
    assert "knowledge_store" in source
    assert "add_summary" in source


def test_knowledge_library_cards_show_verification_links_and_dedup_warning():
    source = _source()
    assert "https://doi.org/" in source
    assert "_find_near_duplicate" in source
    assert "NEURODB_DEDUP_THRESHOLD" in source
    assert "Similar to approved source" in source


def test_knowledge_library_approved_summary_is_collapsed():
    source = _source()
    assert "Show summary" in source


def test_app_mounts_knowledge_library_tab():
    app_source = pathlib.Path("src/neurodb/ui/app.py").read_text()
    assert "Knowledge Library" in app_source
    assert "knowledge_library" in app_source
