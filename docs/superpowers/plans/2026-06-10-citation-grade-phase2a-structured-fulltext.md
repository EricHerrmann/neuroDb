# Citation-Grade Phase 2a — Structured-Source Full-Text RAG — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the tutor and research agents quote real paper text with provenance, for papers the user acquires from structured sources (arXiv HTML/LaTeX, PMC JATS, user-supplied clean text), via a second Chroma collection, a dedicated quote tool, and fail-closed quote verification.

**Architecture:** A separate `FullTextBackend` fetch layer (independent of the search path) acquires clean structured text on a per-paper "Acquire full text" action; the text is section-chunked with offset provenance into a new `paper_chunks` table and a second `knowledge_chunks` Chroma collection; agents retrieve quotable passages through `search_full_text` and must earn a `[verified]` tag via `verify_quote` (default unverified), backstopped by an end-of-turn reconciliation of the agent's own tool-call ledger.

**Tech Stack:** Python, SQLAlchemy ORM over DuckDB (SQLite in tests), ChromaDB, httpx, FastAPI, React/vitest, pytest.

**Spec:** `docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md` (invariants #1 tier-as-trust, #2 provenance, #3 threshold, #4 quote verification, #6 disclosure, #8 temporal).

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md` | Create | Phase-gate manual test plan (browser acquire flow + quoting) |
| `docs/projectStatus.md` | Modify | Register plan + manual plan; active focus |
| `src/neurodb/schema.py` | Modify | `Paper.full_text_status`/`text_source`; new `PaperChunk` model |
| `src/neurodb/db.py` | Modify | Migration 024 (`paper_chunks` + 2 Paper columns) + registry entry |
| `src/neurodb/chunking.py` | Create | Pure `chunk_sections` |
| `src/neurodb/full_text_client.py` | Create | Dataclasses, `FullTextBackend` protocol, 3 backends, `acquire` orchestrator |
| `src/neurodb/chunk_store.py` | Create | `ChunkStore` over `knowledge_chunks` |
| `src/neurodb/quote_verify.py` | Create | `normalize_quote`, `verify_quote`, `build_quote_ledger`, `reconcile_quotes` |
| `src/neurodb/agents/full_text_tools.py` | Create | `FULL_TEXT_TOOLS` defs + shared executors |
| `src/neurodb/agents/tutor_agent.py` | Modify | Register tools, dispatch, prompt contract |
| `src/neurodb/agents/research_agent.py` | Modify | Register tools, dispatch, prompt contract |
| `src/neurodb/agents/base.py` | Modify | End-of-turn quote-warning backstop |
| `src/neurodb/api/app.py` | Modify | Build + register `chunk_store` on app state |
| `src/neurodb/api/deps.py` | Modify | `get_chunk_store` provider |
| `src/neurodb/api/schemas/knowledge_library.py` | Modify | `PaperItem.full_text_status`/`text_source` |
| `src/neurodb/api/routes/knowledge_library.py` | Modify | `POST /{id}/acquire-full-text` |
| `src/neurodb/api/routes/chat.py` | Modify | Pass `chunk_store` into agents |
| `frontend/` Knowledge Library component | Modify | Acquire button, tier badge, status |

Fixtures: `tests/fixtures/full_text/` (arXiv HTML, JATS XML samples).

---

## Task 1: Manual test plan (phase-gate, before code)

**Files:**
- Create: `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md`:

```markdown
# Manual Test Plan — Citation-Grade Phase 2a: Structured Full-Text RAG

**Feature:** Acquire structured full text, chunk/embed it, retrieve quotable passages, verify quotes.
**Spec:** docs/superpowers/specs/2026-06-10-citation-grade-phase2a-structured-fulltext-design.md

## Prerequisites
1. **Automated suite green.** Run `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those tracked in `docs/testLog.md`.
2. API/React app running against a local DuckDB + Chroma with `.env` loaded.

## Tests
- **T1 — Acquire arXiv full text.** Approve a paper whose URL is an arXiv abstract page. Click "Acquire full text". Verify the tier badge becomes "full text" and status "verified".
- **T2 — Acquire PMC (OA) full text.** Same for a PMC open-access paper (JATS). Verify "full text"/"verified".
- **T3 — Non-OA / publisher HTML rejected.** Acquire a paper whose URL is a publisher HTML/PDF page. Verify it stays "abstract", status "unavailable", with the Phase-2b deferral message.
- **T4 — User-supplied text.** Paste/upload `.md` text for a paper with no fetchable source. Verify "full text"/"verified".
- **T5 — Grounded quote.** In a tutor chat, ask the agent to quote a passage from a verified paper. Verify the quote renders with a source+section anchor and a `[verified]` marker.
- **T6 — Honest absence.** Ask the agent to quote about a topic absent from any acquired paper. Verify it says it has no grounded full-text support rather than inventing a quote.
- **T7 — Unverified backstop.** Induce the agent to present a quote it did not verify (e.g., a paraphrase in quotes). Verify the response carries the ⚠ unverified notice.
- **T8 — Idempotent re-acquire.** Re-run "Acquire full text" on a verified paper. Verify no duplicate chunks (chunk count unchanged) and status stays "verified".

## Pass/Fail
All of T1–T8 behave as described; no regression in queue/approve/search flows.
```

- [ ] **Step 2: Register in projectStatus.md**

In `docs/projectStatus.md`, under `**Active Plans / Specs**`, add:

```markdown
| `docs/superpowers/plans/2026-06-10-citation-grade-phase2a-structured-fulltext.md` | Citation-grade Phase 2a implementation plan — 13 tasks (migration 024 paper_chunks, chunking, full_text_client backends, chunk_store, quote_verify, full-text tools, agent wiring, ledger backstop, acquire route, React surface, manual gate); ready to execute |
| `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md` | Citation-grade Phase 2a manual test plan — T1-T8 acquire/quote/verify/idempotency; pending implementation |
```

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md docs/projectStatus.md
git commit -m "docs: add citation-grade Phase 2a manual test plan and plan registration"
```

---

## Task 2: Migration 024 + ORM (`paper_chunks`, `full_text_status`, `text_source`)

**Files:**
- Modify: `src/neurodb/schema.py` (after `Paper.currency_status`, ~line 273; add `PaperChunk` class)
- Modify: `src/neurodb/db.py` (add migration after `_migration_023_paper_tier_currency` ~line 844; register in `_MIGRATIONS` ~line 879)
- Test: `tests/unit/test_migration_024_paper_chunks.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_024_paper_chunks.py`:

```python
"""Unit tests for migration 024: paper_chunks + papers.full_text_status/text_source."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_024_paper_chunks
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_024_registered():
    assert _MIGRATIONS.get(24) is _migration_024_paper_chunks


def test_adds_columns_and_table_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)"))
        _migration_024_paper_chunks(conn)
        _migration_024_paper_chunks(conn)  # second run must not raise
        conn.commit()
    insp = inspect(eng)
    cols = {c["name"] for c in insp.get_columns("papers")}
    assert {"full_text_status", "text_source"} <= cols
    assert "paper_chunks" in insp.get_table_names()


def test_full_chain_includes_024():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 24
    assert "paper_chunks" in inspect(eng).get_table_names()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_024_paper_chunks.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_024_paper_chunks'`.

- [ ] **Step 3: Add the ORM columns + `PaperChunk` model**

In `src/neurodb/schema.py`, inside `class Paper`, after the `currency_status` column block, add:

```python
    full_text_status: Mapped[str | None] = mapped_column(String(16), nullable=True)
    text_source: Mapped[str | None] = mapped_column(String(32), nullable=True)
```

Then add a new model after the `Paper` class (before `class ChatSession`):

```python
class PaperChunk(Base):
    """A retrieval unit of a paper's full text, with section/offset provenance."""
    __tablename__ = "paper_chunks"

    id: Mapped[int] = mapped_column(
        Integer, Sequence("paper_chunks_id_seq"), primary_key=True
    )
    # NOTE: paper_id is a plain indexed column, NOT an enforced ForeignKey.
    # DuckDB rejects UPDATE on any column of an FK-referenced row, and the
    # approve/acquire flow UPDATEs papers (status, chroma_id, full_text_status).
    # An enforced FK here would lock those updates. Keep it convention-only,
    # matching the migration DDL (which also omits REFERENCES).
    paper_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    section: Mapped[str | None] = mapped_column(String(256), nullable=True)
    char_start: Mapped[int | None] = mapped_column(Integer, nullable=True)
    char_end: Mapped[int | None] = mapped_column(Integer, nullable=True)
    text_source: Mapped[str] = mapped_column(String(32), nullable=False)
    chroma_id: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

Confirm `Sequence` is imported at the top of `schema.py` (it is used by existing models). No `ForeignKey` is needed for `PaperChunk` — see the note above.

- [ ] **Step 4: Add the migration and register it**

In `src/neurodb/db.py`, after `_migration_023_paper_tier_currency`, add:

```python
def _migration_024_paper_chunks(conn) -> None:
    """Add full-text provenance columns and the paper_chunks table (Phase 2a)."""
    for ddl in (
        "ALTER TABLE papers ADD COLUMN full_text_status VARCHAR(16)",
        "ALTER TABLE papers ADD COLUMN text_source VARCHAR(32)",
    ):
        try:
            conn.execute(text(ddl))
        except Exception:
            pass  # column already exists
    try:
        conn.execute(text(
            """
            CREATE TABLE IF NOT EXISTS paper_chunks (
                id INTEGER PRIMARY KEY,
                paper_id INTEGER NOT NULL,
                chunk_index INTEGER NOT NULL,
                text TEXT NOT NULL,
                section VARCHAR(256),
                char_start INTEGER,
                char_end INTEGER,
                text_source VARCHAR(32) NOT NULL,
                chroma_id VARCHAR(128) NOT NULL,
                created_at VARCHAR(32) NOT NULL
            )
            """
        ))
        conn.execute(text(
            "CREATE INDEX IF NOT EXISTS ix_paper_chunks_paper_id "
            "ON paper_chunks (paper_id)"
        ))
    except Exception:
        pass
```

In the `_MIGRATIONS` dict, after the `23:` entry, add:

```python
    24: _migration_024_paper_chunks,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_024_paper_chunks.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py tests/unit/test_migration_024_paper_chunks.py
git commit -m "feat: add paper_chunks table and full-text provenance columns (migration 024)"
```

---

## Task 3: `chunking.py` — section-aware chunker (pure)

**Files:**
- Create: `src/neurodb/chunking.py`
- Test: `tests/unit/test_chunking.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_chunking.py`:

```python
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
    # offsets are absolute and monotonic; overlap means next start < previous end
    assert chunks[0].char_start == 1000
    assert chunks[1].char_start < chunks[0].char_end
    # indices are sequential across the whole paper
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_indices_run_across_sections():
    secs = [_sec("A", "a" * 50, 0), _sec("B", "b" * 50, 50)]
    chunks = chunk_sections(secs, max_chars=100, overlap=0)
    assert [c.chunk_index for c in chunks] == [0, 1]


def test_empty_sections_yield_no_chunks():
    assert chunk_sections([_sec("Empty", "   ", 0)], max_chars=100, overlap=0) == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_chunking.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.chunking'`.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/chunking.py`:

```python
"""Section-aware chunking for full-text RAG (Phase 2a). Pure, no I/O."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Section:
    label: str | None
    text: str
    char_start: int
    char_end: int


@dataclass
class Chunk:
    chunk_index: int
    text: str
    section: str | None
    char_start: int
    char_end: int


def chunk_sections(
    sections: list[Section], *, max_chars: int = 1200, overlap: int = 150
) -> list[Chunk]:
    """Chunk each section on its own boundaries; split oversize ones with overlap.

    Offsets are absolute (indexing into the normalized full text). Sections that
    are blank after stripping contribute no chunks.
    """
    chunks: list[Chunk] = []
    index = 0
    step = max(1, max_chars - overlap)
    for sec in sections:
        if not sec.text.strip():
            continue
        if len(sec.text) <= max_chars:
            chunks.append(
                Chunk(index, sec.text, sec.label, sec.char_start, sec.char_end)
            )
            index += 1
            continue
        pos = 0
        while pos < len(sec.text):
            piece = sec.text[pos : pos + max_chars]
            if not piece.strip():
                break
            start = sec.char_start + pos
            chunks.append(Chunk(index, piece, sec.label, start, start + len(piece)))
            index += 1
            pos += step
    return chunks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_chunking.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chunking.py tests/unit/test_chunking.py
git commit -m "feat: add section-aware chunk_sections (Phase 2a)"
```

---

## Task 4: `full_text_client.py` — dataclasses, protocol, `UserSuppliedBackend`

**Files:**
- Create: `src/neurodb/full_text_client.py`
- Test: `tests/unit/test_full_text_user_supplied.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_full_text_user_supplied.py`:

```python
from neurodb.full_text_client import (
    FullTextResult,
    SuppliedInput,
    UserSuppliedBackend,
)


class _Paper:
    url = None
    doi = None


def test_markdown_splits_on_headings():
    md = "# Intro\nHello world.\n\n## Methods\nWe did things."
    backend = UserSuppliedBackend()
    supplied = SuppliedInput(text=md, format="md")
    assert backend.can_handle(_Paper(), supplied)
    result = backend.fetch(_Paper(), http=None, supplied=supplied)
    assert isinstance(result, FullTextResult)
    assert result.text_source == "user_supplied"
    labels = [s.label for s in result.sections]
    assert "Intro" in labels and "Methods" in labels
    # offsets index into the normalized full_text
    for s in result.sections:
        assert result.full_text[s.char_start : s.char_end] == s.text


def test_plain_text_is_single_section():
    backend = UserSuppliedBackend()
    supplied = SuppliedInput(text="Just one block of prose.", format="txt")
    result = backend.fetch(_Paper(), http=None, supplied=supplied)
    assert len(result.sections) == 1
    assert result.sections[0].text == "Just one block of prose."


def test_cannot_handle_without_text():
    assert not UserSuppliedBackend().can_handle(_Paper(), SuppliedInput(url="http://x"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_user_supplied.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.full_text_client'`.

- [ ] **Step 3: Write the dataclasses, protocol, and `UserSuppliedBackend`**

Create `src/neurodb/full_text_client.py`:

```python
"""Structured-source full-text acquisition (Phase 2a).

A focused fetch layer, separate from literature_client.search(): given one
already-chosen paper, fetch clean full text from a structured source. No PDF
parsing and no generic-HTML scraping — those are deferred to Phase 2b.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Protocol

from neurodb.chunking import Section


@dataclass
class FullTextResult:
    text_source: str  # arxiv_html | arxiv_src | jats | user_supplied
    sections: list[Section]
    full_text: str


@dataclass
class SuppliedInput:
    url: str | None = None
    text: str | None = None
    format: str | None = None  # txt | md | jats


@dataclass
class AcquireFailure:
    status: str  # unavailable | failed
    reason: str  # needs_parser_phase2b | not_oa | fetch_error | no_source
    message: str


class FullTextBackend(Protocol):
    name: str

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool: ...

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None: ...


def sections_from_labeled_blocks(blocks: list[tuple[str | None, str]]) -> tuple[list[Section], str]:
    """Build offset-correct Sections from (label, text) pairs and the joined full text."""
    sections: list[Section] = []
    parts: list[str] = []
    cursor = 0
    for label, body in blocks:
        body = body.strip()
        if not body:
            continue
        if parts:
            parts.append("\n\n")
            cursor += 2
        start = cursor
        parts.append(body)
        cursor += len(body)
        sections.append(Section(label=label, text=body, char_start=start, char_end=cursor))
    return sections, "".join(parts)


class UserSuppliedBackend:
    name = "user_supplied"

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        return bool(supplied and supplied.text and supplied.text.strip())

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        text = supplied.text
        fmt = (supplied.format or "txt").lower()
        if fmt == "md":
            blocks = _split_markdown(text)
        else:
            blocks = [(None, text)]
        sections, full_text = sections_from_labeled_blocks(blocks)
        if not sections:
            return None
        return FullTextResult("user_supplied", sections, full_text)


def _split_markdown(md: str) -> list[tuple[str | None, str]]:
    blocks: list[tuple[str | None, str]] = []
    label: str | None = None
    buf: list[str] = []
    for line in md.splitlines():
        m = re.match(r"^#{1,6}\s+(.*)$", line)
        if m:
            if buf:
                blocks.append((label, "\n".join(buf).strip()))
                buf = []
            label = m.group(1).strip()
        else:
            buf.append(line)
    if buf:
        blocks.append((label, "\n".join(buf).strip()))
    return blocks
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_user_supplied.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_user_supplied.py
git commit -m "feat: full-text client scaffolding + user-supplied backend (Phase 2a)"
```

---

## Task 5: `ArxivSourceBackend`

**Files:**
- Modify: `src/neurodb/full_text_client.py`
- Create fixture: `tests/fixtures/full_text/arxiv_sample.html`
- Test: `tests/unit/test_full_text_arxiv.py`

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/full_text/arxiv_sample.html` (a minimal arXiv-HTML-shaped doc):

```html
<html><body>
<section><h2>1 Introduction</h2><p>We study engram allocation.</p></section>
<section><h2>2 Methods</h2><p>CREB was overexpressed in the amygdala.</p></section>
</body></html>
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_full_text_arxiv.py`:

```python
from pathlib import Path

from neurodb.full_text_client import ArxivSourceBackend, SuppliedInput

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "full_text" / "arxiv_sample.html"


class _Paper:
    def __init__(self, url=None, doi=None):
        self.url = url
        self.doi = doi


class _StubHttp:
    def __init__(self, body):
        self._body = body
        self.requested = []

    def get(self, url, **kw):
        self.requested.append(url)
        class _R:
            status_code = 200
            text = self._body
            def raise_for_status(self_inner):
                return None
        return _R()


def test_extracts_arxiv_id_from_abs_url():
    backend = ArxivSourceBackend()
    assert backend._arxiv_id(_Paper(url="https://arxiv.org/abs/2401.01234")) == "2401.01234"
    assert backend._arxiv_id(_Paper(url="https://arxiv.org/abs/2401.01234v2")) == "2401.01234v2"
    assert backend._arxiv_id(_Paper(url="https://example.com/x")) is None


def test_can_handle_requires_arxiv_id():
    backend = ArxivSourceBackend()
    assert backend.can_handle(_Paper(url="https://arxiv.org/abs/2401.01234"), None)
    assert not backend.can_handle(_Paper(url="https://pubmed.gov/1"), None)


def test_fetch_parses_sections_from_html():
    backend = ArxivSourceBackend()
    http = _StubHttp(_FIXTURE.read_text())
    result = backend.fetch(_Paper(url="https://arxiv.org/abs/2401.01234"), http, None)
    assert result.text_source == "arxiv_html"
    labels = [s.label for s in result.sections]
    assert any("Introduction" in (l or "") for l in labels)
    assert any("Methods" in (l or "") for l in labels)
    assert "CREB" in result.full_text
    assert "arxiv.org/html/2401.01234" in http.requested[0]
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_arxiv.py -v`
Expected: FAIL — `cannot import name 'ArxivSourceBackend'`.

- [ ] **Step 4: Implement `ArxivSourceBackend`**

Add to `src/neurodb/full_text_client.py` (and add `from html.parser import HTMLParser` and `import re` already present at top):

```python
_ARXIV_ID_RE = re.compile(r"arxiv\.org/(?:abs|pdf|html)/([0-9]{4}\.[0-9]{4,5}(?:v[0-9]+)?)")


class _SectionHTMLParser(HTMLParser):
    """Collect (heading, text) blocks from arXiv-style HTML."""

    def __init__(self):
        super().__init__()
        self.blocks: list[tuple[str | None, str]] = []
        self._label: str | None = None
        self._buf: list[str] = []
        self._in_heading = False
        self._heading: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("h1", "h2", "h3"):
            if self._buf:
                self.blocks.append((self._label, " ".join(self._buf).strip()))
                self._buf = []
            self._in_heading = True
            self._heading = []

    def handle_endtag(self, tag):
        if tag in ("h1", "h2", "h3") and self._in_heading:
            self._in_heading = False
            self._label = " ".join(self._heading).strip() or None

    def handle_data(self, data):
        if self._in_heading:
            self._heading.append(data)
        elif data.strip():
            self._buf.append(data.strip())

    def close(self):
        super().close()
        if self._buf:
            self.blocks.append((self._label, " ".join(self._buf).strip()))


class ArxivSourceBackend:
    name = "arxiv"

    def _arxiv_id(self, paper) -> str | None:
        for value in (getattr(paper, "url", None), getattr(paper, "doi", None)):
            if not value:
                continue
            m = _ARXIV_ID_RE.search(value)
            if m:
                return m.group(1)
        return None

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        return self._arxiv_id(paper) is not None

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        arxiv_id = self._arxiv_id(paper)
        if not arxiv_id:
            return None
        resp = http.get(f"https://arxiv.org/html/{arxiv_id}")
        resp.raise_for_status()
        parser = _SectionHTMLParser()
        parser.feed(resp.text)
        parser.close()
        if not parser.blocks:
            return None
        sections, full_text = sections_from_labeled_blocks(parser.blocks)
        if not sections:
            return None
        return FullTextResult("arxiv_html", sections, full_text)
```

Add the imports at the top of the module:

```python
from html.parser import HTMLParser
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_arxiv.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_arxiv.py tests/fixtures/full_text/arxiv_sample.html
git commit -m "feat: arXiv HTML full-text backend (Phase 2a)"
```

---

## Task 6: `PmcJatsBackend`

**Files:**
- Modify: `src/neurodb/full_text_client.py`
- Create fixture: `tests/fixtures/full_text/jats_sample.xml`
- Test: `tests/unit/test_full_text_pmc.py`

- [ ] **Step 1: Create the fixture**

Create `tests/fixtures/full_text/jats_sample.xml`:

```xml
<article><body>
<sec><title>Introduction</title><p>Memory consolidation depends on the hippocampus.</p></sec>
<sec><title>Results</title><p>Sharp-wave ripples increased after learning.</p></sec>
</body></article>
```

- [ ] **Step 2: Write the failing test**

Create `tests/unit/test_full_text_pmc.py`:

```python
from pathlib import Path

from neurodb.full_text_client import PmcJatsBackend, parse_jats

_FIXTURE = Path(__file__).parent.parent / "fixtures" / "full_text" / "jats_sample.xml"


def test_parse_jats_yields_titled_sections():
    sections, full_text = parse_jats(_FIXTURE.read_text())
    labels = [s.label for s in sections]
    assert labels == ["Introduction", "Results"]
    assert "hippocampus" in full_text
    for s in sections:
        assert full_text[s.char_start : s.char_end] == s.text


def test_backend_returns_jats_source():
    backend = PmcJatsBackend()
    result = backend._result_from_jats(_FIXTURE.read_text())
    assert result.text_source == "jats"
    assert len(result.sections) == 2
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_pmc.py -v`
Expected: FAIL — `cannot import name 'PmcJatsBackend'`.

- [ ] **Step 4: Implement `parse_jats` + `PmcJatsBackend`**

Add to `src/neurodb/full_text_client.py` (add `import xml.etree.ElementTree as ET` at top):

```python
def parse_jats(xml_text: str) -> tuple[list[Section], str]:
    """Extract <sec><title>+text from JATS XML into offset-correct Sections."""
    root = ET.fromstring(xml_text)
    blocks: list[tuple[str | None, str]] = []
    for sec in root.iter("sec"):
        title_el = sec.find("title")
        label = (title_el.text or "").strip() if title_el is not None else None
        texts = [t.strip() for t in sec.itertext() if t.strip()]
        # drop the title text (first item) from the body if present
        body = " ".join(texts[1:] if label and texts and texts[0] == label else texts)
        blocks.append((label, body))
    return sections_from_labeled_blocks(blocks)


class PmcJatsBackend:
    name = "pmc"

    def _pmcid(self, paper, http) -> str | None:
        # Resolve a PMCID via the NCBI ID converter from a PMID or DOI in url/doi.
        ident = None
        for value in (getattr(paper, "doi", None), getattr(paper, "url", None)):
            if value and ("PMC" in value or "/pmc/" in value):
                m = re.search(r"PMC[0-9]+", value)
                if m:
                    return m.group(0)
            if value:
                ident = ident or value
        if not ident:
            return None
        resp = http.get(
            "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/",
            params={"ids": ident, "format": "json", "tool": "neurodb"},
        )
        resp.raise_for_status()
        records = resp.json().get("records", [])
        if records and records[0].get("pmcid"):
            return records[0]["pmcid"]
        return None

    def can_handle(self, paper, supplied: SuppliedInput | None) -> bool:
        for value in (getattr(paper, "doi", None), getattr(paper, "url", None)):
            if value:
                return True
        return False

    def _result_from_jats(self, xml_text: str) -> FullTextResult | None:
        sections, full_text = parse_jats(xml_text)
        if not sections:
            return None
        return FullTextResult("jats", sections, full_text)

    def fetch(self, paper, http, supplied: SuppliedInput | None) -> FullTextResult | None:
        pmcid = self._pmcid(paper, http)
        if not pmcid:
            return None
        resp = http.get(
            "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi",
            params={"db": "pmc", "id": pmcid.replace("PMC", ""), "rettype": "full",
                    "retmode": "xml", "tool": "neurodb"},
        )
        resp.raise_for_status()
        return self._result_from_jats(resp.text)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_pmc.py -v`
Expected: PASS (2 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_pmc.py tests/fixtures/full_text/jats_sample.xml
git commit -m "feat: PMC JATS full-text backend (Phase 2a)"
```

---

## Task 7: `acquire` orchestrator + content-type routing (reject path)

**Files:**
- Modify: `src/neurodb/full_text_client.py`
- Test: `tests/unit/test_full_text_acquire.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_full_text_acquire.py`:

```python
from neurodb.full_text_client import AcquireFailure, FullTextResult, SuppliedInput, acquire


class _Paper:
    def __init__(self, url=None, doi=None):
        self.url = url
        self.doi = doi


class _Resp:
    def __init__(self, body="", headers=None, status=200):
        self.text = body
        self.headers = headers or {}
        self.status_code = status

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp):
        self._resp = resp

    def get(self, url, **kw):
        return self._resp


def test_user_supplied_text_wins():
    result = acquire(_Paper(), http=None, supplied=SuppliedInput(text="hello", format="txt"))
    assert isinstance(result, FullTextResult)
    assert result.text_source == "user_supplied"


def test_generic_html_url_is_rejected_to_phase2b():
    http = _Http(_Resp(body="<html>...</html>", headers={"Content-Type": "text/html"}))
    result = acquire(_Paper(url="https://journal.example/article/1"), http=http, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "needs_parser_phase2b"


def test_pdf_url_is_rejected_to_phase2b():
    http = _Http(_Resp(headers={"Content-Type": "application/pdf"}))
    result = acquire(_Paper(url="https://x/y.pdf"), http=http, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "needs_parser_phase2b"


def test_no_source_returns_unavailable():
    result = acquire(_Paper(), http=None, supplied=None)
    assert isinstance(result, AcquireFailure)
    assert result.reason == "no_source"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_acquire.py -v`
Expected: FAIL — `cannot import name 'acquire'`.

- [ ] **Step 3: Implement the orchestrator**

Add to `src/neurodb/full_text_client.py`:

```python
FULL_TEXT_BACKENDS: list[FullTextBackend] = [
    UserSuppliedBackend(),
    ArxivSourceBackend(),
    PmcJatsBackend(),
]


def acquire(paper, http, supplied: SuppliedInput | None = None):
    """Return a FullTextResult on success, else an AcquireFailure (never raises for routing)."""
    # 1) explicit user-supplied text
    if supplied and supplied.text and supplied.text.strip():
        return UserSuppliedBackend().fetch(paper, http, supplied) or AcquireFailure(
            "failed", "fetch_error", "Supplied text could not be parsed."
        )

    # 2) structured backends keyed off identifiers
    for backend in (ArxivSourceBackend(), PmcJatsBackend()):
        if backend.can_handle(paper, supplied):
            try:
                result = backend.fetch(paper, http, supplied)
            except Exception as exc:  # network/parse failure for this backend
                return AcquireFailure("failed", "fetch_error", f"{type(exc).__name__}: {exc}")
            if result:
                return result
            # PMC resolved but not OA / no JATS body
            if backend.name == "pmc":
                return AcquireFailure(
                    "unavailable", "not_oa",
                    "No open-access full text available for this source.",
                )

    # 3) raw URL content-type sniff
    candidate = (supplied.url if supplied else None) or getattr(paper, "url", None)
    if candidate and http is not None:
        try:
            resp = http.get(candidate)
            resp.raise_for_status()
        except Exception as exc:
            return AcquireFailure("failed", "fetch_error", f"{type(exc).__name__}: {exc}")
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "text/plain" in ctype or "text/markdown" in ctype:
            fmt = "md" if "markdown" in ctype else "txt"
            return UserSuppliedBackend().fetch(
                paper, http, SuppliedInput(text=resp.text, format=fmt)
            ) or AcquireFailure("failed", "fetch_error", "Empty document.")
        if "xml" in ctype:
            return PmcJatsBackend()._result_from_jats(resp.text) or AcquireFailure(
                "failed", "fetch_error", "Empty JATS document."
            )
        if "html" in ctype or "pdf" in ctype:
            return AcquireFailure(
                "unavailable", "needs_parser_phase2b",
                "This looks like a publisher HTML/PDF page — full-text capture for "
                "those arrives in Phase 2b. Paste the text or supply a .txt/.md/JATS file.",
            )

    return AcquireFailure("unavailable", "no_source", "No structured full-text source found.")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_acquire.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/full_text_client.py tests/unit/test_full_text_acquire.py
git commit -m "feat: full-text acquire orchestrator with content-type routing (Phase 2a)"
```

---

## Task 8: `ChunkStore` over `knowledge_chunks`

**Files:**
- Create: `src/neurodb/chunk_store.py`
- Test: `tests/unit/test_chunk_store.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_chunk_store.py`:

```python
import uuid

import chromadb

from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk


class _StubEmbedder:
    def embed(self, texts):
        # deterministic: vector keyed off whether "hippocampus" appears
        return [[1.0, 0.0] if "hippocampus" in t else [0.0, 1.0] for t in texts]


def _store():
    return ChunkStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"chunks_{uuid.uuid4().hex}",
    )


def _chunks():
    return [
        Chunk(0, "the hippocampus consolidates memory", "Intro", 0, 35),
        Chunk(1, "unrelated cerebellum text", "Methods", 36, 61),
    ]


def test_add_and_search_returns_provenance():
    store = _store()
    store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                     text_source="jats", chunks=_chunks())
    hits = store.search("hippocampus", n=1, min_score=0.0)
    assert hits[0]["text"].startswith("the hippocampus")
    assert hits[0]["section"] == "Intro"
    assert hits[0]["source_id"] == 5
    assert hits[0]["char_start"] == 0


def test_below_threshold_returns_empty():
    store = _store()
    store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                     text_source="jats", chunks=_chunks())
    # impossible threshold → honest absence
    assert store.search("hippocampus", n=1, min_score=2.0) == []


def test_reacquire_is_idempotent():
    store = _store()
    for _ in range(2):
        store.delete_paper(5)
        store.add_chunks(paper_id=5, title="T", year=2024, currency_status="current",
                         text_source="jats", chunks=_chunks())
    hits = store.search("hippocampus", n=10, min_score=0.0)
    assert len([h for h in hits if h["source_id"] == 5]) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_chunk_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.chunk_store'`.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/chunk_store.py`:

```python
"""Second Chroma collection holding quotable full-text chunks (Phase 2a)."""
from __future__ import annotations

import chromadb

from neurodb.chunking import Chunk

CHUNK_COLLECTION_NAME = "knowledge_chunks"


class ChunkStore:
    """Semantic index of full-text chunks; only full_text-tier papers live here."""

    def __init__(self, path=None, client=None, embedder=None,
                 collection_name: str = CHUNK_COLLECTION_NAME) -> None:
        if client is not None:
            self._client = client
        elif path is not None:
            self._client = chromadb.PersistentClient(path=path)
        else:
            raise ValueError("Either path or client must be provided")
        self._embedder = embedder
        self._collection = self._client.get_or_create_collection(
            name=collection_name, metadata={"hnsw:space": "cosine"},
        )

    def _chunk_id(self, paper_id: int, chunk_index: int) -> str:
        return f"chunk:{paper_id}:{chunk_index}"

    def add_chunks(self, *, paper_id: int, title: str, year: int | None,
                   currency_status: str, text_source: str, chunks: list[Chunk]) -> list[str]:
        if not chunks:
            return []
        ids = [self._chunk_id(paper_id, c.chunk_index) for c in chunks]
        documents = [c.text for c in chunks]
        metadatas = [
            {
                "source_id": str(paper_id),
                "paper_id": str(paper_id),
                "chunk_index": c.chunk_index,
                "section": c.section or "",
                "char_start": c.char_start if c.char_start is not None else -1,
                "char_end": c.char_end if c.char_end is not None else -1,
                "text_source": text_source,
                "title": title,
                "year": str(year) if year else "",
                "currency_status": currency_status,
                "data_tier": "full_text",
            }
            for c in chunks
        ]
        kwargs = {"ids": ids, "documents": documents, "metadatas": metadatas}
        if self._embedder is not None:
            kwargs["embeddings"] = self._embedder.embed(documents)
        self._collection.upsert(**kwargs)
        return ids

    def delete_paper(self, paper_id: int) -> None:
        try:
            self._collection.delete(where={"paper_id": str(paper_id)})
        except Exception:
            pass

    def search(self, query: str, n: int = 5, min_score: float = 0.0) -> list[dict]:
        if not query:
            return []
        count = self._collection.count()
        if count == 0:
            return []
        kwargs = {"n_results": min(n, count)}
        if self._embedder is not None:
            kwargs["query_embeddings"] = [self._embedder.embed([query])[0]]
        else:
            kwargs["query_texts"] = [query]
        res = self._collection.query(**kwargs)
        if not res["ids"]:
            return []
        out = []
        for i, doc_id in enumerate(res["ids"][0]):
            meta = res["metadatas"][0][i]
            distance = res["distances"][0][i]
            score = 1.0 - distance  # cosine distance → similarity
            if score < min_score:
                continue
            out.append({
                "chunk_id": doc_id,
                "text": res["documents"][0][i],
                "source_id": int(meta.get("source_id") or 0),
                "title": meta.get("title", ""),
                "section": meta.get("section") or None,
                "char_start": meta.get("char_start"),
                "char_end": meta.get("char_end"),
                "text_source": meta.get("text_source", ""),
                "year": meta.get("year") or "",
                "currency_status": meta.get("currency_status", "current"),
                "score": score,
            })
        return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_chunk_store.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chunk_store.py tests/unit/test_chunk_store.py
git commit -m "feat: ChunkStore over knowledge_chunks with relevance threshold (Phase 2a)"
```

---

## Task 9: `quote_verify.py` — verification + ledger backstop (pure)

**Files:**
- Create: `src/neurodb/quote_verify.py`
- Test: `tests/unit/test_quote_verify.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_quote_verify.py`:

```python
from neurodb.quote_verify import (
    LedgerEntry,
    build_quote_ledger,
    normalize_quote,
    reconcile_quotes,
    verify_quote,
)


def test_normalize_collapses_whitespace_and_dashes():
    assert normalize_quote("the  hippo\ncampus—works") == "the hippocampus-works"


def test_verify_matches_substring_of_chunk():
    chunks = [{"chunk_id": "c1", "text": "The hippocampus consolidates memory.",
               "section": "Intro", "char_start": 0, "char_end": 36}]
    m = verify_quote("hippocampus consolidates", chunks)
    assert m is not None and m["chunk_id"] == "c1"


def test_verify_rejects_absent_text():
    chunks = [{"chunk_id": "c1", "text": "The hippocampus.", "section": None,
               "char_start": 0, "char_end": 16}]
    assert verify_quote("the cerebellum coordinates movement", chunks) is None


def test_build_ledger_from_messages():
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "verify_quote",
             "input": {"text": "hippocampus consolidates"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": '{"matched": true, "chunk_id": "c1"}'}]},
    ]
    ledger = build_quote_ledger(messages)
    assert ledger == [LedgerEntry(quoted_text="hippocampus consolidates", matched=True)]


def test_reconcile_flags_unverified_quote():
    ledger = [LedgerEntry("hippocampus consolidates", True)]
    answer = 'It says "hippocampus consolidates memory" and also "the cerebellum is unrelated here".'
    warnings = reconcile_quotes(answer, ledger, min_quote_chars=10)
    # the first quote contains a verified substring; the second has no matched entry
    assert any("cerebellum is unrelated" in w for w in warnings)
    assert not any("hippocampus consolidates memory" in w for w in warnings)


def test_reconcile_flags_false_positive():
    ledger = [LedgerEntry("hippocampus consolidates", False)]
    answer = 'Quote: "hippocampus consolidates strongly here".'
    warnings = reconcile_quotes(answer, ledger, min_quote_chars=10)
    assert len(warnings) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_quote_verify.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.quote_verify'`.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/quote_verify.py`:

```python
"""Fail-closed quote verification + end-of-turn ledger backstop (Phase 2a, invariant #4)."""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

_WS = re.compile(r"\s+")
_DASHES = re.compile(r"[‐-―−]")  # hyphens/dashes/minus → "-"
_QUOTE_SPAN = re.compile(r"[\"“]([^\"”]+)[\"”]")


def normalize_quote(text: str) -> str:
    text = _DASHES.sub("-", text)
    return _WS.sub(" ", text).strip()


def verify_quote(text: str, chunks: list[dict]) -> dict | None:
    """Return a match descriptor if the (normalized) text is a substring of some chunk."""
    needle = normalize_quote(text)
    if not needle:
        return None
    for c in chunks:
        if needle in normalize_quote(c["text"]):
            return {
                "matched": True,
                "chunk_id": c.get("chunk_id"),
                "section": c.get("section"),
                "char_start": c.get("char_start"),
                "char_end": c.get("char_end"),
            }
    return None


@dataclass
class LedgerEntry:
    quoted_text: str
    matched: bool


def build_quote_ledger(messages: list[dict]) -> list[LedgerEntry]:
    """Extract verify_quote calls + their matched results from the turn's messages."""
    pending: dict[str, str] = {}  # tool_use_id -> quoted text
    results: dict[str, bool] = {}
    for msg in messages:
        content = msg.get("content")
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict):
                continue
            if block.get("type") == "tool_use" and block.get("name") == "verify_quote":
                pending[block.get("id")] = (block.get("input") or {}).get("text", "")
            elif block.get("type") == "tool_result":
                tid = block.get("tool_use_id")
                if tid in pending:
                    raw = block.get("content")
                    text = raw if isinstance(raw, str) else json.dumps(raw)
                    try:
                        results[tid] = bool(json.loads(text).get("matched"))
                    except Exception:
                        results[tid] = False
    return [LedgerEntry(pending[tid], results.get(tid, False)) for tid in pending]


def reconcile_quotes(answer_text: str, ledger: list[LedgerEntry],
                     *, min_quote_chars: int = 25) -> list[str]:
    """Return a warning per quoted span not backed by a matched verify_quote entry."""
    verified = [normalize_quote(e.quoted_text) for e in ledger if e.matched]
    warnings: list[str] = []
    for span in _QUOTE_SPAN.findall(answer_text):
        if len(span) < min_quote_chars:
            continue
        norm = normalize_quote(span)
        if any(v and (v in norm or norm in v) for v in verified):
            continue
        warnings.append(
            f'⚠ The quoted text "{span.strip()}" was not verified against a stored source.'
        )
    return warnings
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_quote_verify.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/quote_verify.py tests/unit/test_quote_verify.py
git commit -m "feat: fail-closed quote verification + ledger reconciliation (Phase 2a)"
```

---

## Task 10: `full_text_tools.py` — shared tool defs + executors

**Files:**
- Create: `src/neurodb/agents/full_text_tools.py`
- Test: `tests/unit/test_full_text_tools.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_full_text_tools.py`:

```python
import json
import uuid

import chromadb

from neurodb.agents.full_text_tools import (
    FULL_TEXT_TOOLS,
    execute_search_full_text,
    execute_verify_quote,
)
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk


class _StubEmbedder:
    def embed(self, texts):
        return [[1.0, 0.0] if "hippocampus" in t else [0.0, 1.0] for t in texts]


def _store():
    s = ChunkStore(client=chromadb.EphemeralClient(), embedder=_StubEmbedder(),
                   collection_name=f"chunks_{uuid.uuid4().hex}")
    s.add_chunks(paper_id=9, title="Ripples", year=2024, currency_status="current",
                 text_source="jats",
                 chunks=[Chunk(0, "the hippocampus consolidates memory", "Intro", 0, 35)])
    return s


def test_tool_names_present():
    names = {t["name"] for t in FULL_TEXT_TOOLS}
    assert names == {"search_full_text", "verify_quote"}


def test_search_returns_grounded_passage():
    out = json.loads(execute_search_full_text(_store(), {"query": "hippocampus"}, min_score=0.0))
    assert out["grounded"] is True
    assert out["passages"][0]["section"] == "Intro"


def test_search_below_threshold_is_honest_absence():
    out = json.loads(execute_search_full_text(_store(), {"query": "hippocampus"}, min_score=2.0))
    assert out["grounded"] is False


def test_verify_quote_matches_stored_chunk():
    out = json.loads(execute_verify_quote(_store(), {"text": "hippocampus consolidates", "source_id": 9}))
    assert out["matched"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_full_text_tools.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.agents.full_text_tools'`.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/agents/full_text_tools.py`:

```python
"""Shared full-text quoting tools (registered on tutor + research agents)."""
from __future__ import annotations

import json

from neurodb.quote_verify import verify_quote

FULL_TEXT_TOOLS = [
    {
        "name": "search_full_text",
        "description": (
            "Search stored full text of acquired papers and return verbatim, "
            "provenance-anchored passages eligible for quoting. Returns "
            "{grounded: false} when nothing clears the relevance threshold — "
            "say so rather than inventing a quote."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "What to find in full text."},
                "n_results": {"type": "integer", "description": "Max passages."},
            },
            "required": ["query"],
        },
    },
    {
        "name": "verify_quote",
        "description": (
            "Verify a verbatim quote against the stored full text of a source before "
            "presenting it. Returns {matched: true, ...provenance} or {matched: false}. "
            "A quote may be tagged [verified] ONLY after this returns matched=true."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The exact text to verify."},
                "source_id": {"type": "integer", "description": "The paper/source id."},
            },
            "required": ["text", "source_id"],
        },
    },
]

DEFAULT_MIN_SCORE = 0.25


def execute_search_full_text(chunk_store, inputs: dict, *, min_score: float = DEFAULT_MIN_SCORE) -> str:
    if chunk_store is None:
        return json.dumps({"grounded": False, "message": "Full-text store not available."})
    passages = chunk_store.search(
        inputs["query"], n=inputs.get("n_results", 5), min_score=min_score
    )
    if not passages:
        return json.dumps({
            "grounded": False,
            "message": "No grounded full-text support for that query.",
        })
    return json.dumps({"grounded": True, "passages": passages})


def execute_verify_quote(chunk_store, inputs: dict, *, min_score: float = 0.0) -> str:
    if chunk_store is None:
        return json.dumps({"matched": False, "message": "Full-text store not available."})
    source_id = int(inputs["source_id"])
    # pull this source's chunks back out of the store for exact matching
    passages = chunk_store.search(inputs["text"], n=20, min_score=-1.0)
    chunks = [p for p in passages if p["source_id"] == source_id]
    match = verify_quote(inputs["text"], chunks)
    return json.dumps(match or {"matched": False})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_full_text_tools.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/full_text_tools.py tests/unit/test_full_text_tools.py
git commit -m "feat: shared search_full_text + verify_quote agent tools (Phase 2a)"
```

> Note: `execute_verify_quote` matches against the chunk store. If retrieval recall proves insufficient for exact verification, switch it to read `paper_chunks` rows directly by `paper_id` (DB exact text) — see spec §12. Keep the store-based path unless a test exposes a miss.

---

## Task 11: Wire tools into both agents (registration, dispatch, prompt contract)

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py` (imports; `__init__` to accept `chunk_store`; `_get_active_tools`; `_execute_tool_block`; `_TUTOR_SYSTEM_PROMPT` contract)
- Modify: `src/neurodb/agents/research_agent.py` (parallel changes)
- Modify: `src/neurodb/api/routes/chat.py` (pass `chunk_store` into agents)
- Test: `tests/unit/test_tutor_agent.py`, `tests/unit/test_research_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tutor_agent.py`:

```python
def test_full_text_tools_registered():
    agent = _agent()
    names = {t["name"] for t in agent._get_active_tools()}
    assert {"search_full_text", "verify_quote"} <= names


def test_prompt_states_quote_verification_contract():
    agent = _agent()
    prompt = agent._build_system_prompt().lower()
    assert "search_full_text" in prompt
    assert "verify_quote" in prompt
    assert "unverified" in prompt
```

(Use the existing `_agent()` factory in that test module; if it does not pass `chunk_store`, the default `None` is fine for these assertions.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_tutor_agent.py -k "full_text_tools_registered or quote_verification_contract" -v`
Expected: FAIL — tools not registered; prompt lacks the contract.

- [ ] **Step 3: Register tools + dispatch + prompt in the tutor agent**

In `src/neurodb/agents/tutor_agent.py` imports, add:

```python
from neurodb.agents.full_text_tools import (
    FULL_TEXT_TOOLS,
    execute_search_full_text,
    execute_verify_quote,
)
```

In `NeuroTutorAgent.__init__`, accept and store a `chunk_store` (add `chunk_store=None` to the signature and, with the other store assignments, `self._chunk_store = chunk_store`).

In `_get_active_tools`, add `+ list(FULL_TEXT_TOOLS)` to the returned concatenation.

In `_execute_tool_block`, before the final `return execute_tool(...)`, add:

```python
        if block.tool_name == "search_full_text":
            return execute_search_full_text(self._chunk_store, block.tool_input)
        if block.tool_name == "verify_quote":
            return execute_verify_quote(self._chunk_store, block.tool_input)
```

Append the contract to `_TUTOR_SYSTEM_PROMPT` (extend the final string literal):

```python
    "When the user wants a quotation, specific claim, figure, or method from a paper, "
    "call search_full_text and quote ONLY text it returns, rendering each quote with its "
    "source title and section. If search_full_text returns grounded=false, say you have no "
    "grounded full-text support rather than quoting from memory. Before presenting any "
    "verbatim quote, call verify_quote with the exact text and source_id; tag a quote "
    "[verified: Title section] ONLY after verify_quote returns matched=true. Any quoted "
    "text you did not or could not verify must be tagged [unverified — from memory]. "
    "Verified is earned from the tool result, never asserted on your own."
```

- [ ] **Step 4: Apply the parallel changes to the research agent**

In `src/neurodb/agents/research_agent.py`: add the same `full_text_tools` import; accept/store `chunk_store` in `__init__`; add `+ list(FULL_TEXT_TOOLS)` to its active-tools method; add the same two dispatch branches; append the same quoting contract to its system prompt string. (Match that file's existing naming for the tools method and prompt constant.)

- [ ] **Step 5: Pass `chunk_store` into agents at construction**

In `src/neurodb/api/routes/chat.py`, at each `NeuroTutorAgent(...)` / `NeuroResearchAgent(...)` construction that already passes `knowledge_store=...`, add `chunk_store=chunk_store,` and obtain `chunk_store` from the request stores (Task 12 adds `get_chunk_store`; here read it from `stores["chunk_store"]` or the dependency you wire in Task 12). For the research path using `get_research_stores`, add `"chunk_store": request.app.state.chunk_store` to that dict in `deps.py` in Task 12 and read it here.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_tutor_agent.py tests/unit/test_research_agent.py -k "full_text or quote_verification or contract" -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py src/neurodb/agents/research_agent.py src/neurodb/api/routes/chat.py tests/unit/test_tutor_agent.py tests/unit/test_research_agent.py
git commit -m "feat: register full-text tools + quote contract on both agents (Phase 2a)"
```

---

## Task 12: End-of-turn ledger backstop in the agent loop

**Files:**
- Modify: `src/neurodb/agents/base.py` (add `_append_quote_warnings`; call it at the `end_turn` emit points in `_chat_inner` and `_chat_stream_inner`)
- Modify: `src/neurodb/api/app.py` (build + register `chunk_store`)
- Modify: `src/neurodb/api/deps.py` (`get_chunk_store`; add to `get_research_stores`)
- Test: `tests/unit/test_agent.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_agent.py`:

```python
from neurodb.agents.base import BaseAgent


def test_append_quote_warnings_flags_unverified():
    messages = [
        {"role": "assistant", "content": [
            {"type": "tool_use", "id": "t1", "name": "verify_quote",
             "input": {"text": "hippocampus consolidates"}}]},
        {"role": "user", "content": [
            {"type": "tool_result", "tool_use_id": "t1",
             "content": '{"matched": true}'}]},
    ]
    answer = 'As stated, "the cerebellum coordinates movement precisely here".'
    out = BaseAgent._append_quote_warnings(answer, messages)
    assert "⚠" in out and "cerebellum coordinates movement" in out


def test_append_quote_warnings_noop_without_quotes():
    out = BaseAgent._append_quote_warnings("No quotes at all here.", [])
    assert out == "No quotes at all here."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_agent.py -k "append_quote_warnings" -v`
Expected: FAIL — `_append_quote_warnings` not defined.

- [ ] **Step 3: Implement the backstop helper**

In `src/neurodb/agents/base.py`, add this `@staticmethod` to `BaseAgent`:

```python
    @staticmethod
    def _append_quote_warnings(answer_text: str, messages: list[dict]) -> str:
        from neurodb.quote_verify import build_quote_ledger, reconcile_quotes

        ledger = build_quote_ledger(messages)
        warnings = reconcile_quotes(answer_text, ledger)
        if not warnings:
            return answer_text
        return answer_text + "\n\n" + "\n".join(warnings)
```

- [ ] **Step 4: Apply the helper at the end-of-turn emit points**

In `_chat_inner` (the non-streaming path), the `end_turn` branch currently yields the assistant text blocks (around line 109-114). Accumulate that text and append warnings once at the end:

```python
            if response.stop_reason == "end_turn":
                messages.append({"role": "assistant", "content": _blocks_to_dicts(response.content)})
                answer = "".join(
                    block.text for block in response.content if block.type == "text"
                )
                yield self._append_quote_warnings(answer, messages)
                return
```

In `_chat_stream_inner` (the streaming path), the deltas are streamed incrementally; emit the warnings as a trailing event after the `end_turn` block (around line 224-235), so they render after the answer:

```python
                # after streaming the answer text for this end_turn:
                warnings = self._append_quote_warnings("".join(_streamed_text), messages)[len("".join(_streamed_text)):]
                if warnings.strip():
                    yield {"type": "delta", "text": warnings}
                yield { ... existing done event ... }
```

Where `_streamed_text` is the list you already accumulate for the streamed answer; if the streaming path does not currently accumulate the answer text, add a local `_streamed_text: list[str] = []` and append each emitted text delta to it within that branch. Keep the existing `done` event untouched.

- [ ] **Step 5: Build + register `chunk_store` and the dependency**

In `src/neurodb/api/app.py`, after `knowledge_store = KnowledgeLibraryStore(path=chroma_path, embedder=embedder)` (line ~87), add:

```python
    from neurodb.chunk_store import ChunkStore
    chunk_store = ChunkStore(path=chroma_path, embedder=embedder)
```

Add a `chunk_store=None` parameter to the app factory signature (next to `knowledge_store=None`, line ~15), set `app.state.chunk_store = chunk_store` (next to line ~23), and pass `chunk_store=chunk_store` where the factory is invoked at startup.

In `src/neurodb/api/deps.py`, add:

```python
def get_chunk_store(request: Request):
    return request.app.state.chunk_store
```

and add `"chunk_store": request.app.state.chunk_store,` to the dict returned by `get_research_stores`.

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_agent.py -k "append_quote_warnings" -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/base.py src/neurodb/api/app.py src/neurodb/api/deps.py tests/unit/test_agent.py
git commit -m "feat: end-of-turn quote-warning backstop + chunk_store wiring (Phase 2a)"
```

---

## Task 13: `acquire-full-text` API route + schema + React surface

**Files:**
- Modify: `src/neurodb/api/schemas/knowledge_library.py` (`PaperItem.full_text_status`/`text_source`)
- Modify: `src/neurodb/api/routes/knowledge_library.py` (new route)
- Modify: frontend Knowledge Library component
- Test: `tests/unit/test_api_knowledge_library.py`, frontend test

- [ ] **Step 1: Write the failing API test**

Append to `tests/unit/test_api_knowledge_library.py` (follow the module's existing TestClient/app fixture pattern):

```python
def test_acquire_full_text_user_supplied(client, approved_paper_id):
    resp = client.post(
        f"/api/knowledge-library/{approved_paper_id}/acquire-full-text",
        json={"text": "# Intro\nThe dentate gyrus supports pattern separation.", "format": "md"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_text_status"] == "verified"
    assert body["data_tier"] == "full_text"


def test_acquire_full_text_generic_html_is_unavailable(client, approved_paper_with_html_url):
    resp = client.post(
        f"/api/knowledge-library/{approved_paper_with_html_url}/acquire-full-text",
        json={},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["full_text_status"] == "unavailable"
    assert body["data_tier"] != "full_text"
```

(Reuse or add small fixtures `approved_paper_id` / `approved_paper_with_html_url` mirroring existing approve-flow fixtures in that file; the HTML case can inject a stub http client returning `Content-Type: text/html`.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py -k "acquire_full_text" -v`
Expected: FAIL — route not found (404).

- [ ] **Step 3: Add the schema fields**

In `src/neurodb/api/schemas/knowledge_library.py`, in `class PaperItem` after `currency_status`, add:

```python
    full_text_status: str | None = None
    text_source: str | None = None
```

- [ ] **Step 4: Implement the route**

In `src/neurodb/api/routes/knowledge_library.py`, add imports:

```python
import httpx

from neurodb.api.deps import get_chunk_store
from neurodb.chunking import chunk_sections
from neurodb.full_text_client import AcquireFailure, SuppliedInput, acquire
from neurodb.schema import PaperChunk
```

Add a request model near the top (after `DuplicateCheckResponse`):

```python
class AcquireFullTextRequest(BaseModel):
    url: str | None = None
    text: str | None = None
    format: str | None = None
```

Add the route:

```python
@router.post("/{source_id}/acquire-full-text", response_model=PaperItem)
def acquire_full_text(
    source_id: int,
    body: AcquireFullTextRequest | None = None,
    engine: Engine = Depends(get_engine),
    chunk_store=Depends(get_chunk_store),
) -> PaperItem:
    body = body or AcquireFullTextRequest()
    supplied = SuppliedInput(url=body.url, text=body.text, format=body.format)
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        if paper is None:
            raise HTTPException(status_code=404, detail="Source not found")
        if paper.status != "approved":
            raise HTTPException(status_code=400, detail="Approve the source first")

    with httpx.Client(timeout=20.0, follow_redirects=True) as http:
        result = acquire(paper, http, supplied)

    warnings: list[str] = []
    if isinstance(result, AcquireFailure):
        _update_paper_fields(source_id, engine, full_text_status=result.status)
        warnings.append(result.message)
    else:
        chunks = chunk_sections(result.sections)
        chunk_store.delete_paper(source_id)
        chunk_store.add_chunks(
            paper_id=source_id, title=paper.title, year=paper.year,
            currency_status=paper.currency_status, text_source=result.text_source,
            chunks=chunks,
        )
        created_at = datetime.now(UTC).isoformat()
        with get_session(engine) as session:
            session.query(PaperChunk).filter(PaperChunk.paper_id == source_id).delete()
            for c in chunks:
                session.add(PaperChunk(
                    paper_id=source_id, chunk_index=c.chunk_index, text=c.text,
                    section=c.section, char_start=c.char_start, char_end=c.char_end,
                    text_source=result.text_source,
                    chroma_id=f"chunk:{source_id}:{c.chunk_index}", created_at=created_at,
                ))
        _update_paper_fields(
            source_id, engine, full_text_status="verified",
            text_source=result.text_source, data_tier="full_text",
        )
    item = _read_paper_item(source_id, engine)
    return item.model_copy(update={"warnings": warnings})
```

If `_update_paper_fields` does not yet accept `full_text_status`/`text_source`/`data_tier`, extend it to pass those columns through (it already updates arbitrary paper columns for status/chroma_id). Add a small `_read_paper_item(source_id, engine)` helper if one does not exist, mirroring `_paper_item_from_row`.

- [ ] **Step 5: Run API test to verify it passes**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py -k "acquire_full_text" -v`
Expected: PASS.

- [ ] **Step 6: Frontend — acquire button, tier badge, status**

First read the existing Knowledge Library component and its test to match conventions:

Run: `ls frontend/src && grep -rl "knowledge-library\|KnowledgeLibrary\|data_tier" frontend/src`

In that component:
- Render a **tier badge** from `paper.data_tier` (`full text` / `abstract` / `metadata`).
- Render `paper.full_text_status` (verified / unavailable / failed) when present.
- Add an **"Acquire full text"** button on approved papers that `POST`s to `/api/knowledge-library/{id}/acquire-full-text` (empty body for auto-resolve; with an optional text/URL input for user-supplied), shows a spinner while pending, and refreshes the row on completion; surface `warnings[0]` when status is `unavailable`.

Add/extend the component's vitest test to assert the button calls the endpoint and the badge reflects `data_tier`. Follow the existing test file's mocking pattern (e.g. `vi.fn()` fetch mock).

- [ ] **Step 7: Run frontend tests**

Run: `cd frontend && npm test -- --run` (or the repo's configured command).
Expected: PASS, build clean.

- [ ] **Step 8: Commit**

```bash
git add src/neurodb/api/schemas/knowledge_library.py src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library.py frontend/
git commit -m "feat: acquire-full-text route + Knowledge Library tier/status UI (Phase 2a)"
```

---

## Task 14: Full-suite verification + status sync

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Run the whole backend suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — no new failures beyond those tracked in `docs/testLog.md`.

- [ ] **Step 2: Lint the new/changed modules**

Run: `uv run ruff check src/neurodb/chunking.py src/neurodb/full_text_client.py src/neurodb/chunk_store.py src/neurodb/quote_verify.py src/neurodb/agents/full_text_tools.py src/neurodb/agents/base.py src/neurodb/agents/tutor_agent.py src/neurodb/agents/research_agent.py src/neurodb/api/routes/knowledge_library.py`
Expected: no new errors (pre-existing E501/UP in untouched code are out of scope).

- [ ] **Step 3: Update active focus + counts in projectStatus.md**

In `docs/projectStatus.md`, set `**Active focus:**` to note Phase 2a implemented behind migration 024 with manual verification pending via `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md`; update the backend test count in the relevant phase row.

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: mark citation-grade Phase 2a implemented, manual verification pending"
```

- [ ] **Step 5: Manual verification**

Execute `docs/testsPlans/manualTestPlan_citation_phase2a_fulltext.md` (T1–T8) against the running app. On sign-off, move the plan to the completed table in `projectStatus.md`.

---

## Notes / coordination

- **Embedder:** 2a uses whatever `embedder` `app.py` already injects into the stores (kept light/CPU per spec §9). No SPECTER2 change here.
- **Literature source registry overlap:** `full_text_client` is intentionally separate from the deferred `SourceBackend` *search* registry (spec decision (a)); it does not modify `literature_client.search()`. If the search registry later lands, converge `FullTextBackend.fetch` into it then.
- **Out of scope (Phase 2b/2c):** OA PDF + Docling parse gate, `page` anchors, the formal CI retrieval-eval harness, full automatic quote-correctness interception, retraction/version provenance, embedder upgrade.
- **Network in tests:** every backend test injects a stub/fixture http client — no live calls in the suite.
```
