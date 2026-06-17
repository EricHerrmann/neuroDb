import pytest

from neurodb.tex_parser import _expand_includes, _find_main_tex


def _write_main(d, name="main.tex"):
    (d / name).write_text(r"\documentclass{article}\begin{document}Hi\end{document}")
    return d / name


def test_finds_single_main(tmp_path):
    main = _write_main(tmp_path)
    (tmp_path / "helper.tex").write_text(r"\section{X} text")  # no doc markers
    assert _find_main_tex(tmp_path) == main


def test_no_main_raises(tmp_path):
    (tmp_path / "frag.tex").write_text(r"\section{X} just a fragment")
    with pytest.raises(ValueError):
        _find_main_tex(tmp_path)


def test_multiple_mains_picks_first_sorted(tmp_path):
    a = tmp_path / "a.tex"
    b = tmp_path / "b.tex"
    body = r"\documentclass{article}\begin{document}Hi\end{document}"
    a.write_text(body)
    b.write_text(body)
    assert _find_main_tex(tmp_path) == a


def test_expands_nested_includes(tmp_path):
    (tmp_path / "main.tex").write_text(r"A \input{chap1} B")
    (tmp_path / "chap1.tex").write_text(r"C \include{chap2} D")
    (tmp_path / "chap2.tex").write_text(r"E")
    out = _expand_includes(tmp_path / "main.tex", tmp_path)
    assert "A" in out and "C" in out and "E" in out and "D" in out


def test_missing_include_is_skipped(tmp_path):
    (tmp_path / "main.tex").write_text(r"A \input{nope} B")
    out = _expand_includes(tmp_path / "main.tex", tmp_path)
    assert "A" in out and "B" in out  # no crash


def test_include_cycle_terminates(tmp_path):
    (tmp_path / "main.tex").write_text(r"A \input{loop}")
    (tmp_path / "loop.tex").write_text(r"B \input{main}")
    out = _expand_includes(tmp_path / "main.tex", tmp_path)
    assert "A" in out and "B" in out  # terminates, no infinite recursion


def test_include_traversal_blocked(tmp_path):
    (tmp_path / "proj").mkdir()
    (tmp_path / "secret.tex").write_text(r"SECRET")
    (tmp_path / "proj" / "main.tex").write_text(r"A \input{../secret} B")
    out = _expand_includes(tmp_path / "proj" / "main.tex", tmp_path / "proj")
    assert "SECRET" not in out


# ---------------------------------------------------------------------------
# parse_tex integration tests (Task 4)
# ---------------------------------------------------------------------------

from neurodb.chunking import Section  # noqa: E402
from neurodb.tex_parser import parse_tex  # noqa: E402


def _full_project(d):
    (d / "main.tex").write_text(
        r"""\documentclass{article}
\begin{document}
Intro prose about memory and plasticity in the hippocampus region of the brain.
\section{Methods}
We measured $x = \frac{a}{b}$ across many trials and recorded the outcomes carefully.
\input{results}
\end{document}
"""
    )
    (d / "results.tex").write_text(
        r"\section{Results} The results were significant and reproducible across all subjects."
    )
    (d / "refs.bbl").write_text(r"\begin{thebibliography}{1}\bibitem{a} Smith 2020.\end{thebibliography}")


def test_parse_tex_sections_and_anchors(tmp_path):
    _full_project(tmp_path)
    art = parse_tex(tmp_path)
    assert art.text_source == "tex_pylatexenc"
    labels = [s.label for s in art.sections]
    assert "Methods" in labels and "Results" in labels
    assert all(s.page is None for s in art.sections)
    assert art.parse_confidence >= 0.0


def test_parse_tex_preserves_math_verbatim(tmp_path):
    _full_project(tmp_path)
    art = parse_tex(tmp_path)
    joined = "\n".join(s.text for s in art.sections)
    assert "\\frac{a}{b}" in joined


def test_parse_tex_includes_references(tmp_path):
    _full_project(tmp_path)
    art = parse_tex(tmp_path)
    assert any(s.label == "References" and "Smith" in s.text for s in art.sections)


def test_parse_tex_empty_raises(tmp_path):
    (tmp_path / "main.tex").write_text(r"\documentclass{article}\begin{document}\end{document}")
    with pytest.raises(ValueError):
        parse_tex(tmp_path)


def test_parse_tex_seam_used_when_provided(tmp_path):
    _full_project(tmp_path)
    fake = lambda d: [Section(label="S", text="x" * 300, char_start=0, char_end=300)]
    art = parse_tex(tmp_path, latexml_convert=fake)
    assert art.text_source == "tex_latexml"
    assert art.sections[0].label == "S"


def test_parse_tex_seam_failure_falls_back(tmp_path):
    _full_project(tmp_path)
    def boom(d):
        raise RuntimeError("no latexml")
    art = parse_tex(tmp_path, latexml_convert=boom)
    assert art.text_source == "tex_pylatexenc"
