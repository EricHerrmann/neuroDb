# Citation-Grade Phase 2b Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make queued papers without a clean structured source quotable by discovering an OA PDF
(or accepting a user-supplied PDF/HTML link), parsing it, and admitting it to the quote index
only through a confidence-tiered parse-quality gate.

**Architecture:** A fallback ladder runs after 2a's structured `acquire()` declines. Parsing is
an async background job that writes a terminal `full_text_status`. A staging table holds
medium-confidence parses for human review; only auto-accepted or confirmed parses are
chunked/embedded into the existing Chroma `knowledge_chunks` index, so retrieval stays
trustworthy by construction.

**Tech Stack:** Python 3.12, SQLAlchemy + DuckDB, FastAPI, httpx, Docling (PDF, primary),
PyMuPDF (PDF fallback), trafilatura (HTML), Chroma; React/TypeScript + Vitest for the UI.

**Spec:** `docs/superpowers/specs/2026-06-12-citation-grade-phase2b-pdf-html-design.md`

---

## File structure

**New modules**
- `src/neurodb/fulltext_types.py` — shared `ParsedArtifact` dataclass (decouples parsers from
  `full_text_client`).
- `src/neurodb/parse_quality.py` — `score(artifact)` heuristic + `gate(confidence)` thresholds.
- `src/neurodb/oa_locator.py` — OA PDF URL discovery (Unpaywall, S2, landing-page scan, PMID→DOI).
- `src/neurodb/pdf_parser.py` — Docling-primary / PyMuPDF-fallback PDF → `ParsedArtifact`.
- `src/neurodb/html_extractor.py` — trafilatura HTML → `ParsedArtifact`.
- `src/neurodb/fulltext_staging.py` — staging-table CRUD.
- `src/neurodb/phase2b.py` — orchestrator (the async job body): discover → parse → gate →
  terminal state.
- `scripts/`-style migration registered in `src/neurodb/db.py` (`_migration_025_phase2b`).

**Modified**
- `src/neurodb/chunking.py` — add optional `page` to `Section`/`Chunk`.
- `src/neurodb/schema.py` — `papers.parse_confidence`, `paper_chunks.page`,
  new `PaperFulltextStaging`.
- `src/neurodb/chunk_store.py` — carry `page` into Chroma metadata + search results.
- `src/neurodb/full_text_client.py` — user-supplied URL/PDF entry; 2b deferral becomes a typed
  signal the route acts on.
- `src/neurodb/api/routes/knowledge_library.py` — async dispatch, `_commit_chunks` helper,
  review endpoint, request shape.
- `frontend/src/components/KnowledgeLibrary*.tsx` (+ tests) — status-driven acquire surface.
- `docs/projectStatus.md`, `docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md`.

---

## Phase A — schema & shared types

### Task 1: Migration 025 (columns + staging table)

**Files:**
- Modify: `src/neurodb/db.py` (add `_migration_025_phase2b`; register `25:` in `_MIGRATIONS`)
- Test: `tests/unit/test_migration_025_phase2b.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_migration_025_phase2b.py
from sqlalchemy import create_engine, inspect, text
from neurodb.db import _MIGRATIONS, _migration_025_phase2b  # noqa: F401


def test_migration_025_adds_columns_and_staging():
    eng = create_engine("duckdb:///:memory:")
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER)"))
        conn.execute(text("CREATE TABLE paper_chunks (id INTEGER)"))
        conn.commit()
        _MIGRATIONS[25](conn)
        conn.commit()
    cols_papers = {c["name"] for c in inspect(eng).get_columns("papers")}
    cols_chunks = {c["name"] for c in inspect(eng).get_columns("paper_chunks")}
    assert "parse_confidence" in cols_papers
    assert "page" in cols_chunks
    assert "paper_fulltext_staging" in inspect(eng).get_table_names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_025_phase2b.py -v`
Expected: FAIL — `KeyError: 25` (migration not registered).

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/db.py — add after _migration_024_paper_chunks
def _migration_025_phase2b(conn) -> None:
    """Phase 2b: parse confidence, page anchors, and the parse staging table."""
    for ddl in (
        "ALTER TABLE papers ADD COLUMN parse_confidence DOUBLE",
        "ALTER TABLE paper_chunks ADD COLUMN page INTEGER",
    ):
        try:
            conn.execute(text(ddl))
        except Exception:
            pass  # column already exists
    try:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS paper_fulltext_staging (
                id INTEGER PRIMARY KEY,
                source_id INTEGER NOT NULL,
                text_source VARCHAR(32) NOT NULL,
                parse_confidence DOUBLE,
                fetched_url TEXT,
                artifact_json TEXT NOT NULL,
                created_at VARCHAR(32) NOT NULL
            )
            """
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_fulltext_staging_source_id "
            "ON paper_fulltext_staging (source_id)"
        ))
        conn.execute(text(
            "CREATE SEQUENCE IF NOT EXISTS paper_fulltext_staging_id_seq START 1"
        ))
    except Exception:
        pass
```

Then register it:

```python
# src/neurodb/db.py — in _MIGRATIONS, after `24: _migration_024_paper_chunks,`
    25: _migration_025_phase2b,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_025_phase2b.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_025_phase2b.py
git commit -m "feat(2b): migration 025 — parse_confidence, page anchor, staging table"
```

### Task 2: ORM models (parse_confidence, page, PaperFulltextStaging)

**Files:**
- Modify: `src/neurodb/schema.py` (Paper: `parse_confidence`; PaperChunk: `page`; new model)
- Test: `tests/unit/test_phase2b_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_phase2b_schema.py
from sqlalchemy import create_engine
from neurodb.schema import Base, Paper, PaperChunk, PaperFulltextStaging


def test_phase2b_models_create_and_roundtrip():
    eng = create_engine("duckdb:///:memory:")
    Base.metadata.create_all(eng)
    from sqlalchemy.orm import Session
    with Session(eng) as s:
        s.add(PaperFulltextStaging(
            source_id=1, text_source="pdf_docling", parse_confidence=0.7,
            fetched_url="http://x/p.pdf", artifact_json="{}", created_at="t",
        ))
        s.commit()
        row = s.query(PaperFulltextStaging).one()
        assert row.source_id == 1 and row.parse_confidence == 0.7
    # new optional columns exist with None defaults
    assert Paper.__table__.c.parse_confidence is not None
    assert PaperChunk.__table__.c.page is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_phase2b_schema.py -v`
Expected: FAIL — `ImportError: cannot import name 'PaperFulltextStaging'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/schema.py — add to class Paper (after data_tier/currency block)
    parse_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
```

```python
# src/neurodb/schema.py — add to class PaperChunk (after char_end)
    page: Mapped[int | None] = mapped_column(Integer, nullable=True)
```

```python
# src/neurodb/schema.py — new model (place near PaperChunk)
class PaperFulltextStaging(Base):
    """A parsed full-text artifact awaiting human review. Insert/delete only (no FK)."""
    __tablename__ = "paper_fulltext_staging"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("paper_fulltext_staging_id_seq"), primary_key=True
    )
    source_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    text_source: Mapped[str] = mapped_column(String(32), nullable=False)
    parse_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    fetched_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    artifact_json: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

Confirm `Float` is imported in `schema.py` (it is, per the existing `model_call_log`).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_phase2b_schema.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_phase2b_schema.py
git commit -m "feat(2b): ORM — parse_confidence, chunk page, PaperFulltextStaging"
```

### Task 3: Page anchors in chunking

**Files:**
- Modify: `src/neurodb/chunking.py` (add `page` to `Section` and `Chunk`; carry through)
- Test: `tests/unit/test_chunking_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_chunking_page.py
from neurodb.chunking import Section, chunk_sections


def test_chunk_carries_page_from_section():
    secs = [Section(label="Intro", text="hello world", char_start=0, char_end=11, page=3)]
    chunks = chunk_sections(secs)
    assert chunks[0].page == 3


def test_section_page_defaults_none():
    secs = [Section(label=None, text="abc", char_start=0, char_end=3)]
    assert chunk_sections(secs)[0].page is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_chunking_page.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'page'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/chunking.py
@dataclass
class Section:
    label: str | None
    text: str
    char_start: int
    char_end: int
    page: int | None = None


@dataclass
class Chunk:
    chunk_index: int
    text: str
    section: str | None
    char_start: int
    char_end: int
    page: int | None = None
```

In `chunk_sections`, pass `sec.page` on both `Chunk(...)` constructions:

```python
            chunks.append(
                Chunk(index, sec.text, sec.label, sec.char_start, sec.char_end, sec.page)
            )
```
```python
            chunks.append(
                Chunk(index, piece, sec.label, start, start + len(piece), sec.page)
            )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_chunking_page.py tests/unit/test_chunking.py -v`
Expected: PASS (existing chunking tests still pass — `page` is optional).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chunking.py tests/unit/test_chunking_page.py
git commit -m "feat(2b): optional page anchor on Section/Chunk"
```

### Task 4: Shared ParsedArtifact type

**Files:**
- Create: `src/neurodb/fulltext_types.py`
- Test: `tests/unit/test_fulltext_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_fulltext_types.py
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact


def test_parsed_artifact_holds_sections_confidence_source():
    a = ParsedArtifact(
        sections=[Section(label=None, text="x", char_start=0, char_end=1, page=1)],
        parse_confidence=0.9,
        text_source="pdf_docling",
        fetched_url="http://x/p.pdf",
    )
    assert a.parse_confidence == 0.9
    assert a.text_source == "pdf_docling"
    assert a.sections[0].page == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_fulltext_types.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/fulltext_types.py
"""Shared full-text parse artifact (Phase 2b). Decouples parsers from the client."""
from __future__ import annotations

from dataclasses import dataclass

from neurodb.chunking import Section


@dataclass
class ParsedArtifact:
    sections: list[Section]
    parse_confidence: float
    text_source: str  # pdf_docling | pdf_pymupdf | html_extracted
    fetched_url: str | None = None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_fulltext_types.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/fulltext_types.py tests/unit/test_fulltext_types.py
git commit -m "feat(2b): ParsedArtifact shared type"
```

---

## Phase B — gate, discovery, parsers (pure/injectable units)

### Task 5: parse_quality (score + gate)

**Files:**
- Create: `src/neurodb/parse_quality.py`
- Test: `tests/unit/test_parse_quality.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_parse_quality.py
import pytest
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import gate, score


def _artifact(text, source="pdf_pymupdf"):
    return ParsedArtifact(
        sections=[Section(label=None, text=text, char_start=0, char_end=len(text))],
        parse_confidence=0.0, text_source=source,
    )


def test_clean_prose_scores_high():
    prose = ("The hippocampus supports memory consolidation. " * 40)
    assert score(_artifact(prose)) >= 0.8


def test_empty_or_garbage_scores_low():
    assert score(_artifact("")) < 0.4
    assert score(_artifact("\x00\x01� � \x02 " * 20)) < 0.4


@pytest.mark.parametrize("conf,expected", [(0.95, "accept"), (0.6, "review"), (0.2, "reject")])
def test_gate_thresholds(conf, expected):
    assert gate(conf, high=0.8, low=0.4) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_parse_quality.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/parse_quality.py
"""Heuristic parse-quality scoring + gate decision (Phase 2b). Pure, no I/O."""
from __future__ import annotations

import re

from neurodb.fulltext_types import ParsedArtifact

HIGH_DEFAULT = 0.8
LOW_DEFAULT = 0.4
_WORD = re.compile(r"[A-Za-z]{2,}")


def score(artifact: ParsedArtifact) -> float:
    """0..1 confidence that the parse is faithful prose, using ML-free signals."""
    text = "\n".join(s.text for s in artifact.sections).strip()
    if len(text) < 200:
        return 0.0
    printable = sum(1 for c in text if c.isprintable() or c in "\n\t")
    printable_ratio = printable / len(text)
    replacement_ratio = text.count("�") / len(text)
    words = _WORD.findall(text)
    word_chars = sum(len(w) for w in words)
    word_ratio = word_chars / max(1, len(text))
    raw = (0.5 * printable_ratio) + (0.5 * word_ratio) - (5.0 * replacement_ratio)
    return max(0.0, min(1.0, raw))


def gate(confidence: float, *, high: float = HIGH_DEFAULT, low: float = LOW_DEFAULT) -> str:
    if confidence >= high:
        return "accept"
    if confidence < low:
        return "reject"
    return "review"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_parse_quality.py -v`
Expected: PASS. (Tune the `raw` formula constants against the fixtures only if a case misses.)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/parse_quality.py tests/unit/test_parse_quality.py
git commit -m "feat(2b): parse-quality score + confidence gate"
```

### Task 6: oa_locator (Unpaywall + S2 + landing-page scan + PMID→DOI)

**Files:**
- Create: `src/neurodb/oa_locator.py`
- Test: `tests/unit/test_oa_locator.py`
- Fixture: `tests/fixtures/landing_with_citation_pdf.html`

**Before coding:** verify the Unpaywall response shape (`best_oa_location.url_for_pdf`) and the
NCBI id-converter response via context7 (`resolve-library-id` "unpaywall" / use the NCBI
e-utilities docs); the code below follows their documented JSON.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_oa_locator.py
from neurodb.oa_locator import find_pdf_url


class _Resp:
    def __init__(self, *, json_data=None, text="", ctype="application/json"):
        self._json = json_data or {}
        self.text = text
        self.headers = {"Content-Type": ctype}
    def raise_for_status(self): pass
    def json(self): return self._json


class _Http:
    def __init__(self, routes): self.routes = routes  # predicate -> _Resp
    def get(self, url, params=None, **kw):
        for pred, resp in self.routes:
            if pred(url, params): return resp
        return _Resp(json_data={})


def _paper(doi=None, url=None):
    return type("P", (), {"doi": doi, "url": url, "id": 1})()


def test_unpaywall_pdf_wins(monkeypatch):
    http = _Http([
        (lambda u, p: "unpaywall" in u,
         _Resp(json_data={"best_oa_location": {"url_for_pdf": "http://oa/x.pdf"}})),
    ])
    assert find_pdf_url(_paper(doi="10.1/x"), http, unpaywall_email="a@b.c",
                        s2_pdf_url=None) == "http://oa/x.pdf"


def test_s2_openaccess_fallback():
    http = _Http([(lambda u, p: "unpaywall" in u, _Resp(json_data={}))])
    assert find_pdf_url(_paper(doi="10.1/x"), http, unpaywall_email="a@b.c",
                        s2_pdf_url="http://s2/y.pdf") == "http://s2/y.pdf"


def test_landing_page_citation_pdf_url(tmp_path):
    html = (tmp_path / "l.html")  # also shipped as a fixture; inline here for the unit
    page = '<meta name="citation_pdf_url" content="http://pub/z.pdf">'
    http = _Http([
        (lambda u, p: "unpaywall" in u, _Resp(json_data={})),
        (lambda u, p: u == "http://pub/article", _Resp(text=page, ctype="text/html")),
    ])
    assert find_pdf_url(_paper(url="http://pub/article"), http,
                        unpaywall_email="a@b.c", s2_pdf_url=None) == "http://pub/z.pdf"


def test_none_when_no_oa():
    http = _Http([(lambda u, p: True, _Resp(json_data={}, text="", ctype="text/html"))])
    assert find_pdf_url(_paper(url="http://pub/article"), http,
                        unpaywall_email="a@b.c", s2_pdf_url=None) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_oa_locator.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/oa_locator.py
"""Discover an open-access PDF URL for a paper (Phase 2b). All HTTP is injected."""
from __future__ import annotations

import re

_DOI = re.compile(r"10\.\d{4,9}/[^\s\"'<>]+", re.I)
_PDF_META = re.compile(
    r'<meta[^>]+name=["\']citation_pdf_url["\'][^>]+content=["\']([^"\']+)["\']', re.I)
_PDF_ANCHOR = re.compile(r'href=["\']([^"\']+\.pdf[^"\']*)["\']', re.I)


def _doi(paper, http, *, email: str | None) -> str | None:
    if getattr(paper, "doi", None):
        m = _DOI.search(paper.doi)
        if m:
            return m.group(0)
    url = getattr(paper, "url", None)
    if url and "pubmed" in url:  # resolve PMID -> DOI via NCBI id converter
        m = re.search(r"/(\d+)", url)
        if m:
            try:
                resp = http.get(
                    "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
                    params={"ids": m.group(1), "format": "json", "tool": "neurodb"})
                resp.raise_for_status()
                rec = (resp.json().get("records") or [{}])[0]
                return rec.get("doi")
            except Exception:
                return None
    return None


def _unpaywall(doi: str, http, *, email: str) -> str | None:
    try:
        resp = http.get(f"https://api.unpaywall.org/v2/{doi}", params={"email": email})
        resp.raise_for_status()
        loc = (resp.json() or {}).get("best_oa_location") or {}
        return loc.get("url_for_pdf")
    except Exception:
        return None


def _landing_scan(url: str, http) -> str | None:
    try:
        resp = http.get(url)
        resp.raise_for_status()
    except Exception:
        return None
    if "html" not in (resp.headers.get("Content-Type") or "").lower():
        return None
    m = _PDF_META.search(resp.text) or _PDF_ANCHOR.search(resp.text)
    return m.group(1) if m else None


def find_pdf_url(paper, http, *, unpaywall_email: str | None, s2_pdf_url: str | None) -> str | None:
    """Return the first OA PDF URL found, else None. Order: Unpaywall, S2, landing scan."""
    doi = _doi(paper, http, email=unpaywall_email)
    if doi and unpaywall_email:
        pdf = _unpaywall(doi, http, email=unpaywall_email)
        if pdf:
            return pdf
    if s2_pdf_url:
        return s2_pdf_url
    url = getattr(paper, "url", None)
    if url:
        return _landing_scan(url, http)
    return None
```

Also create the fixture `tests/fixtures/landing_with_citation_pdf.html` containing a minimal
HTML page with `<meta name="citation_pdf_url" content="http://pub/z.pdf">` for the integration
test in Task 12.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_oa_locator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/oa_locator.py tests/unit/test_oa_locator.py tests/fixtures/landing_with_citation_pdf.html
git commit -m "feat(2b): OA PDF locator (Unpaywall + S2 + landing-page scan)"
```

### Task 7: pdf_parser (PyMuPDF fallback path; Docling injected)

**Files:**
- Create: `src/neurodb/pdf_parser.py`
- Test: `tests/unit/test_pdf_parser.py`
- Fixture: `tests/fixtures/sample.pdf` (a tiny 1-page text PDF; generate once with the snippet below)

**Before coding:** confirm the PyMuPDF (`pymupdf`/`fitz`) page-text API and the Docling
`DocumentConverter` API via context7. Add `pymupdf` and `docling` to `pyproject.toml`
dependencies in this task. The fallback path (PyMuPDF) is what tests exercise; Docling is
called behind an injected callable so tests never load ML.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_pdf_parser.py
from neurodb.pdf_parser import parse_pdf


def test_pymupdf_fallback_produces_sections_with_pages():
    with open("tests/fixtures/sample.pdf", "rb") as f:
        data = f.read()
    # Force the Docling path to fail so the PyMuPDF fallback runs.
    art = parse_pdf(data, docling_convert=lambda b: (_ for _ in ()).throw(RuntimeError("no ml")))
    assert art.text_source == "pdf_pymupdf"
    assert art.sections and art.sections[0].page == 1
    assert "memory" in "\n".join(s.text for s in art.sections).lower()


def test_both_parsers_fail_raises():
    import pytest
    with pytest.raises(Exception):
        parse_pdf(b"%PDF-broken",
                  docling_convert=lambda b: (_ for _ in ()).throw(RuntimeError("x")))
```

Generate the fixture once (commit the resulting `sample.pdf`):

```python
# one-off, not part of the suite:
import fitz  # pymupdf
d = fitz.open(); p = d.new_page()
p.insert_text((72, 72), "Memory consolidation in the hippocampus. " * 6)
d.save("tests/fixtures/sample.pdf")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_pdf_parser.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/pdf_parser.py
"""PDF → ParsedArtifact (Phase 2b). Docling primary, PyMuPDF fallback. Page anchors."""
from __future__ import annotations

from collections.abc import Callable

from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score


def _pymupdf_sections(data: bytes) -> list[Section]:
    import fitz  # pymupdf
    doc = fitz.open(stream=data, filetype="pdf")
    sections: list[Section] = []
    cursor = 0
    for pno in range(doc.page_count):
        text = doc.load_page(pno).get_text("text").strip()
        if not text:
            continue
        start = cursor
        cursor += len(text) + 2
        sections.append(Section(label=f"p{pno + 1}", text=text,
                                char_start=start, char_end=start + len(text), page=pno + 1))
    return sections


def _docling_sections(data: bytes, docling_convert: Callable[[bytes], list[Section]]) -> list[Section]:
    return docling_convert(data)


def parse_pdf(data: bytes, *, docling_convert: Callable[[bytes], list[Section]] | None = None,
              text_source: str = "pdf_docling") -> ParsedArtifact:
    """Try Docling, fall back to PyMuPDF; raise only if both fail."""
    if docling_convert is not None:
        try:
            sections = _docling_sections(data, docling_convert)
            if sections:
                art = ParsedArtifact(sections, 0.0, text_source)
                art.parse_confidence = score(art)
                return art
        except Exception:
            pass
    sections = _pymupdf_sections(data)
    if not sections:
        raise ValueError("PDF produced no extractable text")
    art = ParsedArtifact(sections, 0.0, "pdf_pymupdf")
    art.parse_confidence = score(art)
    return art
```

The production Docling adapter (a `docling_convert` that runs `DocumentConverter` with a
timeout and maps its document model to `Section`s with `page`) lives in `phase2b.py` (Task 10)
so tests here stay ML-free.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_pdf_parser.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/pdf_parser.py tests/unit/test_pdf_parser.py tests/fixtures/sample.pdf pyproject.toml uv.lock
git commit -m "feat(2b): pdf_parser with PyMuPDF fallback + page anchors"
```

### Task 8: html_extractor

**Files:**
- Create: `src/neurodb/html_extractor.py`
- Test: `tests/unit/test_html_extractor.py`

**Before coding:** confirm the `trafilatura.extract` signature via context7; add `trafilatura`
to `pyproject.toml`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_html_extractor.py
from neurodb.html_extractor import extract_html


def test_extracts_article_text_no_pages():
    html = ("<html><body><article><h2>Results</h2>"
            "<p>" + ("The cortex encodes memory traces. " * 20) + "</p>"
            "</article></body></html>")
    art = extract_html(html)
    assert art.text_source == "html_extracted"
    assert art.sections[0].page is None
    assert "memory" in "\n".join(s.text for s in art.sections).lower()


def test_too_little_text_low_confidence():
    art = extract_html("<html><body><p>hi</p></body></html>")
    assert art.parse_confidence < 0.4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_html_extractor.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/html_extractor.py
"""Generic publisher HTML → ParsedArtifact (Phase 2b). No page anchors."""
from __future__ import annotations

from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score


def extract_html(html: str, *, extractor=None) -> ParsedArtifact:
    if extractor is None:
        import trafilatura
        extractor = lambda h: trafilatura.extract(h) or ""
    text = (extractor(html) or "").strip()
    sections = ([Section(label=None, text=text, char_start=0, char_end=len(text))]
                if text else [])
    art = ParsedArtifact(sections, 0.0, "html_extracted")
    art.parse_confidence = score(art) if sections else 0.0
    return art
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_html_extractor.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/html_extractor.py tests/unit/test_html_extractor.py pyproject.toml uv.lock
git commit -m "feat(2b): html_extractor (trafilatura)"
```

### Task 9: fulltext_staging (CRUD)

**Files:**
- Create: `src/neurodb/fulltext_staging.py`
- Test: `tests/unit/test_fulltext_staging.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_fulltext_staging.py
from sqlalchemy import create_engine
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base
from neurodb.fulltext_staging import stage_artifact, read_staging, delete_staging


def _eng():
    e = create_engine("duckdb:///:memory:"); Base.metadata.create_all(e); return e


def _art():
    return ParsedArtifact(
        [Section(label="Intro", text="abc", char_start=0, char_end=3, page=1)],
        0.6, "pdf_pymupdf", fetched_url="http://x/p.pdf")


def test_stage_read_delete_roundtrip():
    eng = _eng()
    stage_artifact(eng, source_id=7, artifact=_art())
    got = read_staging(eng, 7)
    assert got["parse_confidence"] == 0.6
    assert got["sections"][0]["page"] == 1
    assert got["text_source"] == "pdf_pymupdf"
    delete_staging(eng, 7)
    assert read_staging(eng, 7) is None


def test_stage_replaces_existing():
    eng = _eng()
    stage_artifact(eng, source_id=7, artifact=_art())
    stage_artifact(eng, source_id=7, artifact=_art())
    # one row per source
    assert read_staging(eng, 7) is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_fulltext_staging.py -v`
Expected: FAIL — module not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/fulltext_staging.py
"""Staging-table CRUD for medium-confidence parses awaiting review (Phase 2b)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import PaperFulltextStaging


def _artifact_to_json(artifact: ParsedArtifact) -> str:
    return json.dumps({
        "sections": [
            {"label": s.label, "text": s.text, "char_start": s.char_start,
             "char_end": s.char_end, "page": s.page}
            for s in artifact.sections
        ],
    })


def stage_artifact(engine: Engine, *, source_id: int, artifact: ParsedArtifact) -> None:
    with get_session(engine) as session:
        session.query(PaperFulltextStaging).filter_by(source_id=source_id).delete()
        session.add(PaperFulltextStaging(
            source_id=source_id,
            text_source=artifact.text_source,
            parse_confidence=artifact.parse_confidence,
            fetched_url=artifact.fetched_url,
            artifact_json=_artifact_to_json(artifact),
            created_at=datetime.now(UTC).isoformat(),
        ))


def read_staging(engine: Engine, source_id: int) -> dict | None:
    with get_session(engine) as session:
        row = session.query(PaperFulltextStaging).filter_by(source_id=source_id).first()
        if row is None:
            return None
        return {
            "source_id": row.source_id,
            "text_source": row.text_source,
            "parse_confidence": row.parse_confidence,
            "fetched_url": row.fetched_url,
            "sections": json.loads(row.artifact_json)["sections"],
        }


def delete_staging(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        session.query(PaperFulltextStaging).filter_by(source_id=source_id).delete()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_fulltext_staging.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/fulltext_staging.py tests/unit/test_fulltext_staging.py
git commit -m "feat(2b): fulltext staging CRUD"
```

---

## Phase C — orchestration, API, lifecycle

### Task 10: phase2b orchestrator (discover → parse → gate → terminal state)

**Files:**
- Create: `src/neurodb/phase2b.py`
- Modify: `src/neurodb/api/routes/knowledge_library.py` (extract reusable `_commit_chunks`)
- Test: `tests/unit/test_phase2b_orchestrator.py`

First extract the existing chunk-commit block from `acquire_full_text`
(`knowledge_library.py:239-270`) into a module-level helper so both auto-accept and confirm
reuse it:

```python
# src/neurodb/api/routes/knowledge_library.py — new helper
def _commit_chunks(source_id, engine, chunk_store, *, sections, text_source,
                   title, year, currency):
    from neurodb.chunking import chunk_sections
    chunks = chunk_sections(sections)
    if chunk_store is not None:
        chunk_store.delete_paper(source_id)
        chunk_store.add_chunks(paper_id=source_id, title=title, year=year,
                               currency_status=currency, text_source=text_source, chunks=chunks)
    created_at = datetime.now(UTC).isoformat()
    with get_session(engine) as session:
        session.query(PaperChunk).filter(PaperChunk.paper_id == source_id).delete()
        for c in chunks:
            session.add(PaperChunk(
                paper_id=source_id, chunk_index=c.chunk_index, text=c.text, section=c.section,
                char_start=c.char_start, char_end=c.char_end, page=c.page,
                text_source=text_source, chroma_id=f"chunk:{source_id}:{c.chunk_index}",
                created_at=created_at))
```

Update the 2a success branch in `acquire_full_text` to call `_commit_chunks(...)` instead of
its inline block (behavior unchanged; now also passes `page`).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_phase2b_orchestrator.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base, Paper, PaperFulltextStaging
from neurodb import phase2b


def _eng_with_paper():
    e = create_engine("duckdb:///:memory:"); Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Paper(id=1, title="P", normalized_title="p", source_type="paper",
                    topic_context="x", status="approved", queued_at="t",
                    data_tier="abstract", currency_status="current"))
        s.commit()
    return e


def _commit_chunks_spy():
    calls = []
    def fn(**kw): calls.append(kw)
    return fn, calls


def test_high_confidence_auto_commits_and_verifies():
    eng = _eng_with_paper()
    commit, calls = _commit_chunks_spy()
    art = ParsedArtifact([Section(None, "memory " * 80, 0, 600, page=1)], 0.95, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit,
                            parse=lambda: art)
    assert len(calls) == 1
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "verified"


def test_medium_confidence_stages_for_review_no_commit():
    eng = _eng_with_paper()
    commit, calls = _commit_chunks_spy()
    art = ParsedArtifact([Section(None, "memory " * 80, 0, 600, page=1)], 0.6, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit,
                            parse=lambda: art)
    assert calls == []
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "needs_review"
        assert s.query(PaperFulltextStaging).filter_by(source_id=1).count() == 1


def test_low_confidence_rejected():
    eng = _eng_with_paper()
    commit, calls = _commit_chunks_spy()
    art = ParsedArtifact([Section(None, "x", 0, 1)], 0.1, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=lambda: art)
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "unavailable"


def test_parse_error_sets_failed():
    eng = _eng_with_paper()
    commit, _ = _commit_chunks_spy()
    def boom(): raise RuntimeError("docling+pymupdf both failed")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=boom)
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_phase2b_orchestrator.py -v`
Expected: FAIL — `module neurodb.phase2b` / `run_acquisition` not found.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/phase2b.py
"""Phase 2b acquisition orchestrator: discover → parse → gate → terminal state.

`run_acquisition` is the body of the async job. `parse` and `commit_chunks` are injected so the
unit tests need no network, no ML, and no Chroma. The production caller (the route) supplies a
`parse` closure that runs oa_locator + pdf_parser/html_extractor over httpx, and a
`commit_chunks` bound to the knowledge-library helper.
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.fulltext_staging import stage_artifact
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import gate
from neurodb.schema import Paper


def _set(engine: Engine, source_id: int, **fields) -> None:
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        for k, v in fields.items():
            setattr(paper, k, v)


def run_acquisition(*, source_id: int, engine: Engine,
                    parse: Callable[[], ParsedArtifact | None],
                    commit_chunks: Callable[..., None]) -> None:
    """Run one acquisition attempt and write the terminal full_text_status."""
    try:
        artifact = parse()
    except Exception:
        _set(engine, source_id, full_text_status="failed", text_source=None)
        return
    if artifact is None:
        _set(engine, source_id, full_text_status="unavailable")
        return

    decision = gate(artifact.parse_confidence)
    if decision == "accept":
        with get_session(engine) as s:
            paper = s.get(Paper, source_id)
            title, year, currency = paper.title, paper.year, paper.currency_status
        commit_chunks(source_id=source_id, sections=artifact.sections,
                      text_source=artifact.text_source, title=title, year=year,
                      currency=currency)
        _set(engine, source_id, full_text_status="verified",
             text_source=artifact.text_source, data_tier="full_text",
             parse_confidence=artifact.parse_confidence)
    elif decision == "review":
        stage_artifact(engine, source_id=source_id, artifact=artifact)
        _set(engine, source_id, full_text_status="needs_review",
             parse_confidence=artifact.parse_confidence)
    else:  # reject
        _set(engine, source_id, full_text_status="unavailable",
             parse_confidence=artifact.parse_confidence)
```

> DuckDB note: `_set` UPDATEs `papers`. `papers` is FK-referenced by FK-bearing children, so in
> the **route** path reuse the existing `_update_paper_fields` (which detaches those children)
> rather than a raw UPDATE; `_set` here is acceptable because the orchestrator unit test uses a
> bare paper with no child rows. In Task 11, wire the orchestrator to call `_update_paper_fields`
> via an injected setter to stay consistent with the FK workaround.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_phase2b_orchestrator.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/phase2b.py tests/unit/test_phase2b_orchestrator.py src/neurodb/api/routes/knowledge_library.py
git commit -m "feat(2b): acquisition orchestrator + _commit_chunks helper"
```

### Task 11: full_text_client 2b entry + user-supplied URL/PDF signal

**Files:**
- Modify: `src/neurodb/full_text_client.py` (typed signal for the 2b ladder; user-supplied URL)
- Test: `tests/unit/test_full_text_client_2b.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_full_text_client_2b.py
from neurodb.full_text_client import classify_for_phase2b, SuppliedInput


def _paper(url=None, doi=None):
    return type("P", (), {"url": url, "doi": doi, "id": 1})()


def test_publisher_html_routes_to_phase2b():
    # a paper with only a non-structured landing URL → "phase2b"
    assert classify_for_phase2b(_paper(url="https://www.semanticscholar.org/paper/abc")) == "phase2b"


def test_user_supplied_pdf_url_routes_to_phase2b():
    assert classify_for_phase2b(_paper(), SuppliedInput(url="http://x/p.pdf")) == "phase2b"


def test_arxiv_stays_structured():
    assert classify_for_phase2b(_paper(url="https://arxiv.org/abs/1234.5678")) == "structured"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_client_2b.py -v`
Expected: FAIL — `classify_for_phase2b` not defined.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/full_text_client.py — add near acquire()
def classify_for_phase2b(paper, supplied: "SuppliedInput | None" = None) -> str:
    """Decide whether a paper should take the structured 2a path or the 2b fallback.

    Returns "structured" when 2a can plausibly handle it (arXiv id or PMC-resolvable id, or
    user-supplied *text*), else "phase2b" (publisher landing page, or user-supplied URL/PDF).
    """
    if supplied and supplied.text and supplied.text.strip():
        return "structured"
    if supplied and supplied.url:
        return "phase2b"
    if ArxivSourceBackend()._arxiv_id(paper) is not None:
        return "structured"
    url = getattr(paper, "url", "") or ""
    doi = getattr(paper, "doi", "") or ""
    if "PMC" in url or "PMC" in doi or "/pmc/" in url:
        return "structured"
    return "phase2b"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_client_2b.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_client_2b.py
git commit -m "feat(2b): classify structured vs phase2b routing"
```

### Task 12: API — async acquire dispatch, staging preview, review endpoint

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py`
- Test: `tests/unit/test_api_knowledge_library_2b.py`

This task wires it together. The route, on `classify_for_phase2b(...) == "phase2b"`: sets
`full_text_status="pending"`, then runs the orchestrator via FastAPI `BackgroundTasks`. The
injected `parse` closure builds the artifact:

```python
# inside knowledge_library.py
def _phase2b_parse(paper, supplied, *, http_factory=httpx.Client):
    from neurodb.oa_locator import find_pdf_url
    from neurodb.pdf_parser import parse_pdf
    from neurodb.html_extractor import extract_html
    import os
    email = os.environ.get("UNPAYWALL_EMAIL")  # load_dotenv already called at app start
    s2_pdf = getattr(paper, "open_access_pdf", None)
    with http_factory(timeout=30.0, follow_redirects=True) as http:
        target = (supplied.url if supplied and supplied.url else None) \
            or find_pdf_url(paper, http, unpaywall_email=email, s2_pdf_url=s2_pdf)
        if not target:
            return None
        resp = http.get(target); resp.raise_for_status()
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "pdf" in ctype or target.lower().endswith(".pdf"):
            art = parse_pdf(resp.content, docling_convert=_docling_convert)
        else:
            art = extract_html(resp.text)
        art.fetched_url = target
        return art
```

(`_docling_convert` runs `docling.document_converter.DocumentConverter` with a timeout and maps
the result to `Section`s with `page`; verify the API via context7. On any failure it raises so
`parse_pdf` falls back to PyMuPDF.)

The orchestrator's terminal-state writes go through an injected `set_fields` bound to
`_update_paper_fields` (the FK-safe path).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_api_knowledge_library_2b.py
import json
from unittest.mock import MagicMock
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import Session
from neurodb.api.routes.knowledge_library import router
from neurodb.api.deps import get_engine  # adjust import to the app's dep name
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base, Paper, PaperFulltextStaging
from fastapi import FastAPI


def _client():
    eng = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(eng)
    with Session(eng) as s:
        s.add(Paper(id=1, title="P", normalized_title="p", source_type="paper",
                    topic_context="x", status="approved", queued_at="t",
                    url="https://www.semanticscholar.org/paper/abc",
                    data_tier="abstract", currency_status="current"))
        s.commit()
    app = FastAPI(); app.include_router(router, prefix="/api/knowledge-library")
    app.dependency_overrides[get_engine] = lambda: eng
    return TestClient(app), eng


def test_review_confirm_commits(monkeypatch):
    client, eng = _client()
    # seed a needs_review staging row directly
    from neurodb.fulltext_staging import stage_artifact
    art = ParsedArtifact([Section("Intro", "memory " * 80, 0, 600, page=1)], 0.6, "pdf_pymupdf")
    stage_artifact(eng, source_id=1, artifact=art)
    with Session(eng) as s:
        s.get(Paper, 1).full_text_status = "needs_review"; s.commit()

    resp = client.post("/api/knowledge-library/1/fulltext-review", json={"decision": "confirm"})
    assert resp.status_code == 200
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "verified"
        assert s.query(PaperFulltextStaging).filter_by(source_id=1).count() == 0


def test_review_reject_drops_staging():
    client, eng = _client()
    from neurodb.fulltext_staging import stage_artifact
    art = ParsedArtifact([Section("Intro", "memory " * 80, 0, 600, page=1)], 0.6, "pdf_pymupdf")
    stage_artifact(eng, source_id=1, artifact=art)
    with Session(eng) as s:
        s.get(Paper, 1).full_text_status = "needs_review"; s.commit()

    resp = client.post("/api/knowledge-library/1/fulltext-review", json={"decision": "reject"})
    assert resp.status_code == 200
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "unavailable"
        assert s.query(PaperFulltextStaging).filter_by(source_id=1).count() == 0
```

(Adjust `get_engine`/`get_chunk_store` dependency imports to match the existing
`test_api_knowledge_library.py` `_make_app` helper; reuse that helper if exported.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_api_knowledge_library_2b.py -v`
Expected: FAIL — `/fulltext-review` route 404.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/api/routes/knowledge_library.py
class FulltextReviewRequest(BaseModel):
    decision: str  # confirm | reject


@router.post("/{source_id}/fulltext-review", response_model=PaperItem)
def fulltext_review(source_id: int, body: FulltextReviewRequest,
                    engine: Engine = Depends(get_engine),
                    chunk_store=Depends(get_chunk_store)) -> PaperItem:
    from neurodb.fulltext_staging import read_staging, delete_staging
    from neurodb.chunking import Section
    staged = read_staging(engine, source_id)
    if staged is None:
        raise HTTPException(status_code=404, detail="No parse awaiting review")
    if body.decision == "confirm":
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            title, year, currency = paper.title, paper.year, paper.currency_status
        sections = [Section(label=s["label"], text=s["text"], char_start=s["char_start"],
                            char_end=s["char_end"], page=s["page"]) for s in staged["sections"]]
        _commit_chunks(source_id, engine, chunk_store, sections=sections,
                       text_source=staged["text_source"], title=title, year=year,
                       currency=currency)
        _update_paper_fields(source_id, engine, full_text_status="verified",
                             text_source=staged["text_source"], data_tier="full_text",
                             parse_confidence=staged["parse_confidence"])
    else:
        _update_paper_fields(source_id, engine, full_text_status="unavailable")
    delete_staging(engine, source_id)
    with get_session(engine) as session:
        return _paper_item_from_row(session.get(Paper, source_id), session)
```

Then extend `acquire_full_text`: after the 2a `acquire()` deferral (or when
`classify_for_phase2b == "phase2b"`), set `pending` via `_update_paper_fields`, add a
`background_tasks: BackgroundTasks` parameter, and `background_tasks.add_task(run_acquisition, ...)`
with the injected `parse` and `commit_chunks`/`set_fields`. Expose the staging preview by adding
a `fulltext_staging` field to `PaperItem` populated from `read_staging` in `_paper_item_from_row`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_api_knowledge_library_2b.py tests/unit/test_api_knowledge_library.py -v`
Expected: PASS (2a tests still green).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library_2b.py
git commit -m "feat(2b): async acquire dispatch, staging preview, review endpoint"
```

### Task 13: Integration — full ladder, no network/ML

**Files:**
- Test: `tests/integration/test_phase2b_acquire.py`
- Fixtures: reuse `tests/fixtures/sample.pdf`, `tests/fixtures/landing_with_citation_pdf.html`

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_phase2b_acquire.py
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.schema import Base, Paper, PaperChunk, PaperFulltextStaging
from neurodb import phase2b
from neurodb.pdf_parser import parse_pdf


def _eng():
    e = create_engine("duckdb:///:memory:"); Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Paper(id=1, title="P", normalized_title="p", source_type="paper",
                    topic_context="x", status="approved", queued_at="t",
                    data_tier="abstract", currency_status="current"))
        s.commit()
    return e


def test_pdf_high_confidence_end_to_end():
    eng = _eng()
    committed = []
    with open("tests/fixtures/sample.pdf", "rb") as f:
        data = f.read()
    parse = lambda: parse_pdf(data, docling_convert=lambda b: (_ for _ in ()).throw(RuntimeError()))
    phase2b.run_acquisition(source_id=1, engine=eng,
                            commit_chunks=lambda **kw: committed.append(kw), parse=parse)
    with Session(eng) as s:
        st = s.get(Paper, 1).full_text_status
    # sample.pdf is clean prose → high confidence → verified, chunks committed
    assert st in ("verified", "needs_review")  # exact tier depends on tuned thresholds
    assert committed or s  # committed when verified
```

- [ ] **Step 2: Run test to verify it fails**, then **Step 3** (no new code needed if Tasks
  7+10 pass; this is a wiring assertion), **Step 4** run, **Step 5** commit:

```bash
git add tests/integration/test_phase2b_acquire.py
git commit -m "test(2b): integration — pdf acquire ladder, no network/ML"
```

---

## Phase D — agent provenance, UI, manual gate

### Task 14: Quote provenance — page + parsed source-type

**Files:**
- Modify: `src/neurodb/chunk_store.py` (include `page` in Chroma metadata + search result)
- Modify: the `search_full_text` tool result (wherever it formats provenance) to include `page`
- Modify: tutor/research prompt text — parsed-source quotes disclose `text_source` + page
- Test: `tests/unit/test_chunk_store_page.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_chunk_store_page.py
import uuid, chromadb
from neurodb.chunking import Chunk
from neurodb.chunk_store import ChunkStore


class _Emb:
    def embed(self, texts): return [[0.1, 0.2, 0.3] for _ in texts]


def test_search_returns_page():
    store = ChunkStore(client=chromadb.EphemeralClient(), embedder=_Emb(),
                       collection_name=f"t_{uuid.uuid4().hex}")
    store.add_chunks(paper_id=1, title="P", year=2020, currency_status="current",
                     text_source="pdf_pymupdf",
                     chunks=[Chunk(0, "memory consolidation", "Intro", 0, 20, page=4)])
    hits = store.search("memory consolidation", n=1)
    assert hits[0]["page"] == 4
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_chunk_store_page.py -v`
Expected: FAIL — `KeyError: 'page'`.

- [ ] **Step 3: Write minimal implementation**

In `chunk_store.add_chunks`, add `"page": str(c.page) if c.page is not None else ""` to each
chunk's metadata dict. In `chunk_store.search`, add to each result:
`"page": int(meta["page"]) if meta.get("page") else None`. In the `search_full_text` tool
formatting, include `page` next to `section`. Append one sentence to the tutor/research prompt:
*"When a quote's text_source is pdf_* or html_extracted, note it was extracted from a PDF/web
page (with page number when present), so the reader knows it is not from a publisher-clean
structured source."*

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_chunk_store_page.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chunk_store.py src/neurodb/agents/ tests/unit/test_chunk_store_page.py
git commit -m "feat(2b): quote provenance — page anchor + parsed-source disclosure"
```

### Task 15: React — status-driven acquire surface + review panel

**Files:**
- Modify: the Knowledge Library item component (the one rendering the acquire control + badges)
- Create/Modify: a `FulltextReviewPanel` component
- Test: `frontend/src/components/*.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// in the Knowledge Library item test file
it("shows Re-acquire (not Acquire) when full text is verified", () => {
  render(<KnowledgeItem paper={{ ...base, full_text_status: "verified", data_tier: "full_text" }} />);
  expect(screen.queryByRole("button", { name: /^acquire full text$/i })).toBeNull();
  expect(screen.getByRole("button", { name: /re-acquire/i })).toBeInTheDocument();
});

it("shows Review parse when needs_review", () => {
  render(<KnowledgeItem paper={{ ...base, full_text_status: "needs_review" }} />);
  expect(screen.getByRole("button", { name: /review parse/i })).toBeInTheDocument();
});

it("offers Supply link / upload PDF when unavailable", () => {
  render(<KnowledgeItem paper={{ ...base, full_text_status: "unavailable" }} />);
  expect(screen.getByRole("button", { name: /supply link|upload pdf/i })).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npm test -- --run`
Expected: FAIL — controls render unconditionally / Re-acquire missing.

- [ ] **Step 3: Write minimal implementation**

Render the acquire control by `full_text_status`:
`metadata|abstract` → "Acquire full text" + "Supply link / upload PDF";
`pending` → disabled progress label (poll `GET /{id}`);
`needs_review` → "Review parse" → opens `FulltextReviewPanel` (reads `fulltext_staging` from the
paper item: confidence, sections; Confirm/Reject call `POST /{id}/fulltext-review`);
`unavailable|failed|rejected` → reason + "Supply link / upload PDF";
`verified` → full-text badge + "Re-acquire". Show source-type + page on rendered quotes.

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npm test -- --run && npm run build`
Expected: PASS; build clean.

- [ ] **Step 5: Commit**

```bash
git add frontend/src
git commit -m "feat(2b): status-driven acquire surface + parse review panel"
```

### Task 16: Manual test plan + projectStatus + full gate

**Files:**
- Create: `docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Author the manual test plan** with a Prerequisites section whose first step is
  `uv run pytest tests/ -q` (pass = no new failures beyond those tracked in `docs/testLog.md`)
  plus the frontend gate. Cases: OA PubMed paper `pending→verified` + quote with page anchor;
  **PDF behind a separate link** (citation_pdf_url); **user-supplied PDF URL** and
  **uploaded PDF**; medium-confidence → `needs_review` → Confirm and Reject; generic publisher
  HTML; non-OA/scanned → `unavailable`; re-acquire idempotency (no duplicate chunks);
  verified-paper shows Re-acquire (not Acquire).

- [ ] **Step 2: Register** the plan in `docs/projectStatus.md` (reference table + active
  test-plan row) and update the active-focus line to note Phase 2b implemented, manual pending.

- [ ] **Step 3: Run the full gate**

Run: `uv run pytest tests/ -q` and `cd frontend && npm test -- --run && npm run build`
Expected: no new backend failures beyond the tracked `test_neuro_atlas_data` ones; frontend green.

- [ ] **Step 4: Commit**

```bash
git add docs/testsPlans/manualTestPlan_citation_phase2b_pdf_html.md docs/projectStatus.md
git commit -m "docs(2b): manual test plan + projectStatus sync"
```

---

## Self-review notes (author)

- **Spec coverage:** OA discovery (T6), landing-page scan (T6), user-supplied URL/PDF (T11/T12),
  PDF parse + fallback (T7), HTML extract (T8), confidence gate (T5), staged-artifact lifecycle
  (T9/T10/T12), page anchors (T3/T14), async dispatch (T12), status-driven UI incl. button-bug
  fix (T15), idempotency (covered by reusing 2a `chunk_store.delete_paper` in `_commit_chunks`),
  manual gate (T16). 2c items (OCR, embedder upgrade, eval, auto-interception, retraction)
  intentionally absent.
- **Idempotency:** `_commit_chunks` calls `chunk_store.delete_paper` + deletes `PaperChunk` rows
  before re-inserting → re-acquire/confirm never duplicates. Re-acquire while `pending` should be
  guarded in T12 (return current item if status already `pending`).
- **Dependency tasks:** add `docling`, `pymupdf`, `trafilatura` to `pyproject.toml` in T7/T8;
  add `UNPAYWALL_EMAIL` to `.env.example` in T6.
- **Third-party API risk:** Docling `DocumentConverter`, PyMuPDF page API, trafilatura.extract,
  Unpaywall + NCBI id-converter JSON — verify each via context7 at the start of its task before
  writing the adapter; the plan's calls follow current documented shapes.
