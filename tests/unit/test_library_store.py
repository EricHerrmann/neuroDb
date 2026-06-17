import pytest
from neurodb import library_store


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    return tmp_path


def test_lists_only_supported_top_level_files(lib):
    (lib / "a.pdf").write_bytes(b"%PDF-1.4")
    (lib / "b.txt").write_text("hi")
    (lib / "c.exe").write_bytes(b"x")
    (lib / "sub").mkdir()
    (lib / "sub" / "d.pdf").write_bytes(b"x")
    names = {f["name"] for f in library_store.list_library_files()}
    assert names == {"a.pdf", "b.txt"}


def test_resolve_valid_file(lib):
    (lib / "paper.pdf").write_bytes(b"%PDF-1.4")
    p = library_store.resolve_library_path("paper.pdf")
    assert p is not None and p.name == "paper.pdf"


def test_resolve_rejects_traversal(lib, tmp_path):
    secret = tmp_path.parent / "secret.pdf"
    secret.write_bytes(b"%PDF")
    assert library_store.resolve_library_path("../secret.pdf") is None


def test_resolve_rejects_absolute(lib):
    assert library_store.resolve_library_path("/etc/passwd") is None


def test_resolve_missing_and_unsupported(lib):
    (lib / "x.exe").write_bytes(b"x")
    assert library_store.resolve_library_path("nope.pdf") is None
    assert library_store.resolve_library_path("x.exe") is None


def test_lists_skips_symlink_escaping_root(lib, tmp_path):
    outside = tmp_path.parent / "outside.pdf"
    outside.write_bytes(b"%PDF")
    try:
        (lib / "link.pdf").symlink_to(outside)
    except (OSError, NotImplementedError):
        import pytest; pytest.skip("symlinks not supported here")
    names = {f["name"] for f in library_store.list_library_files()}
    assert "link.pdf" not in names


def test_lists_tex_project_folders(lib):
    (lib / "proj").mkdir()
    (lib / "proj" / "main.tex").write_text(r"\documentclass{article}")
    (lib / "empty").mkdir()  # no .tex -> not a project
    (lib / "a.pdf").write_bytes(b"%PDF")  # a file, not a project
    names = {p["name"] for p in library_store.list_library_projects()}
    assert names == {"proj"}
    assert all(p["kind"] == "tex_project" for p in library_store.list_library_projects())


def test_resolve_tex_project(lib):
    (lib / "proj").mkdir()
    (lib / "proj" / "sub").mkdir()
    (lib / "proj" / "sub" / "paper.tex").write_text(r"\documentclass{article}")
    p = library_store.resolve_library_project("proj")
    assert p is not None and p.name == "proj"


def test_resolve_project_rejects_non_tex_dir(lib):
    (lib / "empty").mkdir()
    (lib / "empty" / "readme.txt").write_text("hi")
    assert library_store.resolve_library_project("empty") is None


def test_resolve_project_rejects_traversal(lib, tmp_path):
    (tmp_path.parent / "outside").mkdir(exist_ok=True)
    assert library_store.resolve_library_project("../outside") is None
