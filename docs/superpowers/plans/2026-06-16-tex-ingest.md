# TeX Ingest & Parsing Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ingest a user-extracted TeX project folder from the Knowledge Library into full-text chunks, mirroring the existing PDF/HTML Phase 2b path.

**Architecture:** A new pure module `tex_parser.py` turns a TeX project folder into a `ParsedArtifact` using `pylatexenc` (default) behind an injectable `latexml_convert` seam (deferred, like `docling_convert`). `library_store.py` gains folder-aware listing/resolution; the Knowledge Library route wires a folder → `SuppliedInput(path=<folder>)` → existing Phase 2b background job. Sections are anchored by section label (`page=None`); no schema migration.

**Tech Stack:** Python 3.12, `pylatexenc` (new dep), DuckDB + SQLAlchemy, ChromaDB, FastAPI, pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-06-16-tex-ingest-design.md`

---

## File Structure

- **Create** `src/neurodb/tex_parser.py` — TeX project folder → `ParsedArtifact`. Pure except filesystem reads. Mirrors `pdf_parser.py`.
- **Modify** `src/neurodb/library_store.py` — add `list_library_projects()` and `resolve_library_project()`; existing file functions untouched.
- **Modify** `src/neurodb/api/routes/knowledge_library.py` — `/library-files` includes projects; acquire routing resolves a project folder; `_phase2b_parse` routes a directory to `parse_tex`.
- **Modify** `pyproject.toml` — add `pylatexenc` dependency; update `uv.lock`.
- **Create** `tests/unit/test_tex_parser.py` — unit tests for the parser.
- **Modify** `tests/unit/test_library_store.py` — add project listing/resolution tests.
- **Create** `tests/integration/test_tex_ingest.py` — fixture project → chunks + idempotency.
- **Create** `docs/testsPlans/manualTestPlan_tex_ingest.md` — manual plan with pytest prerequisite.
- **Modify** `docs/projectStatus.md` — reference table + active focus sync.

**Reuse (do not reimplement):**
- `neurodb.full_text_client.sections_from_labeled_blocks(blocks) -> (sections, full_text)` — builds offset-correct `Section`s with `page=None` from `(label, text)` pairs.
- `neurodb.parse_quality.score(artifact) -> float` — parse-confidence scoring.
- `neurodb.chunking.Section`, `neurodb.fulltext_types.ParsedArtifact`.

---

## Task 1: Add the pylatexenc dependency

**Files:**
- Modify: `pyproject.toml` (the `[project] dependencies` list, around line 7–23)

- [ ] **Step 1: Add the dependency**

In `pyproject.toml`, inside the `dependencies = [ ... ]` array, add a line next to the existing `"pymupdf>=1.27.2.3",` entry:

```toml
    "pylatexenc>=2.10",
```

- [ ] **Step 2: Lock and install**

Run: `uv lock && uv sync`
Expected: `uv.lock` updates to include `pylatexenc`; install succeeds with no errors.

- [ ] **Step 3: Verify import**

Run: `uv run python -c "from pylatexenc.latex2text import LatexNodes2Text; print('ok')"`
Expected: prints `ok`

- [ ] **Step 4: Commit**

```bash
git add pyproject.toml uv.lock
git commit -m "build(lib): add pylatexenc dependency for TeX ingest"
```

---

## Task 2: Main-file detection

**Files:**
- Create: `src/neurodb/tex_parser.py`
- Test: `tests/unit/test_tex_parser.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_tex_parser.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_tex_parser.py -q`
Expected: FAIL — `ModuleNotFoundError` / `cannot import name '_find_main_tex'`

- [ ] **Step 3: Write minimal implementation**

Create `src/neurodb/tex_parser.py`:

```python
"""TeX project folder -> ParsedArtifact (Phase 2b TeX ingest).

Default path uses pylatexenc (pure-Python). A `latexml_convert` seam is accepted for a future
high-fidelity LaTeXML adapter (deferred); it defaults to None, so pylatexenc is used today.
Sections are anchored by section label (page=None); TeX has no pages.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def _has_doc_markers(p: Path) -> bool:
    try:
        t = p.read_text(errors="replace")
    except OSError:
        return False
    return "\\documentclass" in t and "\\begin{document}" in t


def _find_main_tex(project_dir: Path) -> Path:
    """Return the main .tex (contains \\documentclass and \\begin{document}).

    Multiple matches -> first by sorted path (logged). No match -> ValueError.
    """
    mains = [p for p in sorted(project_dir.rglob("*.tex")) if p.is_file() and _has_doc_markers(p)]
    if not mains:
        raise ValueError(f"No main .tex (\\documentclass + \\begin{{document}}) in {project_dir}")
    if len(mains) > 1:
        logger.warning("Multiple main .tex files in %s; using %s", project_dir, mains[0])
    return mains[0]
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_tex_parser.py -q`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/tex_parser.py tests/unit/test_tex_parser.py
git commit -m "feat(lib): TeX main-file detection"
```

---

## Task 3: Include expansion

**Files:**
- Modify: `src/neurodb/tex_parser.py`
- Test: `tests/unit/test_tex_parser.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_tex_parser.py`:

```python
from neurodb.tex_parser import _expand_includes


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_tex_parser.py -k include -q`
Expected: FAIL — `cannot import name '_expand_includes'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/neurodb/tex_parser.py` (add `import re` to the imports at top):

```python
import re

_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_MAX_INCLUDE_DEPTH = 20


def _expand_includes(path: Path, root: Path, _seen: set | None = None, _depth: int = 0) -> str:
    """Inline \\input/\\include relative to root. Skips missing/escaping files; guards cycles."""
    if _seen is None:
        _seen = set()
    rp = path.resolve()
    if rp in _seen or _depth > _MAX_INCLUDE_DEPTH:
        return ""
    _seen.add(rp)
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ""

    def _repl(m: re.Match) -> str:
        name = m.group(1).strip()
        if not name.endswith(".tex"):
            name += ".tex"
        child = (root / name)
        try:
            inside = child.resolve().is_relative_to(root.resolve())
        except OSError:
            inside = False
        if not inside or not child.exists():
            logger.warning("Skipping missing/escaping include: %s", name)
            return ""
        return _expand_includes(child, root, _seen, _depth + 1)

    return _INCLUDE_RE.sub(_repl, text)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_tex_parser.py -q`
Expected: PASS (7 passed)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/tex_parser.py tests/unit/test_tex_parser.py
git commit -m "feat(lib): TeX include expansion with cycle and traversal guards"
```

---

## Task 4: Sectionize, math, references, and `parse_tex` assembly

**Files:**
- Modify: `src/neurodb/tex_parser.py`
- Test: `tests/unit/test_tex_parser.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_tex_parser.py`:

```python
from neurodb.chunking import Section
from neurodb.tex_parser import parse_tex


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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_tex_parser.py -k parse_tex -q`
Expected: FAIL — `cannot import name 'parse_tex'`

- [ ] **Step 3: Write minimal implementation**

Add to `src/neurodb/tex_parser.py`. Add these imports at the top:

```python
from collections.abc import Callable

from neurodb.chunking import Section
from neurodb.full_text_client import sections_from_labeled_blocks
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score
```

Then add the body:

```python
_SECTION_RE = re.compile(r"\\(?:sub)*section\*?\s*\{([^}]*)\}")
_DOC_RE = re.compile(r"\\begin\{document\}(.*)\\end\{document\}", re.DOTALL)


def _document_body(src: str) -> str:
    """Return the text between \\begin{document} and \\end{document}, else the whole source."""
    m = _DOC_RE.search(src)
    return m.group(1) if m else src


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split body into (heading-title, raw-latex) blocks on section macros.

    Text before the first heading gets label None. Nested-brace titles are not supported
    (a known limitation; such titles are truncated at the first closing brace).
    """
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return [(None, body)]
    blocks: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        blocks.append((None, body[: matches[0].start()]))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        blocks.append((title, body[start:end]))
    return blocks


def _references_block(project_dir: Path, l2t) -> tuple[str, str] | None:
    bbls = sorted(p for p in project_dir.rglob("*.bbl") if p.is_file())
    if not bbls:
        return None
    text = l2t.latex_to_text(bbls[0].read_text(errors="replace")).strip()
    return ("References", text) if text else None


def parse_tex(
    project_dir: Path,
    *,
    latexml_convert: Callable[[Path], list[Section]] | None = None,
    text_source: str = "tex_latexml",
) -> ParsedArtifact:
    """Parse a TeX project folder into a ParsedArtifact.

    Uses latexml_convert if provided and it yields sections; otherwise (default today) uses
    pylatexenc. Raises ValueError if no text is extractable.
    """
    from pylatexenc.latex2text import LatexNodes2Text

    if latexml_convert is not None:
        try:
            sections = latexml_convert(project_dir)
            if sections:
                art = ParsedArtifact(sections, 0.0, text_source)
                art.parse_confidence = score(art)
                return art
        except Exception:
            logger.exception("latexml_convert failed; falling back to pylatexenc")

    main = _find_main_tex(project_dir)
    src = _expand_includes(main, project_dir)
    body = _document_body(src)
    l2t = LatexNodes2Text(math_mode="verbatim")

    blocks: list[tuple[str | None, str]] = []
    for label, raw in _split_sections(body):
        clean_label = l2t.latex_to_text(label).strip() if label else None
        blocks.append((clean_label or None, l2t.latex_to_text(raw)))
    refs = _references_block(project_dir, l2t)
    if refs:
        blocks.append(refs)

    sections, _full = sections_from_labeled_blocks(blocks)
    if not sections:
        raise ValueError("TeX project produced no extractable text")
    art = ParsedArtifact(sections, 0.0, "tex_pylatexenc")
    art.parse_confidence = score(art)
    return art
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_tex_parser.py -q`
Expected: PASS (13 passed)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/tex_parser.py tests/unit/test_tex_parser.py
git commit -m "feat(lib): TeX sectionize/math/references + parse_tex with LaTeXML seam"
```

---

## Task 5: Library store folder listing and resolution

**Files:**
- Modify: `src/neurodb/library_store.py`
- Test: `tests/unit/test_library_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_library_store.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_library_store.py -k project -q`
Expected: FAIL — `module 'neurodb.library_store' has no attribute 'list_library_projects'`

- [ ] **Step 3: Write minimal implementation**

Append to `src/neurodb/library_store.py`:

```python
def _has_tex(folder: Path) -> bool:
    return any(c.is_file() and c.suffix.lower() == ".tex" for c in folder.rglob("*.tex"))


def list_library_projects() -> list[dict]:
    """Surface top-level subdirectories containing at least one .tex as selectable projects."""
    root = library_root()
    projects: list[dict] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if not p.resolve().is_relative_to(root):
            continue
        if not _has_tex(p):
            continue
        projects.append({"name": p.name, "kind": "tex_project", "modified": p.stat().st_mtime})
    return projects


def resolve_library_project(name: str) -> Path | None:
    """Return the resolved folder iff `name` is a directory inside the root containing a .tex."""
    if not name:
        return None
    root = library_root()
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_dir():
        return None
    if not _has_tex(candidate):
        return None
    return candidate
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_library_store.py -q`
Expected: PASS (all existing + 4 new)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/library_store.py tests/unit/test_library_store.py
git commit -m "feat(lib): list and resolve TeX project folders in library store"
```

---

## Task 6: Route wiring — listing, acquire routing, parse dispatch

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py` (`/library-files` ~L99; acquire ~L252; `_phase2b_parse` ~L382)
- Test: `tests/unit/test_api_knowledge_library_local_file.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_api_knowledge_library_local_file.py`:

```python
def test_library_files_lists_tex_project(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    (tmp_path / "proj").mkdir()
    (tmp_path / "proj" / "main.tex").write_text(r"\documentclass{article}")
    client, _ = _make_duckdb_client()
    resp = client.get("/api/knowledge-library/library-files")
    assert resp.status_code == 200
    assert any(f["name"] == "proj" and f.get("kind") == "tex_project" for f in resp.json())


def test_phase2b_parse_reads_tex_project(tmp_path):
    (tmp_path / "main.tex").write_text(
        r"""\documentclass{article}\begin{document}
\section{Methods} We measured plasticity across hippocampal neurons in many trials.
\end{document}"""
    )
    art = _phase2b_parse(_paper(), SuppliedInput(path=str(tmp_path)))
    assert art is not None
    assert art.text_source == "tex_pylatexenc"
    assert art.fetched_url == tmp_path.name
    assert any(s.label == "Methods" for s in art.sections)
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py -k "tex" -q`
Expected: FAIL — listing lacks the project; `_phase2b_parse` treats the dir as HTML and returns None.

- [ ] **Step 3a: Update the `/library-files` endpoint**

In `src/neurodb/api/routes/knowledge_library.py`, replace the `library_files` function (~L98-101):

```python
@router.get("/library-files")
def library_files() -> list[dict]:
    from neurodb.library_store import list_library_files, list_library_projects
    return list_library_files() + list_library_projects()
```

- [ ] **Step 3b: Add the project branch to acquire routing**

Replace the `if body.source_path:` block (~L252-270) with:

```python
    if body.source_path:
        from neurodb.library_store import (
            library_root, resolve_library_path, resolve_library_project,
        )
        project = resolve_library_project(body.source_path)
        if project is not None:
            supplied = SuppliedInput(path=str(project))
        else:
            resolved = resolve_library_path(body.source_path)
            if resolved is None:
                root = library_root()
                try:
                    inside = (root / body.source_path).resolve().is_relative_to(root)
                except Exception:
                    inside = False
                if not inside:
                    raise HTTPException(status_code=400, detail="Invalid file path")
                raise HTTPException(status_code=404,
                                    detail="File not found in library or unsupported type")
            ext = resolved.suffix.lower()
            if ext in (".txt", ".md"):
                supplied = SuppliedInput(text=resolved.read_text(errors="replace"),
                                         format="md" if ext == ".md" else "txt")
            else:  # .pdf/.html/.htm
                supplied = SuppliedInput(path=str(resolved))
```

- [ ] **Step 3c: Add the directory branch to `_phase2b_parse`**

In `_phase2b_parse` (~L382), replace the `if supplied and supplied.path:` block body with:

```python
    if supplied and supplied.path:
        from pathlib import Path
        p = Path(supplied.path)
        try:
            if p.is_dir():
                from neurodb.tex_parser import parse_tex
                artifact = parse_tex(p)
            elif p.suffix.lower() == ".pdf":
                artifact = parse_pdf(p.read_bytes())
            else:  # .html/.htm
                artifact = extract_html(p.read_text(errors="replace"))
            artifact.fetched_url = p.name
            return artifact
        except Exception:
            logger.exception("Phase 2b local-file parse failed for %s", supplied.path)
            return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py -q`
Expected: PASS (existing + 2 new)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library_local_file.py
git commit -m "feat(lib): route TeX project folders through Phase 2b acquire"
```

---

## Task 7: Integration test — end-to-end and idempotency

**Files:**
- Create: `tests/integration/test_tex_ingest.py`

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_tex_ingest.py`:

```python
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
```

- [ ] **Step 2: Run to verify it fails, then passes**

Run: `uv run pytest tests/integration/test_tex_ingest.py -q`
Expected: PASS (3 passed) — all dependencies exist by now; this test locks the end-to-end contract and idempotency. If it fails, fix the parser, not the test.

- [ ] **Step 3: Commit**

```bash
git add tests/integration/test_tex_ingest.py
git commit -m "test(lib): TeX ingest end-to-end + idempotency integration test"
```

---

## Task 8: Manual test plan and project-state sync

**Files:**
- Create: `docs/testsPlans/manualTestPlan_tex_ingest.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_tex_ingest.md`:

```markdown
# Manual Test Plan — TeX Ingest (Knowledge Library)

## Purpose
Verify that an operator can extract an arXiv TeX tarball into the Knowledge Library,
select the resulting project folder, acquire it, and get section-anchored searchable full
text — covering the real server/DB wiring and browser workflow that automated tests do not.

## Prerequisites
1. **Automated tests pass.** Run `uv run pytest tests/ -q`.
   Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Streamlit/API server running against the local DuckDB.
3. A real arXiv source tarball downloaded (e.g., from an `e-print` link).

## Steps
1. Extract the tarball into `knowledge_library_files/<paper_name>/` (so the folder holds
   `main.tex`, any `\input` children, and a `.bbl`).
2. In the Knowledge Library picker, confirm `<paper_name>` appears as a TeX project
   (kind = `tex_project`), distinct from loose PDF/HTML files.
3. Approve a target paper, then acquire it using the project folder as the source.
4. Wait for the background job to complete (status leaves `pending`).

## Expected Results
- The paper's full-text status becomes populated; `text_source` is `tex_pylatexenc`.
- Semantic search over the paper returns chunks anchored by section label (e.g., `Methods`,
  `Results`, `References`), not page numbers.
- Inline math appears as raw LaTeX in retrieved chunk text.
- Re-acquiring the same project does not duplicate chunks (chunk count stable).

## Pass/Fail
PASS when all Expected Results hold and no new automated-test failures were introduced.
```

- [ ] **Step 2: Sync `docs/projectStatus.md`**

In `docs/projectStatus.md`: update the active-focus line to reference TeX ingest, bump the
Phase 2b test count by the number of tests added in this plan, and add two reference-table
rows:
- `docs/superpowers/specs/2026-06-16-tex-ingest-design.md` — TeX ingest design spec
- `docs/testsPlans/manualTestPlan_tex_ingest.md` — TeX ingest manual test plan

(Match the existing table format exactly; do not restructure the doc.)

- [ ] **Step 3: Full test run**

Run: `uv run pytest tests/ -q`
Expected: green except for any failures already tracked in `docs/testLog.md`.

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_tex_ingest.md docs/projectStatus.md
git commit -m "docs(lib): TeX ingest manual test plan + projectStatus sync"
```

---

## Self-Review Notes

- **Spec coverage:** §2 scope → Tasks 5/6 (folder unit, no extraction). §3 hybrid engine → Task 4 (pylatexenc default + seam). §4.1 parser internals → Tasks 2-4. §4.2 store → Task 5. §4.3 route → Task 6. §6 anchor model (`page=None`) → asserted in Tasks 4/7. §7 error handling → Tasks 4/6 (`ValueError` → `None`). §8 testing → Tasks 2-7. §9 state sync → Task 8.
- **No migration:** `page=None` + nullable `PaperChunk.page` confirmed; no Task touches schema.
- **Type consistency:** `parse_tex(project_dir, *, latexml_convert=None, text_source="tex_latexml")` and helper names (`_find_main_tex`, `_expand_includes`, `_split_sections`, `_document_body`, `_references_block`) are identical across Tasks 2-7. `list_library_projects`/`resolve_library_project` consistent across Tasks 5-6.
- **Reuse:** `sections_from_labeled_blocks` and `score` reused, not reimplemented.
```
