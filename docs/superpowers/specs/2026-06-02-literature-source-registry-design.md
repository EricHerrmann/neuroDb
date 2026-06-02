# Literature Source Backend Registry — Design

- **Date:** 2026-06-02
- **Status:** Design approved; implementation deferred (see Sequencing)
- **Epoch:** Tutor (`src/neurodb/literature_client.py`, migration target `src/neurodb/tutor/`)
- **Tracked under:** Tech Debt **TD-5** (Reusable Abstractions and Extension Points)
- **Driver:** Adding a neuroscience literature source currently touches ~5 files beyond the irreducible per-source code.

## Problem

Adding arXiv (commits `faadc12`..`b90e972`) required changes in seven files. Only
two represent irreducible per-source work; the other five are accidental coupling:

| Change | Per-source? | Notes |
| --- | --- | --- |
| API client method (`_search_arxiv`) | **Irreducible** | Every source has a distinct endpoint/auth/query. |
| Response normalizer (`_parse_arxiv_xml`) | **Irreducible** | Every source returns a distinct schema. |
| New `arxiv_count` column + DB migration | Accidental | A new source should not require a schema migration. |
| Hardcoded fan-out in `search()` | Accidental | `search()` names each `_search_X` explicitly. |
| `_log_search` signature grows an argument | Accidental | One positional count per source. |
| `source_type` allowed-values string ×2 (tutor + research agents) | Accidental | Duplicated literal lists. |

There are now **three** concrete backends (PubMed, Semantic Scholar, arXiv). Three
implementations is the evidence threshold TD-5 requires for extraction — this is no
longer a premature abstraction.

**Goal:** adding a future source (BioRxiv, OpenAlex, …) becomes **one new file plus
one registration line** — no schema change, no `search()`/logging edits, no agent edits.

## Design

### 1. `SourceBackend` protocol

```python
from typing import Protocol

class SourceBackend(Protocol):
    name: str  # stable id, e.g. "pubmed", "semantic_scholar", "arxiv"

    def search(self, query: str, limit: int) -> list[dict]:
        """Return normalized result dicts; MUST catch its own errors and
        return [] on failure (graceful degradation stays inside the backend)."""
```

Each backend is a small class owning its HTTP usage and parsing, emitting the
existing normalized shape: `title, doi, url, abstract, source_type, year,
citation_count, source`. The `source` field equals `name`.

Backends receive the shared `http` client and `timeout` via constructor injection
so tests inject a fake HTTP client per backend.

### 2. Registry + generic fan-out

`LiteratureSearchClient` holds an injectable list of backends:

```python
def __init__(self, engine, http_client=None, timeout=5.0, backends=None):
    self._http = http_client or httpx.Client(timeout=timeout)
    self._backends = backends or [
        PubMedBackend(self._http, timeout),
        SemanticScholarBackend(self._http, timeout),
        ArxivBackend(self._http, timeout),
    ]

def search(self, query: str, limit: int = 10) -> list[dict]:
    merged: list[dict] = []
    counts: dict[str, int] = {}
    for backend in self._backends:
        rows = backend.search(query, limit)
        counts[backend.name] = len(rows)
        merged.extend(rows)
    results = _dedup_by_doi(merged)
    self._log_search(query, counts, results)
    return results
```

Adding a source = append one backend to the default list. Dedup stays DOI-only.

### 3. Logging: single `source_counts` JSON column

Replace `pubmed_count` / `semantic_scholar_count` / `arxiv_count` with one
`source_counts` column (Text holding JSON), e.g. `{"pubmed": 1, "semantic_scholar":
2, "arxiv": 3}`. `_log_search(query, counts: dict, results)` serializes it.

Migration (next free number at implementation time — likely 021+):
1. `ALTER TABLE literature_searches ADD COLUMN source_counts TEXT`.
2. Backfill existing rows: `source_counts = json({"pubmed": pubmed_count,
   "semantic_scholar": semantic_scholar_count, "arxiv": arxiv_count})`.
3. Drop the three legacy count columns (single-user local DB; no external reader —
   see Blast Radius).

After this, a new source contributes a new JSON key automatically; no further
migration is ever required for source counts.

**Blast radius (verified 2026-06-02):** the only readers of the legacy count columns
are `schema.py` (the model) and `tests/unit/test_knowledge_schema.py`. No analytics,
API, or UI consumes them. The schema test updates to assert `source_counts`.

### 4. Centralize `source_type` values

Define one constant (e.g. `LITERATURE_SOURCE_TYPES = ("paper", "review",
"preprint", "textbook", "website")`) consumed by both the tutor and research agent
`queue_source` tool descriptions, so a new type is declared once.

### 5. File structure

Promote the single module to a small package, taking the already-noted Tutor-epoch
migration (`literature_client.py` header: "Migration target: src/neurodb/tutor/…"):

```
src/neurodb/tutor/literature/
  __init__.py        # re-exports LiteratureSearchClient for back-compat imports
  client.py          # registry + search() + _log_search
  backends/
    base.py          # SourceBackend protocol + shared helpers (_truncate, _text, _doi_url, _dedup_by_doi)
    pubmed.py        # PubMedBackend + _parse_pubmed_xml
    semantic_scholar.py
    arxiv.py
```

Keep a thin shim at the old import path during transition so existing imports do not
break in one step.

## Testing

- Per-backend parser tests (migrate the existing PubMed/Semantic Scholar/arXiv tests
  into per-backend modules; behavior unchanged).
- Registry test: inject a list of fake backends, assert fan-out, `source_counts`,
  dedup, and that one backend raising does not break the others.
- Back-compat test: `search()` returns the same merged result shape as today.
- Migration test: `source_counts` backfilled correctly from legacy columns; idempotent.

## Acceptance Criteria (TD-5 aligned)

- Adding a literature source requires one new backend file + one registry line —
  no schema migration, no `search()`/`_log_search` signature change, no agent edits.
- Each backend is independently unit-testable at its boundary.
- The refactor removes the per-source count columns (duplicated behavior across ≥2
  call sites) and at least one consumer test is updated.
- Behavior parity: existing literature-search results and logging are preserved.

## Sequencing (deferred — do NOT start before these complete)

This refactor is scheduled **after** both in-flight efforts finish, to avoid
migration-number churn (Groupings Phase 5 drops legacy tables) and to keep focus:

1. **Unified Groupings**: Phase 4 manual sign-off **and** Phase 5 legacy-table
   retirement complete.
2. **Research Question Phase 1**: complete.

When both are done, lift this spec into an implementation plan (`writing-plans`)
and execute. Until then it remains a recorded TD-5 candidate.

## Out of Scope

- Per-source citation enrichment or cross-source title dedup (separate concerns).
- A generic plugin-discovery/entry-point system — the in-repo registry list is
  sufficient for a single-user local platform (YAGNI).
- Config-file-driven enabling/disabling of sources (revisit only if a real need
  appears).
