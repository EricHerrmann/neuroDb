from neurodb.chunking import Chunk, Section, chunk_sections


def _sec(label, text, start):
    return Section(label=label, text=text, char_start=start, char_end=start + len(text))


def test_small_section_becomes_one_chunk():
    secs = [_sec("Intro", "Short intro text.", 0)]
    chunks = chunk_sections(secs, max_chars=100, overlap=10)
    assert len(chunks) == 1
    c = chunks[0]
    assert c.section == "Intro"
    assert c.text == "Short intro text."
    assert c.char_start == 0
    assert c.char_end == len("Short intro text.")
    assert c.chunk_index == 0


def test_oversize_section_splits_with_overlap():
    body = "x" * 250
    chunks = chunk_sections([_sec("Methods", body, 1000)], max_chars=100, overlap=20)
    assert len(chunks) >= 3
    assert all(c.section == "Methods" for c in chunks)
    assert chunks[0].char_start == 1000
    assert chunks[1].char_start < chunks[0].char_end
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_indices_run_across_sections():
    secs = [_sec("A", "a" * 50, 0), _sec("B", "b" * 50, 50)]
    chunks = chunk_sections(secs, max_chars=100, overlap=0)
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_empty_sections_yield_no_chunks():
    assert chunk_sections([_sec("Empty", "   ", 0)], max_chars=100, overlap=0) == []
