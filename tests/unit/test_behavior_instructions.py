from neurodb.agents.behavior_instructions import (
    CITATION_PROVENANCE_RULE,
    data_tier_label,
    load_agent_behavior_instructions,
)


def test_data_tier_label_maps_known_values():
    assert data_tier_label("metadata") == "metadata"
    assert data_tier_label("abstract") == "abstract"
    assert data_tier_label("full_text") == "full text"


def test_data_tier_label_falls_back_to_metadata():
    assert data_tier_label(None) == "metadata"
    assert data_tier_label("") == "metadata"
    assert data_tier_label("weird") == "metadata"
    assert data_tier_label(" Full_Text ") == "full text"


def test_citation_rule_mentions_key_elements():
    text = CITATION_PROVENANCE_RULE
    assert "Knowledge Library" in text
    assert "full text" in text
    assert "URL" in text or "url" in text
    # Knowledge Library citations must be clickable internal deep links carrying the paper id.
    assert "/knowledge-library?focus=" in text
    assert "source_id" in text


def test_load_behavior_instructions_from_configured_path(tmp_path, monkeypatch):
    behavior_path = tmp_path / "behavior.md"
    behavior_path.write_text(
        "# Agent Behavior\n\nBe direct and challenge assumptions with evidence.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NEURODB_AGENT_BEHAVIOR_PATH", str(behavior_path))

    instructions = load_agent_behavior_instructions()

    assert "Additional agent behavior instructions:" in instructions
    assert "Be direct and challenge assumptions with evidence." in instructions


def test_load_behavior_instructions_returns_empty_for_missing_configured_path(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv(
        "NEURODB_AGENT_BEHAVIOR_PATH",
        str(tmp_path / "missing.md"),
    )

    assert load_agent_behavior_instructions() == ""


def test_load_behavior_instructions_extracts_marked_section(tmp_path, monkeypatch):
    behavior_path = tmp_path / "AGENTS.md"
    behavior_path.write_text(
        "# Full instructions\n\n"
        "Coding-agent process rules should stay out.\n\n"
        "<!-- neurodb-agent-behavior:start -->\n"
        "Challenge assumptions when evidence warrants it.\n"
        "<!-- neurodb-agent-behavior:end -->\n\n"
        "More coding-agent instructions should stay out.\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("NEURODB_AGENT_BEHAVIOR_PATH", str(behavior_path))

    instructions = load_agent_behavior_instructions()

    assert "Challenge assumptions when evidence warrants it." in instructions
    assert "Coding-agent process rules" not in instructions
    assert "More coding-agent instructions" not in instructions


def test_load_behavior_instructions_applies_character_limit(tmp_path, monkeypatch):
    behavior_path = tmp_path / "behavior.md"
    behavior_path.write_text("First sentence. Second sentence.", encoding="utf-8")
    monkeypatch.setenv("NEURODB_AGENT_BEHAVIOR_PATH", str(behavior_path))

    instructions = load_agent_behavior_instructions(max_chars=14)

    assert "First sentence" in instructions
    assert "Second sentence" not in instructions
    assert "truncated to configured limit" in instructions
