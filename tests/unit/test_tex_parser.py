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
