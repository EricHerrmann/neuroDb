from pathlib import Path

from neurodb.chunking import chunk_sections
from neurodb.full_text_client import classify_for_phase2b, SuppliedInput
from neurodb.tex_parser import parse_tex


def _build_project(d: Path) -> Path:
    proj = d / "arxiv_paper"
    proj.mkdir()
    (proj / "main.tex").write_text(
        r"""\documentclass{article}
\begin{document}
Intro about synaptic plasticity and memory consolidation in the mammalian hippocampus.
\section{Methods}
We recorded $V_m$ from CA1 pyramidal neurons across repeated stimulation trials.
\input{results}
\end{document}
"""
    )
    (proj / "results.tex").write_text(
        r"\section{Results} Long-term potentiation was reliably induced and measured."
    )
    (proj / "refs.bbl").write_text(r"\bibitem{a} Bliss and Lomo, 1973.")
    return proj


def test_tex_project_parses_to_chunks(tmp_path):
    proj = _build_project(tmp_path)
    art = parse_tex(proj)
    chunks = chunk_sections(art.sections)
    assert chunks, "expected at least one chunk"
    assert all(c.page is None for c in chunks)
    assert {"Methods", "Results", "References"} <= {c.section for c in chunks}


def test_tex_ingest_is_idempotent(tmp_path):
    proj = _build_project(tmp_path)
    first = chunk_sections(parse_tex(proj).sections)
    second = chunk_sections(parse_tex(proj).sections)
    assert len(first) == len(second)
    assert [c.text for c in first] == [c.text for c in second]
    assert [c.chunk_index for c in first] == [c.chunk_index for c in second]


def test_tex_folder_routes_to_phase2b(tmp_path):
    proj = _build_project(tmp_path)
    paper = type("P", (), {"url": None, "doi": None, "id": 1, "open_access_pdf": None})()
    assert classify_for_phase2b(paper, SuppliedInput(path=str(proj))) == "phase2b"
