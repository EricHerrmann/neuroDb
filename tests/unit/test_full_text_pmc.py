from pathlib import Path

from neurodb.full_text_client import PmcJatsBackend, parse_jats

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "full_text" / "jats_sample.xml"


def test_parse_jats_yields_titled_sections():
    sections, full_text = parse_jats(_FIXTURE.read_text())
    labels = [s.label for s in sections]
    assert labels == ["Introduction", "Results"]
    assert "hippocampus" in full_text
    for s in sections:
        assert full_text[s.char_start : s.char_end] == s.text


def test_backend_returns_jats_source():
    backend = PmcJatsBackend()
    result = backend._result_from_jats(_FIXTURE.read_text())
    assert result.text_source == "jats"
    assert len(result.sections) == 2
