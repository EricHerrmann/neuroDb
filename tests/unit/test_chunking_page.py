from neurodb.chunking import Section, chunk_sections


def test_chunk_carries_page_from_section():
    secs = [Section(label="Intro", text="hello world", char_start=0, char_end=11, page=3)]
    chunks = chunk_sections(secs)
    assert chunks[0].page == 3


def test_section_page_defaults_none():
    secs = [Section(label=None, text="abc", char_start=0, char_end=3)]
    assert chunk_sections(secs)[0].page is None
