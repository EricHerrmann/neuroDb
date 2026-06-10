from neurodb.full_text_client import (
    FullTextResult,
    SuppliedInput,
    UserSuppliedBackend,
)


class _Paper:
    url = None
    doi = None


def test_markdown_splits_on_headings():
    md = "# Intro\nHello world.\n\n## Methods\nWe did things."
    backend = UserSuppliedBackend()
    supplied = SuppliedInput(text=md, format="md")
    assert backend.can_handle(_Paper(), supplied)
    result = backend.fetch(_Paper(), http=None, supplied=supplied)
    assert isinstance(result, FullTextResult)
    assert result.text_source == "user_supplied"
    labels = [s.label for s in result.sections]
    assert "Intro" in labels and "Methods" in labels
    for s in result.sections:
        assert result.full_text[s.char_start : s.char_end] == s.text


def test_plain_text_is_single_section():
    backend = UserSuppliedBackend()
    supplied = SuppliedInput(text="Just one block of prose.", format="txt")
    result = backend.fetch(_Paper(), http=None, supplied=supplied)
    assert len(result.sections) == 1
    assert result.sections[0].text == "Just one block of prose."


def test_cannot_handle_without_text():
    assert not UserSuppliedBackend().can_handle(_Paper(), SuppliedInput(url="http://x"))
