import os
import pathlib
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.config.model_client import ContentBlock, ModelResponse
from neurodb.schema import Base, Paper, ModelCallLog


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
    assert "Paper" in _source()


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
    """_generate_summary routes to economy tier via TaskRouter when NEURODB_KNOWLEDGE_SUMMARY_MODEL is not set."""
    from neurodb.ui.pages import knowledge_library

    model_client = MagicMock()
    model_client.create_message.return_value = ModelResponse(
        stop_reason="end_turn",
        content=[ContentBlock(type="text", text="summary text")],
        input_tokens=20,
        output_tokens=8,
    )

    with patch(
        "neurodb.config.provider_factory.build_provider_clients",
        return_value={"anthropic": model_client},
    ):
        with patch.dict("os.environ", {}, clear=True):
            summary, telemetry = knowledge_library._generate_summary(_make_knowledge_source())

    assert summary == "summary text"
    assert telemetry is not None
    assert telemetry["provider"] == "anthropic"
    assert telemetry["task_type"] == "summary.knowledge_source"


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


def test_approve_source_logs_knowledge_summary_telemetry():
    from neurodb.ui.pages import knowledge_library

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        source = Paper(
            title="Hippocampal Place Cells",
            normalized_title="hippocampal place cells",
            doi="10.1000/xyz",
            url="https://example.com",
            source_type="paper",
            topic_context="spatial navigation",
            status="pending",
            queued_at="2026-05-07T00:00:00",
        )
        session.add(source)
        session.commit()
        source_id = source.id

    def fake_create(**kwargs):
        block = SimpleNamespace(type="text", text="summary text")
        usage = SimpleNamespace(input_tokens=25, output_tokens=9)
        return SimpleNamespace(stop_reason="end_turn", content=[block], usage=usage)

    mock_client = MagicMock()
    mock_client.messages.create.side_effect = fake_create

    with patch.dict("os.environ", {
        "ANTHROPIC_API_KEY": "test-key",
        "NEURODB_KNOWLEDGE_SUMMARY_MODEL": "claude-test-summary",
    }):
        with patch("anthropic.Anthropic", return_value=mock_client):
            with patch.object(knowledge_library.st, "session_state", {}):
                knowledge_library._approve_source(engine, source_id)

    with Session(engine) as session:
        source = session.query(Paper).filter_by(id=source_id).one()
        row = session.query(ModelCallLog).one()
        assert source.status == "approved"
        assert source.summary == "summary text"
        assert row.task_type == "summary.knowledge_source"
        assert row.model == "claude-test-summary"
        assert row.input_tokens == 25
        assert row.output_tokens == 9


def test_generate_summary_can_route_economy_tier_to_openai(monkeypatch):
    from neurodb.ui.pages import knowledge_library
    import neurodb.config.model_config as mc

    model_client = MagicMock()
    model_client.create_message.return_value = ModelResponse(
        stop_reason="end_turn",
        content=[ContentBlock(type="text", text="summary text")],
        input_tokens=20,
        output_tokens=8,
    )
    base = mc.load_model_config()
    patched_cfg = {**base, "routing": {**base.get("routing", {}), "economy": "openai"}}
    monkeypatch.setattr(mc, "_cache", patched_cfg)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("NEURODB_KNOWLEDGE_SUMMARY_MODEL", raising=False)

    with patch(
        "neurodb.config.provider_factory.build_provider_clients",
        return_value={"openai": model_client},
    ):
        summary, telemetry = knowledge_library._generate_summary(_make_knowledge_source())

    assert summary == "summary text"
    assert telemetry["provider"] == "openai"
    assert telemetry["model"] == "gpt-5.4-mini"
    assert telemetry["task_type"] == "summary.knowledge_source"


def test_generate_summary_without_api_key_returns_no_telemetry():
    from neurodb.ui.pages import knowledge_library

    with patch.dict("os.environ", {}, clear=True):
        summary, telemetry = knowledge_library._generate_summary(_make_knowledge_source())

    assert "Key concepts" in summary
    assert telemetry is None
