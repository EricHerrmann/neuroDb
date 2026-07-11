# Knowledge Library Augmentation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Spec:** `docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md`

**Goal:** Full-text acquisition backfills bibliographic metadata (authors/abstract/year/DOI/URL), emits a `FullTextAcquired` event that reconciles the three stores (DuckDB `papers`, `knowledge_chunks`, `knowledge_library`), and an explicit "use the knowledge library" chat request deterministically searches the library and injects full-content results with a visible searched-library line.

**Architecture:** Three workstreams in spec order **#2 backfill → #3 event + reconciliation → #1 retrieval guarantee**. A `MetadataLookupClient` (Semantic Scholar by DOI, Crossref fallback, title fallback) feeds pure field-selection logic that writes only NULL `Paper` fields through the existing FK-safe updater. A tiny synchronous in-process event emitter (`src/neurodb/events.py`) dispatches `full_text_acquired` from one shared post-acquisition hook used by all three acquisition paths; a reconciliation handler re-syncs `data_tier`/`authors`/`year`/`currency_status` into both Chroma indexes via metadata-only updates (no re-embedding) and writes an `event_log` audit row. The chat route runs a deterministic library search on directive-flagged turns, appends a mandatory full-content block to the context bundle's `prompt_block`, and yields a `library_search` SSE event the React UI renders as a notice.

**Tech Stack:** Python 3 / FastAPI / SQLAlchemy / DuckDB / ChromaDB / httpx / pytest; React + Vitest for the one frontend task.

## Global Constraints

- Test command: `uv run pytest tests/ -q`. Pass criteria everywhere: **no new failures beyond those already tracked in `docs/testLog.md`**.
- **All writes to `papers` rows go through `_update_paper_fields` in `src/neurodb/api/routes/knowledge_library.py`.** DuckDB rejects UPDATE on any column of an FK-referenced row; that helper detaches/restores the FK children. Never `setattr` a `Paper` ORM row directly in production paths.
- **Idempotency:** re-running backfill, reconciliation, or acquisition must not duplicate records or diverge state (repo rule). Chroma writes use deterministic ids (`knowledge_source:{id}`, `chunk:{id}:{index}`).
- **Never overwrite a non-null curated field.** Backfill fills only currently-NULL fields; label the source of every backfilled value.
- **Traceability:** every reconciliation run writes an `event_log` audit row; every backfill writes a `metadata_backfill` audit row recording which fields were filled and from which source (the "label source of backfilled values" rule).
- **No network in tests.** External lookups are stubbed; the metadata client is injected or monkeypatched via a named seam.
- Every CLI entry point calls `load_dotenv()` before reading any environment variable.
- Chroma metadata values must be scalars (str/int/float/bool). Authors are stored in Chroma metadata as a `"; "`-joined string; in `papers.authors_json` as a JSON array string.
- `docs/projectStatus.md` is updated in the same commit as any trigger (new source doc, phase/test-count change, active-focus change).
- Manual test plans are created **before** implementation (Task 1) and their Prerequisites begin with the `uv run pytest tests/ -q` step.

---

### Task 1: Manual test plan, spec decision notes, helper script, doc sync

Phase-gate artifacts required before any implementation code.

**Files:**
- Create: `docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md`
- Create: `tests/manual/check_library_reconciliation.py`
- Modify: `docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md` (two decision notes the spec explicitly asks to be recorded)
- Modify: `docs/projectStatus.md` (reference table rows for the plan + manual test plan)

**Interfaces:**
- Consumes: nothing (docs only).
- Produces: the manual gate document and the verification helper script referenced by later tasks. The script imports `EventLog` (created in Task 6) — it is only run at the manual gate, after implementation.

- [ ] **Step 1: Create the manual test plan**

Write `docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md`:

```markdown
# Manual Test Plan — Knowledge Library Augmentation

Spec: `docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md`
Plan: `docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md`
Status: pending verification

## Prerequisites

1. **Automated test gate (always first):** run `uv run pytest tests/ -q`.
   Pass criteria: no new failures beyond those already tracked in `docs/testLog.md`.
2. Backend running (`uv run uvicorn neurodb.api.app:app_factory --factory --port 8001`)
   and frontend dev server running against it. `.env` present with provider keys;
   `SEMANTIC_SCHOLAR_API_KEY` optional (unauthenticated works, rate-limited).
3. At least one approved paper with a DOI and NULL `authors_json`, and the existing
   full-text corpus (papers 2, 9, 10, 11, 14, 52, 53, 58, 62, 63) present.

Helper script used below:
`uv run python tests/manual/check_library_reconciliation.py <source_id>`
It prints the `papers` row, `event_log` rows, summary-index metadata, and chunk
metadata/count for one paper. Pass/fail criteria are stated per case.

## Part A — Backfill + reconciliation on acquisition

**KA1 — Metadata backfill on acquire.** Pick an approved paper with a DOI and NULL
authors. Acquire full text from the Knowledge Library UI (URL, text, or local file).
Expected: acquisition completes as before; afterwards the helper script shows
`authors_json` populated (JSON array), and `abstract`/`year`/`url` filled where they
were NULL. Curated non-null fields unchanged. Any lookup failure appears as a
response warning, never a blocked acquisition.

**KA2 — Derived stores reconciled.** For the same paper, helper script shows:
summary-index metadata `data_tier: "full_text"`, `authors` non-empty, `year` and
`currency_status` matching the `papers` row; chunk metadata carries the same
`authors`/`year`/`currency_status`; at least one `event_log` row with
`event_name=full_text_acquired`, `status=ok`.

**KA3 — Idempotent re-acquire.** Re-acquire full text for the same paper.
Expected: helper script output identical for papers row, summary metadata, chunk
metadata, and chunk count (no duplicate chunks or summary docs). A new `event_log`
row is appended (audit log is append-only by design).

**KA4 — One-time reconcile of the existing corpus.** Run
`uv run python -m neurodb.cli.reconcile_fulltext --dry-run` (lists the full-text
papers, changes nothing), then without `--dry-run`. Expected: each of the existing
full-text papers reports reconciled; helper script on source 9 (Hopfield) shows
summary `data_tier: "full_text"` (was `abstract`) and authors populated.

## Part B — Guaranteed library use on explicit request

**KB1 — Flagged turn grounds on the library.** In NeuroTutor chat ask:
"Use the knowledge library: who wrote the paper on content-addressable memory and
collective computation?" Expected: a visible notice line
"Searched Knowledge Library — full-text passages: M, summaries: N" appears on the
turn, and the answer names the author (Hopfield) grounded on library content —
not a claim that the agent has no information.

**KB2 — Flagged turn, nothing relevant.** Ask: "Check the library for lattice QCD
results on quark confinement." Expected: the searched-library notice appears with
low/zero counts and the agent states plainly that the library was searched and had
nothing relevant (no invented grounding).

**KB3 — Summary fallback.** Ask a library-flagged question that only matches an
abstract/metadata-tier paper (no full text). Expected: notice shows
`full-text passages: 0, summaries: N>0`; answer grounds on the summary content.

**KB4 — Non-flagged turn unchanged.** Ask a normal topic question with no library
phrase. Expected: no searched-library notice; agent behaves as today (may still
call library tools on its own).
```

- [ ] **Step 2: Create the verification helper script**

Write `tests/manual/check_library_reconciliation.py`:

```python
"""Print DuckDB + Chroma state for one paper: papers row, event_log rows,
summary-index metadata, chunk metadata/count.

Usage: uv run python tests/manual/check_library_reconciliation.py SOURCE_ID [--db PATH]
Read-only; used by docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md.
NOTE: imports EventLog, which exists once the implementation tasks land.
"""
from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", type=int)
    parser.add_argument("--db", default=os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb"))
    args = parser.parse_args()

    import chromadb

    import neurodb.connectors  # noqa: F401 — registers connector ORM models
    from neurodb.api.app import _chroma_path_for_db
    from neurodb.db import get_engine, get_session
    from neurodb.schema import EventLog, Paper

    engine = get_engine(f"duckdb:///{args.db}")
    with get_session(engine) as session:
        paper = session.get(Paper, args.source_id)
        if paper is None:
            raise SystemExit(f"paper {args.source_id} not found")
        print("papers row:", json.dumps({
            "id": paper.id, "title": paper.title, "doi": paper.doi, "url": paper.url,
            "authors_json": paper.authors_json,
            "abstract": (paper.abstract or "")[:120],
            "year": paper.year, "data_tier": paper.data_tier,
            "currency_status": paper.currency_status,
        }, indent=2))
        rows = (
            session.query(EventLog)
            .filter(EventLog.entity_id == str(args.source_id))
            .order_by(EventLog.id.asc())
            .all()
        )
        for row in rows:
            print(f"event_log: {row.event_name} handler={row.handler} "
                  f"status={row.status} at={row.created_at} detail={row.detail_json}")

    client = chromadb.PersistentClient(path=_chroma_path_for_db(args.db))
    summary = client.get_collection("knowledge_library").get(
        ids=[f"knowledge_source:{args.source_id}"]
    )
    print("summary metadata:", json.dumps(summary.get("metadatas") or [], indent=2))
    chunks = client.get_collection("knowledge_chunks").get(
        where={"paper_id": str(args.source_id)}
    )
    metadatas = chunks.get("metadatas") or []
    print(f"chunk count: {len(chunks.get('ids') or [])}")
    if metadatas:
        print("first chunk metadata:", json.dumps(metadatas[0], indent=2))


if __name__ == "__main__":
    main()
```

- [ ] **Step 3: Record the two implementation decisions in the spec**

The spec requires the audit-store choice be "noted here" before code. In
`docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md`:

(a) In Workstream 3, after the bullet ending "(decided during implementation, before code, with the choice noted here).", append:

```markdown
  - **Decision (2026-07-08):** dedicated `event_log` table. `QualityEvent` does not
    fit: it requires a `run_id` FK to `ingest_runs` (no ingest run exists in the
    acquisition path) and its flag/severity semantics describe data-quality findings,
    not reconciliation audit. Table: `event_log(id, event_name, entity_id, handler,
    status, detail_json, created_at)` — append-only.
```

(b) In Workstream 2, after the "Interface" code block and its three bullets, append:

```markdown
Implementation notes (2026-07-08):
- The no-DOI fallback is an external **title** lookup (Semantic Scholar search +
  normalized-title match). No current parser extracts bibliographic metadata
  (`ParsedArtifact` carries none), so if both DOI and title lookup fail, fields stay
  NULL with a recorded warning. Extending parsers to emit document-parsed metadata
  is deferred.
- The write path is injected (`set_fields` callable) rather than passing a live
  `session`/`paper`: DuckDB rejects UPDATEs on FK-referenced `papers` rows, so the
  route supplies its FK-safe `_update_paper_fields`. Decision logic stays pure.
```

- [ ] **Step 4: Sync `docs/projectStatus.md`**

In the reference table, directly under the existing spec row for
`docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md`, add:

```markdown
| `docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md` | Knowledge Library augmentation implementation plan — 12 tasks (manual gate doc, metadata lookup client, backfill logic, event emitter, Chroma metadata updates, event_log + reconciliation handler, acquisition wiring, one-time reconcile CLI, library directive module, chat integration + prompt, frontend notice, verification/doc sync); ready to execute |
| `docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md` | Knowledge Library augmentation manual gate (pending verification) — KA1–KA4 backfill/reconciliation/idempotency/one-time CLI; KB1–KB4 deterministic library search, empty-state honesty, summary fallback, non-flagged turns unchanged |
```

- [ ] **Step 5: Commit**

```bash
git add docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md \
        tests/manual/check_library_reconciliation.py \
        docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md \
        docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md \
        docs/projectStatus.md
git commit -m "docs: knowledge-library augmentation manual gate, spec decisions, plan sync"
```

---

### Task 2: External metadata lookup client

**Files:**
- Create: `src/neurodb/metadata_lookup.py`
- Test: `tests/unit/test_metadata_lookup.py`

**Interfaces:**
- Consumes: nothing internal (httpx only).
- Produces (used by Task 3 and Task 7):
  - `@dataclass PaperMetadata(source: str, authors: list[str], abstract: str | None, year: int | None, doi: str | None, url: str | None)`
  - `class MetadataLookupClient(http_client=None, timeout: float = 10.0)` with `lookup(*, doi: str | None = None, title: str | None = None) -> PaperMetadata | None`

API shapes (verified live 2026-07-08):
- Semantic Scholar `GET https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,abstract,year,authors,externalIds,url` → `{"authors": [{"authorId", "name"}], "year": int, "abstract": str, "externalIds": {"DOI": str}, "url": str, "title": str}`; optional `x-api-key` header from `SEMANTIC_SCHOLAR_API_KEY`.
- Crossref `GET https://api.crossref.org/works/{doi}` → `{"message": {"title": [str], "author": [{"given", "family"}], "published": {"date-parts": [[year, ...]]}, "abstract": "<jats:p>..." , "DOI": str}}` (abstract carries JATS markup — strip tags).
- Title fallback: Semantic Scholar `GET .../paper/search?query={title}&limit=1&fields=...` → `{"data": [paper]}`; trust the hit only when normalized titles match.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_metadata_lookup.py`:

```python
"""Tests for MetadataLookupClient (Semantic Scholar + Crossref, no network)."""
from __future__ import annotations

import httpx
import pytest

from neurodb.metadata_lookup import MetadataLookupClient, PaperMetadata

_S2_DOI = {
    "title": "Neural networks and physical systems",
    "year": 1982,
    "abstract": "Computational properties emerge...",
    "url": "https://www.semanticscholar.org/paper/98b4",
    "externalIds": {"DOI": "10.1073/PNAS.79.8.2554"},
    "authors": [{"authorId": "3219867", "name": "J. Hopfield"}],
}

_CROSSREF = {
    "message": {
        "title": ["Neural networks and physical systems"],
        "author": [{"given": "J J", "family": "Hopfield"}],
        "published": {"date-parts": [[1982, 4]]},
        "abstract": "<jats:p>Computational properties emerge...</jats:p>",
        "DOI": "10.1073/pnas.79.8.2554",
    }
}

_S2_SEARCH = {"data": [_S2_DOI]}


class _StubHTTP:
    """Maps URL substrings to (status_code, json_payload)."""

    def __init__(self, routes: dict):
        self.routes = routes
        self.calls: list[str] = []

    def get(self, url, params=None, headers=None):
        self.calls.append(url)
        for fragment, (status, payload) in self.routes.items():
            if fragment in url:
                return httpx.Response(status, json=payload,
                                      request=httpx.Request("GET", url))
        return httpx.Response(404, json={},
                              request=httpx.Request("GET", url))


def test_doi_lookup_prefers_semantic_scholar():
    http = _StubHTTP({"semanticscholar.org/graph/v1/paper/DOI:": (200, _S2_DOI)})
    found = MetadataLookupClient(http_client=http).lookup(doi="10.1073/pnas.79.8.2554")
    assert isinstance(found, PaperMetadata)
    assert found.source == "semantic_scholar"
    assert found.authors == ["J. Hopfield"]
    assert found.year == 1982
    assert found.doi == "10.1073/PNAS.79.8.2554"
    assert found.abstract.startswith("Computational")


def test_doi_lookup_falls_back_to_crossref():
    http = _StubHTTP({
        "semanticscholar.org/graph/v1/paper/DOI:": (500, {}),
        "api.crossref.org/works/": (200, _CROSSREF),
    })
    found = MetadataLookupClient(http_client=http).lookup(doi="10.1073/pnas.79.8.2554")
    assert found.source == "crossref"
    assert found.authors == ["J J Hopfield"]
    assert found.year == 1982
    assert "<jats:p>" not in found.abstract
    assert found.url == "https://doi.org/10.1073/pnas.79.8.2554"


def test_title_lookup_requires_normalized_title_match():
    http = _StubHTTP({"paper/search": (200, _S2_SEARCH)})
    client = MetadataLookupClient(http_client=http)
    hit = client.lookup(title="Neural networks and physical systems")
    assert hit is not None and hit.authors == ["J. Hopfield"]
    miss = client.lookup(title="A completely different paper title")
    assert miss is None


def test_lookup_returns_none_on_total_failure():
    http = _StubHTTP({})
    assert MetadataLookupClient(http_client=http).lookup(doi="10.1/x") is None
    assert MetadataLookupClient(http_client=http).lookup() is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metadata_lookup.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.metadata_lookup'`

- [ ] **Step 3: Implement the client**

Create `src/neurodb/metadata_lookup.py`:

```python
"""External bibliographic metadata lookup for acquisition backfill.

Source precedence (spec workstream 2): Semantic Scholar by DOI, Crossref by DOI,
then Semantic Scholar title search gated on a normalized-title match. Every
network failure degrades to None; callers record a warning and never block.
"""
from __future__ import annotations

import logging
import os
import re
from dataclasses import dataclass, field

import httpx

logger = logging.getLogger(__name__)

_S2_PAPER_URL = "https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}"
_S2_SEARCH_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
_S2_FIELDS = "title,abstract,year,authors,externalIds,url"
_CROSSREF_URL = "https://api.crossref.org/works/{doi}"
_TAG = re.compile(r"<[^>]+>")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


@dataclass
class PaperMetadata:
    source: str  # "semantic_scholar" | "crossref"
    authors: list[str] = field(default_factory=list)
    abstract: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None


def _norm_title(title: str) -> str:
    return _NON_ALNUM.sub(" ", (title or "").lower()).strip()


class MetadataLookupClient:
    """Provider-agnostic bibliographic lookup used by backfill."""

    def __init__(self, http_client=None, timeout: float = 10.0) -> None:
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=True)

    def lookup(self, *, doi: str | None = None,
               title: str | None = None) -> PaperMetadata | None:
        if doi:
            found = self._s2_by_doi(doi) or self._crossref_by_doi(doi)
            if found is not None:
                return found
        if title:
            return self._s2_by_title(title)
        return None

    def _s2_headers(self) -> dict:
        api_key = os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        return {"x-api-key": api_key} if api_key else {}

    def _s2_by_doi(self, doi: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(
                _S2_PAPER_URL.format(doi=doi),
                params={"fields": _S2_FIELDS},
                headers=self._s2_headers(),
            )
            if resp.status_code != 200:
                return None
            return self._normalize_s2(resp.json())
        except Exception:
            logger.exception("Semantic Scholar DOI lookup failed for %s", doi)
            return None

    def _s2_by_title(self, title: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(
                _S2_SEARCH_URL,
                params={"query": title, "limit": 1, "fields": _S2_FIELDS},
                headers=self._s2_headers(),
            )
            if resp.status_code != 200:
                return None
            data = resp.json().get("data") or []
            if not data:
                return None
            hit = data[0]
            if _norm_title(hit.get("title") or "") != _norm_title(title):
                return None  # wrong paper; do not contaminate curated metadata
            return self._normalize_s2(hit)
        except Exception:
            logger.exception("Semantic Scholar title lookup failed for %r", title)
            return None

    def _crossref_by_doi(self, doi: str) -> PaperMetadata | None:
        try:
            resp = self._http.get(_CROSSREF_URL.format(doi=doi))
            if resp.status_code != 200:
                return None
            return self._normalize_crossref(resp.json().get("message") or {})
        except Exception:
            logger.exception("Crossref DOI lookup failed for %s", doi)
            return None

    @staticmethod
    def _normalize_s2(raw: dict) -> PaperMetadata | None:
        if not raw:
            return None
        doi = (raw.get("externalIds") or {}).get("DOI")
        return PaperMetadata(
            source="semantic_scholar",
            authors=[a["name"] for a in (raw.get("authors") or []) if a.get("name")],
            abstract=(raw.get("abstract") or "").strip() or None,
            year=raw.get("year"),
            doi=doi,
            url=(raw.get("url") or "").strip() or None,
        )

    @staticmethod
    def _normalize_crossref(message: dict) -> PaperMetadata | None:
        if not message:
            return None
        authors = [
            " ".join(part for part in [a.get("given"), a.get("family")] if part)
            for a in (message.get("author") or [])
        ]
        parts = (message.get("published") or {}).get("date-parts") or [[None]]
        year = parts[0][0] if parts and parts[0] else None
        abstract = _TAG.sub(" ", message.get("abstract") or "").strip()
        doi = message.get("DOI")
        return PaperMetadata(
            source="crossref",
            authors=[a for a in authors if a],
            abstract=" ".join(abstract.split()) or None,
            year=int(year) if isinstance(year, int) else None,
            doi=doi,
            url=f"https://doi.org/{doi}" if doi else None,
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metadata_lookup.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/metadata_lookup.py tests/unit/test_metadata_lookup.py
git commit -m "feat(backfill): external metadata lookup client (S2 DOI, Crossref, title fallback)"
```

---

### Task 3: Backfill decision logic

**Files:**
- Create: `src/neurodb/metadata_backfill.py`
- Test: `tests/unit/test_metadata_backfill.py`

**Interfaces:**
- Consumes: `PaperMetadata`, `MetadataLookupClient.lookup` (Task 2); `neurodb.db.get_session`; `neurodb.schema.Paper`.
- Produces (used by Task 7 wiring):
  - `@dataclass BackfillResult(filled: dict[str, str], values: dict[str, object], warnings: list[str])` — `filled` maps field name → source label.
  - `select_backfill_fields(current: dict, found: PaperMetadata) -> dict[str, object]` — pure; returns only fields that are currently NULL/empty.
  - `backfill_paper_metadata(engine, source_id: int, *, metadata_client, set_fields) -> BackfillResult` — `set_fields(**fields)` is the injected FK-safe writer.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_metadata_backfill.py`:

```python
"""Tests for backfill field selection and orchestration (no network)."""
from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import get_session
from neurodb.metadata_backfill import (
    BackfillResult,
    backfill_paper_metadata,
    select_backfill_fields,
)
from neurodb.metadata_lookup import PaperMetadata
from neurodb.schema import Base, Paper

_FOUND = PaperMetadata(
    source="semantic_scholar",
    authors=["J. Hopfield"],
    abstract="Collective properties emerge.",
    year=1982,
    doi="10.1073/pnas.79.8.2554",
    url="https://doi.org/10.1073/pnas.79.8.2554",
)


def _engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _add_paper(engine, **overrides) -> int:
    values = dict(title="Hopfield 1982", normalized_title="hopfield 1982",
                  source_type="paper", topic_context="memory", status="approved",
                  queued_at="2026-01-01T00:00:00")
    values.update(overrides)
    with get_session(engine) as session:
        paper = Paper(**values)
        session.add(paper)
        session.flush()
        return paper.id


class _StubClient:
    def __init__(self, found):
        self.found = found
        self.calls: list[dict] = []

    def lookup(self, *, doi=None, title=None):
        self.calls.append({"doi": doi, "title": title})
        return self.found


def test_select_fills_only_null_fields():
    current = {"authors_json": None, "abstract": "curated abstract",
               "year": None, "doi": "10.9999/curated", "url": None}
    fields = select_backfill_fields(current, _FOUND)
    assert fields == {
        "authors_json": json.dumps(["J. Hopfield"]),
        "year": 1982,
        "url": "https://doi.org/10.1073/pnas.79.8.2554",
    }  # abstract and doi are curated → untouched


def test_select_returns_empty_when_everything_curated():
    current = {"authors_json": "[\"X\"]", "abstract": "a", "year": 2000,
               "doi": "10.1/x", "url": "https://x"}
    assert select_backfill_fields(current, _FOUND) == {}


def test_backfill_uses_doi_when_present_and_writes_via_set_fields():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1073/pnas.79.8.2554")
    client = _StubClient(_FOUND)
    written: dict = {}
    result = backfill_paper_metadata(
        engine, paper_id, metadata_client=client,
        set_fields=lambda **f: written.update(f),
    )
    assert client.calls == [{"doi": "10.1073/pnas.79.8.2554", "title": None}]
    assert written["authors_json"] == json.dumps(["J. Hopfield"])
    assert result.filled["authors_json"] == "semantic_scholar"
    assert result.warnings == []


def test_backfill_falls_back_to_title_when_no_doi():
    engine = _engine()
    paper_id = _add_paper(engine, doi=None)
    client = _StubClient(_FOUND)
    backfill_paper_metadata(engine, paper_id, metadata_client=client,
                            set_fields=lambda **f: None)
    assert client.calls == [{"doi": None, "title": "Hopfield 1982"}]


def test_backfill_lookup_empty_records_warning_and_writes_nothing():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1/x")
    written: dict = {}
    result = backfill_paper_metadata(
        engine, paper_id, metadata_client=_StubClient(None),
        set_fields=lambda **f: written.update(f),
    )
    assert written == {}
    assert result.filled == {} and len(result.warnings) == 1


def test_backfill_write_failure_becomes_warning():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1/x")

    def _boom(**fields):
        raise RuntimeError("duplicate doi")

    result = backfill_paper_metadata(engine, paper_id,
                                     metadata_client=_StubClient(_FOUND),
                                     set_fields=_boom)
    assert result.filled == {}
    assert any("failed" in w for w in result.warnings)


def test_backfill_is_idempotent():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1073/pnas.79.8.2554")
    client = _StubClient(_FOUND)

    def _apply(**fields):
        with get_session(engine) as session:  # sqlite: direct write is fine in tests
            row = session.get(Paper, paper_id)
            for key, value in fields.items():
                setattr(row, key, value)

    first = backfill_paper_metadata(engine, paper_id, metadata_client=client,
                                    set_fields=_apply)
    second = backfill_paper_metadata(engine, paper_id, metadata_client=client,
                                     set_fields=_apply)
    assert first.filled != {}
    assert second.filled == {} and second.values == {}  # nothing left to fill
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_metadata_backfill.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.metadata_backfill'`

- [ ] **Step 3: Implement**

Create `src/neurodb/metadata_backfill.py`:

```python
"""Backfill NULL bibliographic Paper fields on full-text acquisition (workstream 2).

Pure decision logic (select_backfill_fields) is separated from the write, which is
injected as `set_fields` because DuckDB requires the route's FK-safe updater for
`papers` rows. Never overwrites a non-null curated field; never raises out of
backfill_paper_metadata — failures become warnings so acquisition is never blocked.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from neurodb.db import get_session
from neurodb.metadata_lookup import PaperMetadata
from neurodb.schema import Paper


@dataclass
class BackfillResult:
    filled: dict[str, str] = field(default_factory=dict)   # field -> source label
    values: dict[str, object] = field(default_factory=dict)  # field -> written value
    warnings: list[str] = field(default_factory=list)


def select_backfill_fields(current: dict, found: PaperMetadata) -> dict[str, object]:
    """Return only the target fields that are currently NULL/empty. Pure."""
    fields: dict[str, object] = {}
    if not current.get("authors_json") and found.authors:
        fields["authors_json"] = json.dumps(found.authors)
    if not current.get("abstract") and found.abstract:
        fields["abstract"] = found.abstract
    if current.get("year") is None and found.year is not None:
        fields["year"] = found.year
    if not current.get("doi") and found.doi:
        fields["doi"] = found.doi
    if not current.get("url") and found.url:
        fields["url"] = found.url
    return fields


def backfill_paper_metadata(engine, source_id: int, *,
                            metadata_client, set_fields) -> BackfillResult:
    """Fill NULL bibliographic fields for one paper. Warnings, never exceptions."""
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        if paper is None:
            return BackfillResult(warnings=[f"paper {source_id} not found"])
        current = {
            "authors_json": paper.authors_json,
            "abstract": paper.abstract,
            "year": paper.year,
            "doi": paper.doi,
            "url": paper.url,
        }
        title = paper.title

    try:
        found = metadata_client.lookup(
            doi=current["doi"],
            title=None if current["doi"] else title,
        )
    except Exception as exc:
        return BackfillResult(warnings=[f"metadata lookup failed: {exc}"])
    if found is None:
        return BackfillResult(warnings=[
            "no external metadata found (DOI and title lookup empty); "
            "bibliographic fields left NULL",
        ])

    fields = select_backfill_fields(current, found)
    if not fields:
        return BackfillResult()
    try:
        set_fields(**fields)
    except Exception as exc:
        return BackfillResult(warnings=[f"metadata backfill write failed: {exc}"])
    return BackfillResult(
        filled={name: found.source for name in fields},
        values=fields,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_metadata_backfill.py -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/metadata_backfill.py tests/unit/test_metadata_backfill.py
git commit -m "feat(backfill): NULL-only bibliographic field selection + orchestration"
```

---

### Task 4: In-process event emitter

**Files:**
- Create: `src/neurodb/events.py`
- Test: `tests/unit/test_events.py`

**Interfaces:**
- Consumes: nothing internal.
- Produces (used by Tasks 6, 7, 8):
  - `FULL_TEXT_ACQUIRED = "full_text_acquired"` (module constant)
  - `subscribe(name: str, handler: Callable[..., object], *, key: str | None = None) -> None` — re-subscribing with the same `key` replaces (keeps repeated `create_app` calls idempotent).
  - `emit(name: str, **payload) -> list[dict]` — synchronous dispatch; returns `[{"handler": str, "status": "ok"|"error", "error": str | None}]`.
  - `reset() -> None` — test hook; clears all subscriptions.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_events.py`:

```python
"""Tests for the in-process event emitter."""
from __future__ import annotations

import logging

import pytest

from neurodb import events


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


def test_emit_dispatches_to_all_handlers_with_payload():
    seen: list[tuple[str, int]] = []
    events.subscribe("thing_happened", lambda source_id: seen.append(("a", source_id)),
                     key="a")
    events.subscribe("thing_happened", lambda source_id: seen.append(("b", source_id)),
                     key="b")
    outcomes = events.emit("thing_happened", source_id=7)
    assert seen == [("a", 7), ("b", 7)]
    assert [o["status"] for o in outcomes] == ["ok", "ok"]


def test_handler_error_is_isolated_and_recorded(caplog):
    seen: list[int] = []

    def _boom(source_id):
        raise RuntimeError("kaput")

    events.subscribe("thing_happened", _boom, key="boom")
    events.subscribe("thing_happened", lambda source_id: seen.append(source_id),
                     key="ok")
    with caplog.at_level(logging.ERROR):
        outcomes = events.emit("thing_happened", source_id=1)
    assert seen == [1]  # second handler still ran
    assert outcomes[0] == {"handler": "boom", "status": "error", "error": "kaput"}
    assert "boom" in caplog.text  # not swallowed silently


def test_keyed_resubscribe_replaces_previous_handler():
    seen: list[str] = []
    events.subscribe("e", lambda: seen.append("old"), key="k")
    events.subscribe("e", lambda: seen.append("new"), key="k")
    events.emit("e")
    assert seen == ["new"]


def test_emit_with_no_subscribers_returns_empty():
    assert events.emit("nobody_listens", source_id=1) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_events.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.events'`

- [ ] **Step 3: Implement**

Create `src/neurodb/events.py`:

```python
"""Minimal synchronous in-process domain-event emitter (workstream 3).

Single-process by design — no bus, no queue. Handlers run in the emitting
request/thread. A handler error is logged and recorded in the emit outcome,
never raised to the caller and never allowed to stop later handlers.
"""
from __future__ import annotations

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)

FULL_TEXT_ACQUIRED = "full_text_acquired"

_registry: dict[str, dict[str, Callable[..., object]]] = {}


def subscribe(name: str, handler: Callable[..., object], *,
              key: str | None = None) -> None:
    """Register handler for event `name`. Same key replaces (idempotent startup)."""
    handlers = _registry.setdefault(name, {})
    handlers[key or f"{handler.__module__}.{handler.__qualname__}"] = handler


def emit(name: str, **payload) -> list[dict]:
    """Dispatch synchronously to all subscribers; return per-handler outcomes."""
    outcomes: list[dict] = []
    for key, handler in list(_registry.get(name, {}).items()):
        try:
            handler(**payload)
            outcomes.append({"handler": key, "status": "ok", "error": None})
        except Exception as exc:
            logger.exception("event handler %s failed for event %s", key, name)
            outcomes.append({"handler": key, "status": "error", "error": str(exc)})
    return outcomes


def reset() -> None:
    """Test hook: clear all subscriptions."""
    _registry.clear()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_events.py -q`
Expected: 4 passed

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/events.py tests/unit/test_events.py
git commit -m "feat(events): synchronous in-process event emitter with isolated handler errors"
```

---

### Task 5: Chroma metadata-only update methods

Reconciliation must fix metadata without re-embedding documents.

**Files:**
- Modify: `src/neurodb/chunk_store.py` (add one method)
- Modify: `src/neurodb/knowledge_store.py` (add one method)
- Test: `tests/unit/test_store_metadata_update.py`

**Interfaces:**
- Consumes: existing `ChunkStore` / `KnowledgeLibraryStore` internals (`self._collection`).
- Produces (used by Task 6):
  - `ChunkStore.update_paper_metadata(paper_id: int, metadata: dict) -> int` — merges `metadata` into every chunk of the paper; returns updated chunk count (0 when the paper has no chunks).
  - `KnowledgeLibraryStore.update_summary_metadata(source_id: int, metadata: dict) -> bool` — merges into the summary doc `knowledge_source:{source_id}`; False when absent.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_store_metadata_update.py`:

```python
"""Tests for metadata-only updates on the two Chroma stores (no re-embedding)."""
from __future__ import annotations

import uuid

import chromadb

from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.knowledge_store import KnowledgeLibraryStore


class _StubEmbedder:
    def __init__(self):
        self.embed_calls = 0

    def embed(self, texts):
        self.embed_calls += 1
        return [[0.1, 0.2, 0.3] for _ in texts]


def _chunk_store(embedder):
    return ChunkStore(client=chromadb.EphemeralClient(), embedder=embedder,
                      collection_name=f"ck_{uuid.uuid4().hex}")


def _knowledge_store(embedder):
    return KnowledgeLibraryStore(client=chromadb.EphemeralClient(), embedder=embedder,
                                 collection_name=f"kl_{uuid.uuid4().hex}")


def _seed_chunks(store, paper_id=9):
    store.add_chunks(
        paper_id=paper_id, title="Hopfield 1982", year=None,
        currency_status="current", text_source="pdf_pymupdf",
        chunks=[
            Chunk(chunk_index=0, text="alpha", section="Intro", char_start=0, char_end=5),
            Chunk(chunk_index=1, text="beta", section="Methods", char_start=5, char_end=9),
        ],
    )


def test_chunk_metadata_update_merges_and_counts():
    embedder = _StubEmbedder()
    store = _chunk_store(embedder)
    _seed_chunks(store)
    baseline_calls = embedder.embed_calls
    updated = store.update_paper_metadata(9, {"authors": "J. Hopfield", "year": "1982"})
    assert updated == 2
    assert embedder.embed_calls == baseline_calls  # metadata-only, no re-embed
    hits = store.search("alpha", n=5, min_score=-1.0)
    target = [h for h in hits if h["chunk_id"] == "chunk:9:0"][0]
    assert target["year"] == "1982"
    assert target["section"] == "Intro"  # untouched fields preserved


def test_chunk_metadata_update_missing_paper_returns_zero():
    assert _chunk_store(_StubEmbedder()).update_paper_metadata(123, {"a": "b"}) == 0


def test_summary_metadata_update_merges_without_reembedding():
    embedder = _StubEmbedder()
    store = _knowledge_store(embedder)
    store.add_summary(source_id=9, title="Hopfield 1982", doi=None,
                      topic_context="memory", summary="summary text",
                      data_tier="abstract")
    baseline_calls = embedder.embed_calls
    assert store.update_summary_metadata(
        9, {"data_tier": "full_text", "authors": "J. Hopfield"}) is True
    assert embedder.embed_calls == baseline_calls
    hit = store.search("summary text", n=1)[0]
    assert hit["metadata"]["data_tier"] == "full_text"
    assert hit["metadata"]["authors"] == "J. Hopfield"
    assert hit["metadata"]["title"] == "Hopfield 1982"  # untouched fields preserved


def test_summary_metadata_update_missing_doc_returns_false():
    assert _knowledge_store(_StubEmbedder()).update_summary_metadata(77, {}) is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_store_metadata_update.py -q`
Expected: FAIL — `AttributeError: 'ChunkStore' object has no attribute 'update_paper_metadata'`

- [ ] **Step 3: Implement both methods**

In `src/neurodb/chunk_store.py`, after `delete_paper` (line ~63), add:

```python
    def update_paper_metadata(self, paper_id: int, metadata: dict) -> int:
        """Merge metadata into every chunk of a paper without re-embedding."""
        existing = self._collection.get(where={"paper_id": str(paper_id)})
        ids = existing.get("ids") or []
        if not ids:
            return 0
        merged = [{**(old or {}), **metadata} for old in existing["metadatas"]]
        self._collection.update(ids=ids, metadatas=merged)
        return len(ids)
```

In `src/neurodb/knowledge_store.py`, after `remove_summary` (line ~76), add:

```python
    def update_summary_metadata(self, source_id: int, metadata: dict) -> bool:
        """Merge metadata into an existing summary doc without re-embedding."""
        doc_id = f"knowledge_source:{source_id}"
        existing = self._collection.get(ids=[doc_id])
        if not existing.get("ids"):
            return False
        merged = {**(existing["metadatas"][0] or {}), **metadata}
        self._collection.update(ids=[doc_id], metadatas=[merged])
        return True
```

- [ ] **Step 4: Run the new tests plus both stores' existing suites**

Run: `uv run pytest tests/unit/test_store_metadata_update.py tests/unit/test_chunk_store.py tests/unit/test_chunk_store_page.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chunk_store.py src/neurodb/knowledge_store.py \
        tests/unit/test_store_metadata_update.py
git commit -m "feat(stores): metadata-only updates on chunk + summary Chroma collections"
```

---

### Task 6: `event_log` audit table + reconciliation handler

**Files:**
- Modify: `src/neurodb/schema.py` (new `EventLog` model — a new table needs no migration entry: `init_db` runs `Base.metadata.create_all(engine)` at every startup, which creates missing tables)
- Create: `src/neurodb/reconciliation.py`
- Test: `tests/unit/test_reconciliation.py`

**Interfaces:**
- Consumes: `events.subscribe` / `FULL_TEXT_ACQUIRED` (Task 4); `ChunkStore.update_paper_metadata`, `KnowledgeLibraryStore.update_summary_metadata` (Task 5); `Paper`, `get_session`.
- Produces (used by Tasks 7, 8):
  - `class EventLog(Base)` — table `event_log`: `id, event_name, entity_id, handler, status, detail_json, created_at`.
  - `reconcile_full_text_acquired(engine, knowledge_store, chunk_store, *, source_id: int) -> dict` — returns detail dict `{"summary_updated": bool, "chunks_updated": int, "skipped": list[str]}`; writes one `event_log` row per run; re-raises on failure after logging the error row (so `emit` records the error outcome).
  - `register_reconciliation(engine, knowledge_store, chunk_store) -> None` — subscribes with `key="reconcile_derived_stores"`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_reconciliation.py`:

```python
"""Tests for the FullTextAcquired reconciliation handler + event_log audit."""
from __future__ import annotations

import json
import uuid

import chromadb
import pytest
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb import events
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.reconciliation import (
    reconcile_full_text_acquired,
    register_reconciliation,
)
from neurodb.schema import Base, EventLog, Paper


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


def _engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _stores():
    client = chromadb.EphemeralClient()
    return (
        KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                              collection_name=f"kl_{uuid.uuid4().hex}"),
        ChunkStore(client=client, embedder=_StubEmbedder(),
                   collection_name=f"ck_{uuid.uuid4().hex}"),
    )


def _add_full_text_paper(engine) -> int:
    with get_session(engine) as session:
        paper = Paper(title="Hopfield 1982", normalized_title="hopfield 1982",
                      source_type="paper", topic_context="memory",
                      status="approved", queued_at="2026-01-01T00:00:00",
                      authors_json=json.dumps(["J. Hopfield"]), year=1982,
                      data_tier="full_text", currency_status="current")
        session.add(paper)
        session.flush()
        return paper.id


def _seed_stale_stores(knowledge_store, chunk_store, paper_id):
    knowledge_store.add_summary(source_id=paper_id, title="Hopfield 1982", doi=None,
                                topic_context="memory", summary="summary body",
                                data_tier="abstract")  # stale tier
    chunk_store.add_chunks(paper_id=paper_id, title="Hopfield 1982", year=None,
                           currency_status="current", text_source="pdf_pymupdf",
                           chunks=[Chunk(chunk_index=0, text="alpha",
                                         section=None, char_start=0, char_end=5)])


def _summary_meta(knowledge_store, paper_id):
    return knowledge_store.search("summary body", n=1)[0]["metadata"]


def _chunk_meta(chunk_store):
    return chunk_store.search("alpha", n=1, min_score=-1.0)[0]


def test_reconcile_flips_stale_tier_and_pushes_authors():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    detail = reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                          source_id=paper_id)
    assert detail["summary_updated"] is True and detail["chunks_updated"] == 1
    meta = _summary_meta(knowledge_store, paper_id)
    assert meta["data_tier"] == "full_text"
    assert meta["authors"] == "J. Hopfield"
    assert meta["year"] == "1982"
    chunk = _chunk_meta(chunk_store)
    assert chunk["year"] == "1982"

    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert len(rows) == 1
        assert rows[0].event_name == "full_text_acquired"
        assert rows[0].entity_id == str(paper_id)
        assert rows[0].status == "ok"


def test_reconcile_is_idempotent():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                 source_id=paper_id)
    first_summary = _summary_meta(knowledge_store, paper_id)
    reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                 source_id=paper_id)
    assert _summary_meta(knowledge_store, paper_id) == first_summary
    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert [r.status for r in rows] == ["ok", "ok"]  # append-only audit


def test_reconcile_missing_paper_logs_error_row_and_raises():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    with pytest.raises(RuntimeError):
        reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                     source_id=999)
    with get_session(engine) as session:
        rows = session.query(EventLog).all()
        assert len(rows) == 1 and rows[0].status == "error"


def test_reconcile_tolerates_missing_stores():
    engine = _engine()
    paper_id = _add_full_text_paper(engine)
    detail = reconcile_full_text_acquired(engine, None, None, source_id=paper_id)
    assert detail["summary_updated"] is False and detail["chunks_updated"] == 0
    assert len(detail["skipped"]) == 2


def test_register_reconciliation_reacts_to_emit():
    engine = _engine()
    knowledge_store, chunk_store = _stores()
    paper_id = _add_full_text_paper(engine)
    _seed_stale_stores(knowledge_store, chunk_store, paper_id)

    register_reconciliation(engine, knowledge_store, chunk_store)
    register_reconciliation(engine, knowledge_store, chunk_store)  # keyed: no dup
    outcomes = events.emit(events.FULL_TEXT_ACQUIRED, source_id=paper_id)
    assert len(outcomes) == 1 and outcomes[0]["status"] == "ok"
    assert _summary_meta(knowledge_store, paper_id)["data_tier"] == "full_text"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_reconciliation.py -q`
Expected: FAIL — `ImportError` (no `EventLog`, no `neurodb.reconciliation`)

- [ ] **Step 3: Add the `EventLog` model**

In `src/neurodb/schema.py`, after the `QualityEvent` class (line ~93), add:

```python
class EventLog(Base):
    """Append-only audit log of domain events and handler outcomes.

    Deliberately not QualityEvent: that table requires a run_id FK to ingest_runs
    (absent in the acquisition path) and models data-quality findings, not audit.
    """
    __tablename__ = "event_log"

    id: Mapped[int] = mapped_column(Integer, Sequence("event_log_id_seq"), primary_key=True)
    event_name: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    handler: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    detail_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Implement the reconciliation module**

Create `src/neurodb/reconciliation.py`:

```python
"""FullTextAcquired reconciliation: keep derived stores consistent with `papers`.

papers is the source of truth; this handler pushes data_tier / authors / year /
currency_status into the summary index (knowledge_library) and the chunk index
(knowledge_chunks) with metadata-only updates. Idempotent: deterministic doc ids,
merge-updates only. Auditable: one event_log row per run.
"""
from __future__ import annotations

import json
import logging
from datetime import UTC, datetime

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.events import FULL_TEXT_ACQUIRED, subscribe
from neurodb.schema import EventLog, Paper

logger = logging.getLogger(__name__)

HANDLER_KEY = "reconcile_derived_stores"


def register_reconciliation(engine: Engine, knowledge_store, chunk_store) -> None:
    """Subscribe the reconciliation handler once (keyed: re-registration replaces)."""

    def _handler(source_id: int) -> None:
        reconcile_full_text_acquired(engine, knowledge_store, chunk_store,
                                     source_id=source_id)

    subscribe(FULL_TEXT_ACQUIRED, _handler, key=HANDLER_KEY)


def reconcile_full_text_acquired(engine: Engine, knowledge_store, chunk_store, *,
                                 source_id: int) -> dict:
    """Re-sync derived stores for one paper. Raises on failure after audit row."""
    detail: dict = {"summary_updated": False, "chunks_updated": 0, "skipped": []}
    status = "ok"
    try:
        with get_session(engine) as session:
            paper = session.get(Paper, source_id)
            if paper is None:
                raise ValueError(f"paper {source_id} not found")
            authors = ""
            if paper.authors_json:
                authors = "; ".join(json.loads(paper.authors_json))
            metadata = {
                "data_tier": paper.data_tier,
                "year": str(paper.year) if paper.year else "",
                "currency_status": paper.currency_status,
                "authors": authors,
            }
        if knowledge_store is None:
            detail["skipped"].append("knowledge_store unavailable")
        else:
            detail["summary_updated"] = knowledge_store.update_summary_metadata(
                source_id, metadata)
        if chunk_store is None:
            detail["skipped"].append("chunk_store unavailable")
        else:
            detail["chunks_updated"] = chunk_store.update_paper_metadata(
                source_id, metadata)
    except Exception as exc:
        status = "error"
        detail["error"] = str(exc)
        logger.exception("reconciliation failed for source %d", source_id)
    _log_event(engine, source_id=source_id, status=status, detail=detail)
    if status == "error":
        raise RuntimeError(
            f"reconciliation failed for source {source_id}: {detail['error']}")
    return detail


def _log_event(engine: Engine, *, source_id: int, status: str, detail: dict) -> None:
    try:
        with get_session(engine) as session:
            session.add(EventLog(
                event_name=FULL_TEXT_ACQUIRED,
                entity_id=str(source_id),
                handler=HANDLER_KEY,
                status=status,
                detail_json=json.dumps(detail),
                created_at=datetime.now(UTC).isoformat(),
            ))
    except Exception:
        logger.exception("event_log write failed for source %d", source_id)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_reconciliation.py tests/unit/test_db.py -q`
Expected: all pass (test_db confirms the new table doesn't break `create_all`)

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/reconciliation.py tests/unit/test_reconciliation.py
git commit -m "feat(reconcile): event_log audit table + FullTextAcquired store reconciliation"
```

---

### Task 7: Wire backfill + event into all three acquisition paths and app startup

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py` (shared post-acquisition hook; 2a path line ~391; `fulltext_review` confirm path line ~432; `_run_phase2b_job` line ~517)
- Modify: `src/neurodb/phase2b.py` (`run_acquisition` gains `on_verified` callback)
- Modify: `src/neurodb/api/app.py` (`create_app` registers the reconciliation handler)
- Test: `tests/unit/test_api_knowledge_library_postacq.py`

**Interfaces:**
- Consumes: `backfill_paper_metadata` (Task 3), `emit`/`FULL_TEXT_ACQUIRED` (Task 4), `register_reconciliation` (Task 6), existing `_update_paper_fields` / `_commit_chunks`.
- Produces (used by Task 8 CLI):
  - `run_post_acquisition(source_id: int, engine: Engine) -> list[str]` in `knowledge_library.py` — the single shared commit point: backfill, then emit; returns warnings; never raises.
  - `_build_metadata_client() -> MetadataLookupClient` in `knowledge_library.py` — module-level seam; tests monkeypatch it so no test touches the network.
  - `run_acquisition(..., on_verified: Callable[[], None] | None = None)` in `phase2b.py` — called after the accept branch's `set_fields`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_api_knowledge_library_postacq.py`:

```python
"""Integration tests: acquisition triggers backfill + FullTextAcquired reconciliation."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import chromadb
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb import events
from neurodb.api.routes import knowledge_library as kl_module
from neurodb.api.routes.knowledge_library import router
from neurodb.chunk_store import ChunkStore
from neurodb.db import get_session
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.metadata_lookup import PaperMetadata
from neurodb.reconciliation import register_reconciliation
from neurodb.schema import Base, EventLog, Paper

_FOUND = PaperMetadata(
    source="semantic_scholar",
    authors=["J. Hopfield"],
    abstract="Collective properties emerge.",
    year=1982,
    doi="10.1073/pnas.79.8.2554",
    url="https://doi.org/10.1073/pnas.79.8.2554",
)

_BODY_TEXT = ("Content-addressable memory emerges from collective dynamics. " * 30)


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


class _StubMetadataClient:
    def lookup(self, *, doi=None, title=None):
        return _FOUND


@pytest.fixture(autouse=True)
def _clean_registry():
    events.reset()
    yield
    events.reset()


@pytest.fixture(autouse=True)
def _stub_metadata_client(monkeypatch):
    monkeypatch.setattr(kl_module, "_build_metadata_client",
                        lambda: _StubMetadataClient())


def _make_env():
    engine = create_engine("duckdb:///:memory:", poolclass=StaticPool)
    Base.metadata.create_all(engine)
    client = chromadb.EphemeralClient()
    knowledge_store = KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                                            collection_name=f"kl_{uuid.uuid4().hex}")
    chunk_store = ChunkStore(client=client, embedder=_StubEmbedder(),
                             collection_name=f"ck_{uuid.uuid4().hex}")
    register_reconciliation(engine, knowledge_store, chunk_store)

    app = FastAPI()
    app.state.engine = engine
    app.state.knowledge_store = knowledge_store
    app.state.chunk_store = chunk_store
    app.state.tasks = {}
    app.include_router(router, prefix="/api/knowledge-library")
    return TestClient(app), engine, knowledge_store, chunk_store


def _insert_approved_paper(engine, *, doi="10.1073/pnas.79.8.2554") -> int:
    with get_session(engine) as session:
        paper = Paper(title="Hopfield 1982", normalized_title="hopfield 1982",
                      source_type="paper", topic_context="memory",
                      status="approved", queued_at="2026-01-01T00:00:00",
                      reviewed_at="2026-01-02T00:00:00", doi=doi)
        session.add(paper)
        session.flush()
        return paper.id


def _acquire(client, source_id):
    resp = client.post(f"/api/knowledge-library/{source_id}/acquire-full-text",
                       json={"text": _BODY_TEXT, "format": "txt"})
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_acquire_backfills_authors_and_reconciles_stores():
    client, engine, knowledge_store, chunk_store = _make_env()
    source_id = _insert_approved_paper(engine)
    knowledge_store.add_summary(source_id=source_id, title="Hopfield 1982",
                                doi=None, topic_context="memory",
                                summary="summary body", data_tier="abstract")

    item = _acquire(client, source_id)
    assert item["data_tier"] == "full_text"

    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        assert json.loads(paper.authors_json) == ["J. Hopfield"]
        assert paper.year == 1982
        rows = session.query(EventLog).order_by(EventLog.id.asc()).all()
        assert [r.event_name for r in rows] == ["metadata_backfill", "full_text_acquired"]
        assert all(r.status == "ok" for r in rows)
        backfill_detail = json.loads(rows[0].detail_json)
        assert backfill_detail["filled"]["authors_json"] == "semantic_scholar"

    summary_meta = knowledge_store.search("summary body", n=1)[0]["metadata"]
    assert summary_meta["data_tier"] == "full_text"
    assert summary_meta["authors"] == "J. Hopfield"
    chunk_meta = chunk_store.search("collective dynamics", n=1, min_score=-1.0)[0]
    assert chunk_meta["year"] == "1982"


def test_reacquire_is_idempotent():
    client, engine, knowledge_store, chunk_store = _make_env()
    source_id = _insert_approved_paper(engine)
    knowledge_store.add_summary(source_id=source_id, title="Hopfield 1982",
                                doi=None, topic_context="memory",
                                summary="summary body", data_tier="abstract")

    _acquire(client, source_id)
    first_chunks = chunk_store._collection.count()
    first_meta = knowledge_store.search("summary body", n=1)[0]["metadata"]

    _acquire(client, source_id)
    assert chunk_store._collection.count() == first_chunks
    assert knowledge_store.search("summary body", n=1)[0]["metadata"] == first_meta
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        assert json.loads(paper.authors_json) == ["J. Hopfield"]


def test_lookup_failure_never_blocks_acquisition(monkeypatch):
    class _DownClient:
        def lookup(self, *, doi=None, title=None):
            raise RuntimeError("network down")

    monkeypatch.setattr(kl_module, "_build_metadata_client", lambda: _DownClient())
    client, engine, _ks, _cs = _make_env()
    source_id = _insert_approved_paper(engine)

    item = _acquire(client, source_id)
    assert item["data_tier"] == "full_text"  # acquisition still succeeded
    assert any("lookup failed" in w for w in item["warnings"])


def test_run_post_acquisition_reports_handler_errors_as_warnings():
    client, engine, _ks, _cs = _make_env()
    source_id = _insert_approved_paper(engine)

    def _broken(source_id):
        raise RuntimeError("handler exploded")

    events.subscribe(events.FULL_TEXT_ACQUIRED, _broken, key="broken")
    warnings = kl_module.run_post_acquisition(source_id, engine)
    assert any("handler exploded" in w for w in warnings)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_api_knowledge_library_postacq.py -q`
Expected: FAIL — `AttributeError: module ... has no attribute '_build_metadata_client'`

- [ ] **Step 3: Add the shared post-acquisition hook**

In `src/neurodb/api/routes/knowledge_library.py`, add `import json` to the stdlib
imports, add `EventLog` to the existing `from neurodb.schema import (...)` list,
and add:

```python
from neurodb.events import FULL_TEXT_ACQUIRED, emit
from neurodb.metadata_backfill import BackfillResult, backfill_paper_metadata
from neurodb.metadata_lookup import MetadataLookupClient
```

After `_commit_chunks` (line ~545), add:

```python
def _build_metadata_client() -> MetadataLookupClient:
    """Seam for tests: monkeypatch to avoid network in the backfill path."""
    return MetadataLookupClient()


def run_post_acquisition(source_id: int, engine: Engine) -> list[str]:
    """Single shared commit point for all acquisition paths (spec workstream 2+3).

    Backfills NULL bibliographic metadata (audited, source-labeled), then emits
    full_text_acquired so the reconciliation handler sees populated authorship.
    Never raises; every failure becomes a warning so acquisition is never blocked.
    """
    warnings: list[str] = []
    try:
        result = backfill_paper_metadata(
            engine, source_id,
            metadata_client=_build_metadata_client(),
            set_fields=lambda **fields: _update_paper_fields(source_id, engine, **fields),
        )
        warnings.extend(result.warnings)
    except Exception as exc:
        logger.exception("metadata backfill failed for source %d", source_id)
        warnings.append(f"metadata backfill failed: {exc}")
        result = BackfillResult(warnings=[str(exc)])
    _log_backfill(engine, source_id, result)
    outcomes = emit(FULL_TEXT_ACQUIRED, source_id=source_id)
    warnings.extend(
        f"reconciliation handler {o['handler']} failed: {o['error']}"
        for o in outcomes if o["status"] == "error"
    )
    return warnings


def _log_backfill(engine: Engine, source_id: int, result: BackfillResult) -> None:
    """Audit row labeling the source of every backfilled value (provenance rule)."""
    try:
        with get_session(engine) as session:
            session.add(EventLog(
                event_name="metadata_backfill",
                entity_id=str(source_id),
                handler="backfill_paper_metadata",
                status="ok" if not result.warnings else "warning",
                detail_json=json.dumps({
                    "filled": result.filled,
                    "values": {k: str(v) for k, v in result.values.items()},
                    "warnings": result.warnings,
                }),
                created_at=datetime.now(UTC).isoformat(),
            ))
    except Exception:
        logger.exception("backfill audit write failed for source %d", source_id)
```

- [ ] **Step 4: Call the hook from the 2a path**

In `acquire_full_text`, the synchronous success branch currently reads (lines ~387-392):

```python
    else:
        _commit_chunks(source_id, engine, chunk_store, sections=result.sections,
                       text_source=result.text_source, title=paper_title, year=paper_year,
                       currency=paper_currency)
        _update_paper_fields(source_id, engine, full_text_status="verified",
                             text_source=result.text_source, data_tier="full_text")
```

Append one line inside that `else`:

```python
        warnings.extend(run_post_acquisition(source_id, engine))
```

- [ ] **Step 5: Call the hook from the review-confirm path**

In `fulltext_review`, after the confirm branch's `_update_paper_fields(...)` call
(ends line ~436), add:

```python
        post_warnings = run_post_acquisition(source_id, engine)
```

and initialize `post_warnings: list[str] = []` before the `if body.decision == "confirm":`
line so the reject branch has it too. Change the final return of `fulltext_review` from

```python
        return _paper_item_from_row(row, session, staged=None)
```

to

```python
        item = _paper_item_from_row(row, session, staged=None)
    return item.model_copy(update={"warnings": post_warnings})
```

(note the dedent: `model_copy` runs after the session closes, matching `acquire_full_text`).

- [ ] **Step 6: Call the hook from the 2b background job**

In `src/neurodb/phase2b.py`, change the signature of `run_acquisition` to:

```python
def run_acquisition(*, source_id: int, engine: Engine,
                    parse: Callable[[], ParsedArtifact | None],
                    commit_chunks: Callable[..., None],
                    set_fields: Callable[..., None] | None = None,
                    on_verified: Callable[[], None] | None = None) -> None:
```

and in the `accept` branch, after the existing
`set_fields(full_text_status="verified", ...)` call, add:

```python
        if on_verified is not None:
            on_verified()
```

In `knowledge_library.py`'s `_run_phase2b_job`, add the argument to the
`run_acquisition(...)` call:

```python
        on_verified=lambda: run_post_acquisition(source_id, engine),
```

(`run_post_acquisition` never raises, so the background job's terminal state is safe.)

- [ ] **Step 7: Register the handler at app startup**

In `src/neurodb/api/app.py` `create_app`, after `app.state.tasks = {}` (line ~28), add:

```python
    from neurodb.reconciliation import register_reconciliation
    register_reconciliation(engine, knowledge_store, chunk_store)
```

(Keyed subscription: repeated `create_app` calls in tests replace, never duplicate.
The registry is module-global, so the most recently created app's stores win — fine
for the single-app runtime; wiring tests register explicitly after `events.reset()`.)

- [ ] **Step 8: Run the new tests plus the touched suites**

Run: `uv run pytest tests/unit/test_api_knowledge_library_postacq.py tests/unit/test_api_knowledge_library.py tests/unit/test_api_knowledge_library_2b.py tests/unit/test_api_knowledge_library_local_file.py tests/unit/test_api_app_factory.py tests/integration/test_phase2b_acquire.py -q`
Expected: all pass

- [ ] **Step 9: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py src/neurodb/phase2b.py \
        src/neurodb/api/app.py tests/unit/test_api_knowledge_library_postacq.py
git commit -m "feat(acquire): shared post-acquisition hook — backfill + FullTextAcquired emit on all three paths"
```

---

### Task 8: One-time reconcile CLI for the existing full-text corpus

The existing 10 full-text papers were acquired before this feature; without a
one-time pass their metadata stays stale and the original bug (author question on
the Hopfield paper) stays broken. Thin CLI entry point per the repo baseline.

**Files:**
- Create: `src/neurodb/cli/reconcile_fulltext.py`
- Test: `tests/unit/test_reconcile_fulltext_cli.py`

**Interfaces:**
- Consumes: `run_post_acquisition` (Task 7), `register_reconciliation` (Task 6), `_build_runtime_stores` from `neurodb.api.app`.
- Produces: `uv run python -m neurodb.cli.reconcile_fulltext [--db PATH] [--dry-run]`.

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_reconcile_fulltext_cli.py`:

```python
"""Tests for the one-time full-text reconcile CLI (dry-run path only; the live
path builds real Chroma stores + embedder and is covered by the manual gate)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.cli.reconcile_fulltext import select_fulltext_papers
from neurodb.db import get_session
from neurodb.schema import Base, Paper


def test_select_fulltext_papers_returns_only_full_text_tier():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        for title, tier in [("Full A", "full_text"), ("Abs B", "abstract"),
                            ("Full C", "full_text")]:
            session.add(Paper(title=title, normalized_title=title.lower(),
                              source_type="paper", topic_context="t",
                              status="approved", queued_at="2026-01-01T00:00:00",
                              data_tier=tier))
    rows = select_fulltext_papers(engine)
    assert [title for _pid, title in rows] == ["Full A", "Full C"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_reconcile_fulltext_cli.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.cli.reconcile_fulltext'`

- [ ] **Step 3: Implement the CLI**

Create `src/neurodb/cli/reconcile_fulltext.py`:

```python
"""One-time backfill + reconciliation for papers that already have full text.

Runs the same shared post-acquisition hook the acquisition paths use, so the
existing corpus catches up with the FullTextAcquired pipeline. Idempotent:
re-running converges to the same state (audit rows append by design).

Usage: uv run python -m neurodb.cli.reconcile_fulltext [--db PATH] [--dry-run]
Note: the live run loads the embedding model to construct the shared stores
(no inference happens — reconciliation is metadata-only), which can take a
minute on CPU-only machines.
"""
from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv


def select_fulltext_papers(engine) -> list[tuple[int, str]]:
    from neurodb.db import get_session
    from neurodb.schema import Paper

    with get_session(engine) as session:
        rows = (
            session.query(Paper.id, Paper.title)
            .filter(Paper.data_tier == "full_text")
            .order_by(Paper.id.asc())
            .all()
        )
    return [(row[0], row[1]) for row in rows]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb"))
    parser.add_argument("--dry-run", action="store_true",
                        help="List target papers without changing anything.")
    args = parser.parse_args()

    import neurodb.connectors  # noqa: F401 — registers connector ORM models
    from neurodb.db import get_engine, init_db

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    targets = select_fulltext_papers(engine)
    print(f"{len(targets)} full-text papers in {args.db}")
    if args.dry_run:
        for paper_id, title in targets:
            print(f"would reconcile {paper_id}: {title}")
        return

    from neurodb.api.app import _build_runtime_stores
    from neurodb.api.routes.knowledge_library import run_post_acquisition
    from neurodb.reconciliation import register_reconciliation

    stores = _build_runtime_stores(args.db, engine)
    register_reconciliation(engine, stores["knowledge_store"], stores["chunk_store"])
    for paper_id, title in targets:
        warnings = run_post_acquisition(paper_id, engine)
        outcome = "ok" if not warnings else f"warnings: {warnings}"
        print(f"reconciled {paper_id}: {title} — {outcome}")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_reconcile_fulltext_cli.py -q`
Expected: 1 passed. Also sanity-check the module loads:
`uv run python -m neurodb.cli.reconcile_fulltext --help` prints usage.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/cli/reconcile_fulltext.py tests/unit/test_reconcile_fulltext_cli.py
git commit -m "feat(cli): one-time reconcile of existing full-text papers through the acquisition hook"
```

---

### Task 9: Library directive detector + deterministic search module

**Files:**
- Create: `src/neurodb/agents/library_directive.py`
- Test: `tests/unit/test_library_directive.py`

**Interfaces:**
- Consumes: `DEFAULT_MIN_SCORE` from `neurodb.agents.full_text_tools` (0.25); duck-typed `chunk_store.search(query, n, min_score)` and `knowledge_store.search(query, n)`.
- Produces (used by Task 10):
  - `LIBRARY_DIRECTIVE_PHRASES: list[str]` — extensible phrase list.
  - `detect_library_directive(message: str) -> bool` — pure.
  - `run_library_search(message: str, *, chunk_store, knowledge_store, n: int = 5) -> dict` — `{"full_text": list[dict], "summaries": list[dict], "full_text_count": int, "summary_count": int}`; summary fallback only when full text is empty.
  - `library_prompt_block(result: dict) -> str` — mandatory-grounding block, full content, explicit empty case.
  - `library_search_event(result: dict) -> dict` — SSE event `{"type": "library_search", "full_text_count", "summary_count", "text"}`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_library_directive.py`:

```python
"""Tests for the explicit Knowledge-Library directive path (workstream 1)."""
from __future__ import annotations

import pytest

from neurodb.agents.library_directive import (
    detect_library_directive,
    library_prompt_block,
    library_search_event,
    run_library_search,
)


@pytest.mark.parametrize("message", [
    "Use the knowledge library to answer this",
    "who does the library say wrote that paper?",
    "search in the KB for hippocampus results",
    "Please look it up in the library.",
    "check the library first",
    "is that in my library?",
])
def test_detector_matches_directive_phrases(message):
    assert detect_library_directive(message) is True


@pytest.mark.parametrize("message", [
    "tell me about neural plasticity",
    "the librarian recommended a book",
    "python library imports are failing",
    "we visited many libraries in Boston",
    "",
])
def test_detector_rejects_near_misses(message):
    assert detect_library_directive(message) is False


class _StubChunkStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, n=5, min_score=0.0):
        self.calls.append({"query": query, "n": n, "min_score": min_score})
        return self.hits


class _StubKnowledgeStore:
    def __init__(self, hits):
        self.hits = hits
        self.calls = []

    def search(self, query, n=5):
        self.calls.append({"query": query, "n": n})
        return self.hits


_PASSAGE = {"chunk_id": "chunk:9:0", "text": "collective abilities emerge",
            "source_id": 9, "title": "Hopfield 1982", "section": "Abstract",
            "score": 0.9}
_SUMMARY = {"id": "knowledge_source:9", "document": "summary body",
            "metadata": {"title": "Hopfield 1982"}, "distance": 0.1}


def test_full_text_hit_skips_summary_fallback():
    chunk_store = _StubChunkStore([_PASSAGE])
    knowledge_store = _StubKnowledgeStore([_SUMMARY])
    result = run_library_search("q", chunk_store=chunk_store,
                                knowledge_store=knowledge_store)
    assert result["full_text_count"] == 1 and result["summary_count"] == 0
    assert knowledge_store.calls == []
    assert chunk_store.calls[0]["min_score"] == 0.25


def test_empty_full_text_falls_back_to_summaries():
    result = run_library_search("q", chunk_store=_StubChunkStore([]),
                                knowledge_store=_StubKnowledgeStore([_SUMMARY]))
    assert result["full_text_count"] == 0 and result["summary_count"] == 1


def test_missing_stores_yield_empty_result():
    result = run_library_search("q", chunk_store=None, knowledge_store=None)
    assert result["full_text_count"] == 0 and result["summary_count"] == 0


def test_prompt_block_carries_full_content_not_just_titles():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([_PASSAGE]),
        knowledge_store=_StubKnowledgeStore([])))
    assert "collective abilities emerge" in block  # passage body, not title-only
    assert "MUST ground" in block


def test_prompt_block_summary_section_carries_document_body():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([]),
        knowledge_store=_StubKnowledgeStore([_SUMMARY])))
    assert "summary body" in block


def test_prompt_block_empty_case_instructs_plain_statement():
    block = library_prompt_block(run_library_search(
        "q", chunk_store=_StubChunkStore([]),
        knowledge_store=_StubKnowledgeStore([])))
    assert "nothing" in block.lower()
    assert "searched" in block.lower()


def test_library_search_event_shape():
    event = library_search_event(run_library_search(
        "q", chunk_store=_StubChunkStore([_PASSAGE]),
        knowledge_store=_StubKnowledgeStore([])))
    assert event["type"] == "library_search"
    assert event["full_text_count"] == 1 and event["summary_count"] == 0
    assert "full-text passages: 1" in event["text"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_library_directive.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.agents.library_directive'`

- [ ] **Step 3: Implement**

Create `src/neurodb/agents/library_directive.py`:

```python
"""Deterministic Knowledge-Library search on explicit user request (workstream 1).

The orchestrator (chat route) — not the model — runs the search on flagged turns
and injects full-content results as an authoritative block. Provider-independent
by construction: no reliance on tool_choice forcing.
"""
from __future__ import annotations

import re

from neurodb.agents.full_text_tools import DEFAULT_MIN_SCORE

# Extensible phrase list; matched case-insensitively on word boundaries.
# Non-deterministic edges are accepted (spec): tune by editing this list.
LIBRARY_DIRECTIVE_PHRASES = [
    "knowledge library",
    "the library",
    "my library",
    "our library",
    "this library",
    "in the kb",
    "the kb",
    "from the library",
    "check the library",
    "look it up in the library",
]

_PATTERNS = [
    re.compile(rf"\b{re.escape(phrase)}\b", re.IGNORECASE)
    for phrase in LIBRARY_DIRECTIVE_PHRASES
]


def detect_library_directive(message: str) -> bool:
    """True when the user explicitly invokes the Knowledge Library. Pure."""
    return any(pattern.search(message or "") for pattern in _PATTERNS)


def run_library_search(message: str, *, chunk_store, knowledge_store,
                       n: int = 5) -> dict:
    """Full-text search first; summary fallback only when full text is empty."""
    full_text: list[dict] = []
    summaries: list[dict] = []
    if chunk_store is not None:
        try:
            full_text = chunk_store.search(message, n=n, min_score=DEFAULT_MIN_SCORE)
        except Exception:
            full_text = []
    if not full_text and knowledge_store is not None:
        try:
            summaries = knowledge_store.search(message, n=n)
        except Exception:
            summaries = []
    return {
        "full_text": full_text,
        "summaries": summaries,
        "full_text_count": len(full_text),
        "summary_count": len(summaries),
    }


def library_prompt_block(result: dict) -> str:
    """Mandatory full-content injection block for a flagged turn."""
    lines = [
        "Knowledge Library results (deterministic search — the user explicitly "
        "asked for the Knowledge Library):",
        "You MUST ground your answer on these results, or state explicitly that "
        "the Knowledge Library was searched and the results were insufficient.",
    ]
    if result["full_text"]:
        lines += ["", f"Full-text passages ({result['full_text_count']}):"]
        for passage in result["full_text"]:
            section = f", {passage['section']}" if passage.get("section") else ""
            lines.append(f'- [{passage["title"]}{section}] "{passage["text"]}"')
    if result["summaries"]:
        lines += ["", f"Summary results ({result['summary_count']}):"]
        for summary in result["summaries"]:
            metadata = summary.get("metadata") or {}
            title = metadata.get("title") or summary.get("id")
            authors = metadata.get("authors") or ""
            byline = f" (authors: {authors})" if authors else ""
            lines.append(f"- [{title}{byline}] {summary.get('document', '')}")
    if not result["full_text"] and not result["summaries"]:
        lines += [
            "",
            "The Knowledge Library was searched for this request and returned "
            "nothing relevant. State plainly that the library was searched and had "
            "nothing relevant; do not imply library support and do not present "
            "training knowledge as if it came from the library.",
        ]
    return "\n".join(lines)


def library_search_event(result: dict) -> dict:
    """SSE event making the deterministic search visible in the UI."""
    return {
        "type": "library_search",
        "full_text_count": result["full_text_count"],
        "summary_count": result["summary_count"],
        "text": (
            "Searched Knowledge Library — full-text passages: "
            f"{result['full_text_count']}, summaries: {result['summary_count']}"
        ),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_library_directive.py -q`
Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/library_directive.py tests/unit/test_library_directive.py
git commit -m "feat(library): directive detector + deterministic search with mandatory-grounding block"
```

---

### Task 10: Chat-route integration + strengthened tutor prompt

**Files:**
- Modify: `src/neurodb/api/routes/chat.py` (flagged-turn hook in `chat_turn` line ~332; `_stream_chat` gains `preamble` line ~177)
- Modify: `src/neurodb/agents/tutor_agent.py` (`_TUTOR_SYSTEM_PROMPT` lines ~106-116)
- Test: `tests/unit/test_api_chat_library.py`

**Interfaces:**
- Consumes: `detect_library_directive`, `run_library_search`, `library_prompt_block`, `library_search_event` (Task 9); `get_research_stores` keys `knowledge_store` / `chunk_store`; `context_bundle["prompt_block"]`.
- Produces: SSE event `{"type": "library_search", "full_text_count": int, "summary_count": int, "text": str}` yielded before any agent output (consumed by Task 11).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_api_chat_library.py`:

```python
"""Tests for deterministic Knowledge-Library search on flagged chat turns."""
from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock, patch

import chromadb
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.api.routes.chat import AgentAttempt, router
from neurodb.chunk_store import ChunkStore
from neurodb.chunking import Chunk
from neurodb.config.task_router import ModelRoute
from neurodb.knowledge_store import KnowledgeLibraryStore
from neurodb.schema import Base


class _StubEmbedder:
    def embed(self, texts):
        return [[0.1, 0.2, 0.3] for _ in texts]


def _make_stores():
    client = chromadb.EphemeralClient()
    chunk_store = ChunkStore(client=client, embedder=_StubEmbedder(),
                             collection_name=f"ck_{uuid.uuid4().hex}")
    knowledge_store = KnowledgeLibraryStore(client=client, embedder=_StubEmbedder(),
                                            collection_name=f"kl_{uuid.uuid4().hex}")
    return chunk_store, knowledge_store


def _make_client(chunk_store, knowledge_store):
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    app = FastAPI()
    app.state.engine = engine
    app.state.vector_store = None
    app.state.knowledge_store = knowledge_store
    app.state.context_store = None
    app.state.chunk_store = chunk_store
    app.include_router(router, prefix="/api")
    return TestClient(app)


def _mock_attempt():
    agent = MagicMock()
    agent.chat.return_value = iter(["grounded answer"])
    route = ModelRoute(task_type="agent.loop.neuro_tutor", tier="standard",
                       provider="anthropic", model_client=MagicMock(),
                       model_id="anthropic-model", max_tokens=2048)
    return AgentAttempt(route=route, agent=agent)


def _events(resp):
    return [json.loads(line[6:]) for line in resp.text.splitlines()
            if line.startswith("data: ")]


def _post(client, message):
    with patch("neurodb.api.routes.chat._build_agent_attempt",
               return_value=_mock_attempt()) as attempt_mock, \
         patch("neurodb.api.routes.chat.build_provider_clients",
               return_value={"anthropic": MagicMock()}):
        resp = client.post("/api/chat/turn", json={
            "message": message, "history": [], "agent_mode": "neuro_tutor"})
    assert resp.status_code == 200
    return _events(resp), attempt_mock


def test_flagged_turn_emits_library_search_first_and_injects_full_content():
    chunk_store, knowledge_store = _make_stores()
    chunk_store.add_chunks(
        paper_id=9, title="Hopfield 1982", year=1982, currency_status="current",
        text_source="pdf_pymupdf",
        chunks=[Chunk(chunk_index=0,
                      text="collective computational abilities emerge",
                      section="Abstract", char_start=0, char_end=42)])
    client = _make_client(chunk_store, knowledge_store)

    events, attempt_mock = _post(
        client, "Use the knowledge library: who wrote about collective computation?")

    library = [e for e in events if e["type"] == "library_search"]
    assert len(library) == 1
    assert library[0]["full_text_count"] == 1
    assert events[0]["type"] == "library_search"  # visible before any content
    bundle = attempt_mock.call_args.args[8]  # context_bundle positional arg
    assert "collective computational abilities emerge" in bundle["prompt_block"]
    assert "MUST ground" in bundle["prompt_block"]


def test_flagged_turn_with_empty_library_injects_empty_state():
    chunk_store, knowledge_store = _make_stores()
    client = _make_client(chunk_store, knowledge_store)

    events, attempt_mock = _post(client, "check the library for lattice QCD")

    library = [e for e in events if e["type"] == "library_search"]
    assert library[0]["full_text_count"] == 0
    assert library[0]["summary_count"] == 0
    bundle = attempt_mock.call_args.args[8]
    assert "nothing relevant" in bundle["prompt_block"]


def test_non_flagged_turn_emits_no_library_search_event():
    chunk_store, knowledge_store = _make_stores()
    client = _make_client(chunk_store, knowledge_store)

    events, _ = _post(client, "explain long-term potentiation")

    assert [e for e in events if e["type"] == "library_search"] == []


def test_tutor_prompt_covers_author_and_content_questions():
    from neurodb.agents.tutor_agent import _TUTOR_SYSTEM_PROMPT

    assert "authors" in _TUTOR_SYSTEM_PROMPT
    assert "Knowledge Library results" in _TUTOR_SYSTEM_PROMPT
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_api_chat_library.py -q`
Expected: FAIL — no `library_search` events emitted; prompt assertions fail

- [ ] **Step 3: Add the flagged-turn hook to `chat_turn`**

In `src/neurodb/api/routes/chat.py`, add to the imports:

```python
from neurodb.agents.library_directive import (
    detect_library_directive,
    library_prompt_block,
    library_search_event,
    run_library_search,
)
```

In `chat_turn`, immediately after the `if body.agent_mode in {"neuro_tutor", "neuro_research"}:` block that builds `context_bundle` (ends line ~345), add:

```python
    library_event: dict | None = None
    if (
        body.agent_mode in {"neuro_tutor", "neuro_research"}
        and detect_library_directive(body.message)
    ):
        library_result = run_library_search(
            body.message,
            chunk_store=stores["chunk_store"],
            knowledge_store=stores["knowledge_store"],
        )
        library_event = library_search_event(library_result)
        if context_bundle is not None:
            context_bundle["prompt_block"] = (
                f"{context_bundle['prompt_block']}\n\n"
                f"{library_prompt_block(library_result)}"
            )
```

Change the final `StreamingResponse` call to pass the preamble:

```python
    return StreamingResponse(
        _stream_chat(
            attempt,
            body.message,
            history,
            fallback_factory=build_attempt,
            preamble=[library_event] if library_event else None,
        ),
        media_type="text/event-stream",
    )
```

- [ ] **Step 4: Yield the preamble in `_stream_chat`**

Change the `_stream_chat` signature to:

```python
def _stream_chat(
    attempt: AgentAttempt,
    message: str,
    history: list[dict],
    fallback_factory: Callable[[set[str]], AgentAttempt] | None = None,
    preamble: list[dict] | None = None,
) -> Generator[str, None, None]:
```

and as the first statements of its body (before `excluded_providers = set()`), add:

```python
    for event in preamble or []:
        yield _sse(event)
```

- [ ] **Step 5: Strengthen the tutor prompt**

In `src/neurodb/agents/tutor_agent.py` `_TUTOR_SYSTEM_PROMPT`, replace the sentence
starting "When the user wants a quotation, specific claim, figure, or method from a
paper, call search_full_text" with:

```python
    "When the user wants a quotation, specific claim, figure, or method from a "
    "paper, or asks what a specific paper or study in the library says, found, or "
    "who its authors are, call search_full_text and quote ONLY text it returns, "
```

(the rest of that sentence — "rendering each quote with its source title and
section." onward — is unchanged), and append to the very end of the prompt string:

```python
    " When the system prompt contains a 'Knowledge Library results' block, treat it "
    "as the authoritative library search for this turn: ground the answer on it, or "
    "state plainly that the Knowledge Library was searched and had nothing "
    "relevant. Never present training knowledge as if it came from the library."
```

- [ ] **Step 6: Run the new tests plus the chat suite**

Run: `uv run pytest tests/unit/test_api_chat_library.py tests/unit/test_api_chat.py tests/unit/test_agent.py -q`
Expected: all pass

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/api/routes/chat.py src/neurodb/agents/tutor_agent.py \
        tests/unit/test_api_chat_library.py
git commit -m "feat(chat): deterministic library search + mandatory injection on flagged turns"
```

---

### Task 11: Frontend notice for the `library_search` event

**Files:**
- Modify: `frontend/src/hooks/useChat.ts` (event union type line ~90-100; dispatch chain line ~166)
- Test: `frontend/src/hooks/useChat.test.ts` (mirror the provider-fallback notice test, line ~152)

**Interfaces:**
- Consumes: SSE `library_search` event from Task 10.
- Produces: a notice on the assistant message (reuses the existing `notices` mechanism rendered for `provider_fallback`). If the notice type declares `failedProvider`/`fallbackProvider` as required, make them optional.

- [ ] **Step 1: Write the failing test**

In `frontend/src/hooks/useChat.test.ts`, after the provider-fallback test (line ~181), add:

```ts
  it('stores library search notices without replacing final answer text', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseResponse([
        {
          type: 'library_search',
          text: 'Searched Knowledge Library — full-text passages: 2, summaries: 0',
          full_text_count: 2,
          summary_count: 0,
        },
        { type: 'done', text: 'Grounded answer.' },
      ]),
    ))
    const { result } = renderHook(() => useChat('neuro_tutor'), { wrapper: makeWrapper() })

    await act(async () => {
      await result.current.sendMessage('use the knowledge library')
    })

    const last = result.current.messages[result.current.messages.length - 1]
    expect(last.content).toBe('Grounded answer.')
    expect(last.notices).toHaveLength(1)
    expect(last.notices?.[0]?.text).toContain('Searched Knowledge Library')
  })
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd frontend && npm test -- useChat`
Expected: FAIL — no notice stored for `library_search`

- [ ] **Step 3: Implement the event branch**

In `frontend/src/hooks/useChat.ts`, add to the inline event type (near `failed_provider?: string`):

```ts
            full_text_count?: number
            summary_count?: number
```

and after the `provider_fallback` branch (ends line ~182), add:

```ts
          } else if (event.type === 'library_search') {
            setMessages(prev => {
              const next = [...prev]
              const last = { ...next[next.length - 1] }
              const notices = [...(last.notices ?? [])]
              notices.push({
                id: `library-search-${notices.length}`,
                text: event.text ?? 'Searched Knowledge Library',
              })
              last.notices = notices
              next[next.length - 1] = last
              return next
            })
```

- [ ] **Step 4: Run frontend tests**

Run: `cd frontend && npm test`
Expected: all pass (fix the notice type to make provider fields optional if the compiler complains)

- [ ] **Step 5: Commit**

```bash
git add frontend/src/hooks/useChat.ts frontend/src/hooks/useChat.test.ts
git commit -m "feat(ui): render searched-library notice from library_search SSE event"
```

---

### Task 12: Full verification + doc sync

**Files:**
- Modify: `docs/projectStatus.md` (active focus + plan-row status)
- Modify: `docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md` (Status line)
- Modify: `docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md` (mark implemented)

- [ ] **Step 1: Run the full backend suite**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those tracked in `docs/testLog.md`. If a pre-existing failure is ambiguous, cross-check `docs/testLog.md` before touching anything.

- [ ] **Step 2: Run lint and the frontend suite**

Run: `uv run ruff check src/ tests/` and `cd frontend && npm test`
Expected: clean / all pass

- [ ] **Step 3: Sync docs**

- Spec: change `Status: Approved design; implementation not started` to
  `Status: Approved design; workstreams 1–3 implemented 2026-07-08 (manual gate pending); workstream 4 future`.
- This plan: append `; implemented 2026-07-08, manual gate pending` to its Status/summary context in `docs/projectStatus.md`'s plan row.
- `docs/projectStatus.md` **Active focus:** prepend the new manual gate:
  `Run the Knowledge Library augmentation manual gate (docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md, KA1–KA4 + KB1–KB4) — includes the one-time uv run python -m neurodb.cli.reconcile_fulltext pass over the existing full-text corpus.` Keep the existing pending gates listed after it.

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md \
        docs/superpowers/specs/2026-07-08-knowledge-library-augmentation-design.md \
        docs/superpowers/plans/2026-07-08-knowledge-library-augmentation.md
git commit -m "docs: knowledge-library augmentation implemented; manual gate active"
```

- [ ] **Step 5: Hand off to the manual gate**

Implementation stops here. The user runs
`docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md` (KA1–KA4, KB1–KB4),
including the one-time CLI pass. Sign-off and archival to
`docs/testsPlans/completedAndPassedTestPlans/` follow the normal process.

---

## Spec coverage map

| Spec requirement | Task(s) |
|---|---|
| W2: external-by-DOI lookup, title fallback | 2 |
| W2: fill only NULL fields, never clobber curated; source labels; lookup failure → warning, never block | 3, 7 |
| W2: called from all three acquisition paths before the event | 7 |
| W2 tests: field selection, DOI vs fallback, integration authors_json, idempotency | 3 (unit), 7 (integration + idempotency) |
| W3: in-process emitter, subscribe/emit, synchronous | 4 |
| W3: reconciliation flips summary `data_tier`, pushes authors into chunk metadata, re-syncs year/currency | 5, 6 |
| W3: idempotent (deterministic ids, merge updates), auditable (`event_log` decision noted in spec) | 1, 6 |
| W3: registration at startup; acquisition emits, never calls reconciliation directly | 7 |
| W3 tests: dispatch, error isolation, stale-tier integration, double-emit idempotency | 4, 6, 7 |
| W1: phrase detector, deterministic search, summary fallback, mandatory full-content injection, empty case | 9 |
| W1: visible searched-library SSE line; provider-independent (orchestrator-run) | 10, 11 |
| W1: strengthened prompt for non-flagged turns | 10 |
| W1 tests: detector, fallback/empty, flagged-turn integration, full-content behavioral | 9, 10 |
| Existing 10 full-text papers catch up (root-cause fix for the Hopfield author question) | 8, manual KA4 |
| Cross-cutting: provenance — source-labeled backfilled values persisted in `metadata_backfill` audit rows | 7 |
| Cross-cutting: manual test plans before implementation, pytest prerequisite step, helper script in `tests/manual/` | 1 |
| W4 reference mining | explicitly out of scope (separate spec) |
