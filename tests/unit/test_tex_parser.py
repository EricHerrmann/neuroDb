import pytest

from neurodb.tex_parser import _find_main_tex


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
