import os
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


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


# ---------------------------------------------------------------------------
# _generate_summary env-var config (Task 1.2)
# ---------------------------------------------------------------------------

def _make_knowledge_source(**kwargs):
    defaults = dict(
        title="Hippocampal Place Cells",
        source_type="paper",
        doi="10.1000/xyz",
        url="https://example.com",
        topic_context="spatial navigation",
    )
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def test_generate_summary_default_model_is_haiku():
    """_generate_summary uses Haiku when NEURODB_KNOWLEDGE_SUMMARY_MODEL is not set."""
    from neurodb.ui.pages import knowledge_library

    captured_model = {}

    def fake_create(**kwargs):
        captured_model["model"] = kwargs.get("model")
        block = SimpleNamespace(type="text", text="summary text")
        return SimpleNamespace(content=[block])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    env_without_key = {k: v for k, v in os.environ.items() if k != "NEURODB_KNOWLEDGE_SUMMARY_MODEL"}

    with patch.dict("os.environ", env_without_key, clear=True):
        with patch("anthropic.Anthropic", return_value=mock_client):
            with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "test-key"}):
                knowledge_library._generate_summary(_make_knowledge_source())

    assert captured_model.get("model") == "claude-haiku-4-5-20251001"


def test_generate_summary_reads_neurodb_knowledge_summary_model_env():
    """_generate_summary uses NEURODB_KNOWLEDGE_SUMMARY_MODEL when set."""
    from neurodb.ui.pages import knowledge_library

    captured_model = {}

    def fake_create(**kwargs):
        captured_model["model"] = kwargs.get("model")
        block = SimpleNamespace(type="text", text="summary text")
        return SimpleNamespace(content=[block])

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test-key",
        "NEURODB_KNOWLEDGE_SUMMARY_MODEL": "claude-sentinel-model",
    }):
        with patch("anthropic.Anthropic", return_value=mock_client):
            knowledge_library._generate_summary(_make_knowledge_source())

    assert captured_model.get("model") == "claude-sentinel-model"
