# Knowledge Library Local-File Source — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the user ingest a manually-downloaded file (e.g. a paywalled PDF) by dropping it into
a project library directory and picking it in the acquire UI, feeding the existing parse →
quality-gate → chunk pipeline.

**Architecture:** A new `library_store` module manages a gitignored drop-folder and a
path-traversal-safe resolver. The acquire request gains a `source_path`; the route resolves it
within the library dir and routes by extension into pipelines that already exist (`.txt/.md` →
synchronous user-supplied-text; `.pdf/.html` → the 2b async parser+gate). A list endpoint + a UI
picker complete it. No DB migration.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy/DuckDB, httpx, PyMuPDF, trafilatura; React/TS + Vitest.

**Spec:** `docs/superpowers/specs/2026-06-13-knowledge-library-local-file-source-design.md`

---

## File structure
- **New** `src/neurodb/library_store.py` — `library_root`, `list_library_files`, `resolve_library_path`.
- **Modify** `src/neurodb/full_text_client.py` — `SuppliedInput.path`; `classify_for_phase2b` path→phase2b.
- **Modify** `src/neurodb/api/routes/knowledge_library.py` — `AcquireFullTextRequest.source_path`;
  `GET /library-files`; `source_path` routing in `acquire_full_text`; `_phase2b_parse` local-file branch.
- **Modify** `.gitignore` — add `knowledge_library_files/`.
- **Modify** `frontend/src/api/client.ts` (+ types) and `frontend/src/pages/KnowledgeLibraryPanel.tsx`.
- **Docs** — manual plan addendum + `docs/projectStatus.md`.

---

### Task 1: library_store module + gitignore

**Files:**
- Create: `src/neurodb/library_store.py`
- Test: `tests/unit/test_library_store.py`
- Modify: `.gitignore`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_library_store.py
import os
from pathlib import Path
import pytest
from neurodb import library_store


@pytest.fixture
def lib(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    return tmp_path


def test_lists_only_supported_top_level_files(lib):
    (lib / "a.pdf").write_bytes(b"%PDF-1.4")
    (lib / "b.txt").write_text("hi")
    (lib / "c.exe").write_bytes(b"x")          # unsupported
    (lib / "sub").mkdir()
    (lib / "sub" / "d.pdf").write_bytes(b"x")  # subdir ignored
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_library_store.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/library_store.py
"""Local document library (a drop folder) for user-supplied files such as paywalled PDFs.

The user downloads files into the library dir; the Knowledge Library reads them in place. All
reads are constrained to the library root (path-traversal guard).
"""
from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_EXTS = {".pdf", ".txt", ".md", ".html", ".htm"}


def library_root() -> Path:
    root = Path(os.environ.get("NEURODB_LIBRARY_DIR", "knowledge_library_files"))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def list_library_files() -> list[dict]:
    root = library_root()
    files: list[dict] = []
    for p in sorted(root.iterdir()):
        if p.is_file() and p.suffix.lower() in SUPPORTED_EXTS:
            st = p.stat()
            files.append({"name": p.name, "size": st.st_size, "modified": st.st_mtime})
    return files


def resolve_library_path(name: str) -> Path | None:
    """Return the resolved path iff `name` is a supported regular file inside the library root."""
    if not name:
        return None
    root = library_root()
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_file():
        return None
    if candidate.suffix.lower() not in SUPPORTED_EXTS:
        return None
    return candidate
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_library_store.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Add gitignore entry + commit**

Add `knowledge_library_files/` to `.gitignore` (near the other data dirs, e.g. after `*_chroma/`).

```bash
git add src/neurodb/library_store.py tests/unit/test_library_store.py .gitignore
git commit -m "feat(lib): library_store drop-folder + path-traversal guard"
```

---

### Task 2: SuppliedInput.path + classify routing

**Files:**
- Modify: `src/neurodb/full_text_client.py`
- Test: `tests/unit/test_full_text_client_2b.py` (extend)

- [ ] **Step 1: Write the failing test** (append)

```python
# tests/unit/test_full_text_client_2b.py  (add)
def test_supplied_path_routes_to_phase2b():
    from neurodb.full_text_client import classify_for_phase2b, SuppliedInput
    paper = type("P", (), {"url": None, "doi": None, "id": 1})()
    assert classify_for_phase2b(paper, SuppliedInput(path="/lib/x.pdf")) == "phase2b"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_client_2b.py::test_supplied_path_routes_to_phase2b -v`
Expected: FAIL — `SuppliedInput` has no `path` (TypeError) / classify returns "phase2b" only via url.

- [ ] **Step 3: Implement**

In `SuppliedInput` (the dataclass) add a field:
```python
    path: str | None = None  # local library file path (Phase 2b local-file source)
```
In `classify_for_phase2b`, add the path check right after the user-text check and before/with the
url check:
```python
    if supplied and supplied.text and supplied.text.strip():
        return "structured"
    if supplied and (supplied.url or supplied.path):
        return "phase2b"
```

- [ ] **Step 4: Run to verify it passes** (plus the existing routing tests)

Run: `uv run pytest tests/unit/test_full_text_client_2b.py -v`
Expected: PASS (all, incl. the new one).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_client_2b.py
git commit -m "feat(lib): SuppliedInput.path + classify local file as phase2b"
```

---

### Task 3: `_phase2b_parse` local-file branch

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py`
- Test: `tests/unit/test_api_knowledge_library_local_file.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_api_knowledge_library_local_file.py
from neurodb.api.routes.knowledge_library import _phase2b_parse
from neurodb.full_text_client import SuppliedInput


def _paper():
    return type("P", (), {"url": None, "doi": None, "id": 1, "open_access_pdf": None})()


def test_phase2b_parse_reads_local_pdf():
    art = _phase2b_parse(_paper(), SuppliedInput(path="tests/fixtures/sample.pdf"))
    assert art is not None
    assert art.text_source == "pdf_pymupdf"
    assert art.fetched_url == "sample.pdf"
    assert art.sections[0].page == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py::test_phase2b_parse_reads_local_pdf -v`
Expected: FAIL — `_phase2b_parse` tries OA discovery / httpx and returns None (no url).

- [ ] **Step 3: Implement**

At the TOP of `_phase2b_parse` (before the `unpaywall_email`/url logic), add the local-file branch:
```python
    if supplied and supplied.path:
        from pathlib import Path
        from neurodb.html_extractor import extract_html
        from neurodb.pdf_parser import parse_pdf
        p = Path(supplied.path)
        try:
            if p.suffix.lower() == ".pdf":
                artifact = parse_pdf(p.read_bytes())
            else:  # .html/.htm
                artifact = extract_html(p.read_text(errors="replace"))
            artifact.fetched_url = p.name
            return artifact
        except Exception:
            logger.exception("Phase 2b local-file parse failed for %s", supplied.path)
            return None
```
(The existing URL/OA-discovery flow stays below, unchanged.)

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library_local_file.py
git commit -m "feat(lib): _phase2b_parse reads a local library file"
```

---

### Task 4: list endpoint + source_path acquire routing

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py`
- Test: `tests/unit/test_api_knowledge_library_local_file.py` (extend)

- [ ] **Step 1: Write the failing tests** (append; reuse the duckdb TestClient helper from
  `tests/unit/test_api_knowledge_library.py` — import or copy `_make_duckdb_client`)

```python
# tests/unit/test_api_knowledge_library_local_file.py  (add)
import shutil
from unittest.mock import MagicMock
from sqlalchemy.orm import Session
from neurodb.db import get_session
from neurodb.schema import Paper
from tests.unit.test_api_knowledge_library import _make_duckdb_client  # reuse helper


def _approved_paper(engine, **kw):
    with get_session(engine) as s:
        p = Paper(title="P", normalized_title="p", source_type="paper", topic_context="x",
                  status="approved", queued_at="t", data_tier="abstract",
                  currency_status="current", **kw)
        s.add(p); s.flush(); return p.id


def test_library_files_lists_dropped_files(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    (tmp_path / "paper.pdf").write_bytes(b"%PDF-1.4")
    client, _ = _make_duckdb_client()
    resp = client.get("/api/knowledge-library/library-files")
    assert resp.status_code == 200
    assert any(f["name"] == "paper.pdf" for f in resp.json())


def test_acquire_txt_source_path_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    (tmp_path / "note.md").write_text("# Title\n\nSome real body text about memory.\n")
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "note.md"})
    assert resp.status_code == 200
    with Session(engine) as s:
        assert s.get(Paper, pid).full_text_status == "verified"


def test_acquire_pdf_source_path_verifies(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    shutil.copy("tests/fixtures/sample.pdf", tmp_path / "sample.pdf")
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    # Starlette TestClient runs the background task synchronously
    client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                json={"source_path": "sample.pdf"})
    with Session(engine) as s:
        assert s.get(Paper, pid).full_text_status == "verified"


def test_acquire_traversal_path_rejected(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "../../etc/passwd"})
    assert resp.status_code == 400


def test_acquire_missing_file_404(tmp_path, monkeypatch):
    monkeypatch.setenv("NEURODB_LIBRARY_DIR", str(tmp_path))
    client, engine = _make_duckdb_client(MagicMock())
    pid = _approved_paper(engine)
    resp = client.post(f"/api/knowledge-library/{pid}/acquire-full-text",
                       json={"source_path": "ghost.pdf"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py -v`
Expected: FAIL — `/library-files` 404; `source_path` ignored.

- [ ] **Step 3: Implement**

Add the field to `AcquireFullTextRequest`:
```python
    source_path: str | None = None  # a filename in the library dir (local-file source)
```
Add the list endpoint (place it ABOVE the `/{source_id}/...` routes to avoid any dynamic-segment
ambiguity):
```python
@router.get("/library-files")
def library_files() -> list[dict]:
    from neurodb.library_store import list_library_files
    return list_library_files()
```
In `acquire_full_text`, replace the `supplied = ...` construction (currently lines ~245-247) with:
```python
    body = body or AcquireFullTextRequest()
    if body.source_path:
        from neurodb.library_store import library_root, resolve_library_path
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
        else:  # .pdf/.html/.htm -> 2b parser reads the file
            supplied = SuppliedInput(path=str(resolved))
    else:
        effective_url = body.url or body.source_url
        supplied = SuppliedInput(url=effective_url, text=body.text, format=body.format)
```
The rest of the route (the `classify_for_phase2b` branch and the 2a synchronous path) is unchanged:
a `.txt/.md` supplies `text` → classify returns `"structured"` → synchronous verified; a
`.pdf/.html` supplies `path` → classify returns `"phase2b"` → background job → `_phase2b_parse`
local-file branch.

- [ ] **Step 4: Run to verify they pass** (plus the existing knowledge-library suite)

Run: `uv run pytest tests/unit/test_api_knowledge_library_local_file.py tests/unit/test_api_knowledge_library.py -v`
Expected: PASS (new + existing 2a/2b).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library_local_file.py
git commit -m "feat(lib): GET /library-files + source_path acquire routing"
```

---

### Task 5: Frontend — library-file picker

**Files:**
- Modify: `frontend/src/api/client.ts` (+ `frontend/src/api/types.ts` if types live there)
- Modify: `frontend/src/pages/KnowledgeLibraryPanel.tsx`
- Test: `frontend/src/pages/KnowledgeLibraryPanel.test.tsx`

- [ ] **Step 1: Write the failing tests** (adapt to the real test/render conventions — read the file first)

```tsx
it("lists library files in the supply control and acquires by source_path", async () => {
  // mock api.listLibraryFiles -> [{name:"smith2020.pdf", size:123, modified:0}]
  // render an item in an acquirable state (e.g. abstract tier)
  // open the supply control, select "smith2020.pdf", click acquire
  // expect the acquire api to be called with { source_path: "smith2020.pdf" }
});

it("shows an empty-library hint when there are no files", async () => {
  // mock api.listLibraryFiles -> []
  // expect text matching /no files in library/i
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd frontend && npm test -- --run`
Expected: FAIL — no picker / method.

- [ ] **Step 3: Implement**

- In the api client, add `listLibraryFiles(): Promise<{name:string;size:number;modified:number}[]>`
  (GET `/api/knowledge-library/library-files`) and a way to acquire with a path (extend the existing
  acquire-with-url call to accept `{ source_path }`, or add `acquireFullTextWithPath(id, path)` that
  POSTs `{ source_path }`).
- In `SupplyLinkInput`, add a `<select>` populated via a `useQuery(['library-files'], listLibraryFiles)`
  with a refresh button (refetch). When a file is selected and the user clicks acquire, call the
  path acquire; otherwise fall back to the URL path (existing). Render an empty-library hint
  ("No files in library — drop a file in knowledge_library_files/") when the list is empty.
- Keep the control rendered in the same status states as today (acquire / recovery / re-acquire).

- [ ] **Step 4: Run to verify they pass + build**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS; `tsc -b && vite build` clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(lib): Knowledge Library file picker (acquire by source_path)"
```

---

### Task 6: Manual plan addendum + projectStatus + full gate

**Files:**
- Modify: `docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md` (add a Local-File section)
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Add manual cases** — a "Local-file source (LF1–LF3)" section: (LF1) drop a real
  paywalled PDF into `knowledge_library_files/`, pick it in the UI, confirm `pending → verified` and
  a grounded quote with a page anchor; (LF2) drop a `.md` file, pick it → `verified` synchronously;
  (LF3) attempt a traversal filename via the API → refused (400). Reuse the existing Prerequisites
  (which already run `uv run pytest tests/ -q` first).

- [ ] **Step 2: projectStatus sync** — update the active-focus line to note the Knowledge Library
  local-file source is implemented (with new backend/frontend counts from Step 3); the spec is
  already in the reference table — add the plan and confirm the manual-plan row mentions LF1–LF3.

- [ ] **Step 3: Full gate** — run and record:
  - `uv run pytest tests/ -q` (only the pre-existing tracked failures, if any, may remain)
  - `cd frontend && npm test -- --run && npm run build`
  If any NEW backend failure appears, STOP and report it.

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md docs/projectStatus.md
git commit -m "docs(lib): manual cases + projectStatus for local-file source"
```

---

## Self-review (author)
- **Spec coverage:** library dir + path-safety (T1), `SuppliedInput.path`/classify (T2), local-file
  parse (T3), list endpoint + `source_path` routing incl. extension split + 400/404 (T4), UI picker
  + empty hint (T5), manual + status (T6). `.gitignore` in T1.
- **Reuse:** `.txt/.md` → existing user-supplied-text synchronous path; `.pdf/.html` → existing 2b
  parser+gate+orchestrator. No new parser, no migration.
- **Type consistency:** `SuppliedInput.path` introduced in T2 and consumed in T3/T4;
  `resolve_library_path` defined in T1 and used in T4; `_phase2b_parse` local branch (T3) reached via
  classify→`phase2b` (T2) from the path supplied in T4.
- **Security:** every local read goes through `resolve_library_path` / the route's
  `is_relative_to(root)` check; adversarial tests in T1 + an API traversal test in T4.
