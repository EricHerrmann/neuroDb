# arXiv Literature Search Backend — Design

- **Date:** 2026-06-02
- **Status:** Approved (design)
- **Component:** `src/neurodb/literature_client.py`, `src/neurodb/schema.py`, `src/neurodb/db.py`, `src/neurodb/agents/tutor_agent.py`, `src/neurodb/agents/research_agent.py`

## Goal

Add arXiv as a third live literature-search backend, alongside PubMed and
Semantic Scholar, so the tutor's `search_literature` tool surfaces arXiv
preprints automatically. arXiv results are labeled as a distinct `preprint`
source type to preserve the not-peer-reviewed signal the project's
trustworthiness goals depend on.

## Approach

Mirror the existing PubMed / Semantic Scholar pattern exactly: a self-contained
backend method plus a pure XML normalizer, fanned out from
`LiteratureSearchClient.search()`. No new abstraction — arXiv slots in as a peer
of the other two backends.

## Design

### 1. New backend — `_search_arxiv(query, limit)`

In `literature_client.py`. Calls the arXiv Atom API:

```
http://export.arxiv.org/api/query?search_query=all:<query>&start=0&max_results=<limit>
```

Uses the same `try/except → return []` graceful-degradation pattern as the other
two backends, reusing `self._http` and `self._timeout`. An arXiv outage must
never break a search — the other sources still return.

### 2. Pure normalizer — `_parse_arxiv_xml(xml_text)`

Parses Atom `<entry>` elements into the same normalized dict shape the other
backends emit:

| Field            | Source                                                        |
| ---------------- | ------------------------------------------------------------- |
| `title`          | `<title>`                                                     |
| `doi`            | `<arxiv:doi>` if present (published version), else `None`     |
| `url`            | abs page, `https://arxiv.org/abs/<id>` (source-page URL)      |
| `abstract`       | `<summary>`, run through existing `_truncate`                 |
| `source_type`    | `"preprint"` (new type)                                       |
| `year`           | parsed from `<published>`                                     |
| `citation_count` | `None` (arXiv does not provide it)                            |
| `source`         | `"arxiv"`                                                     |

The `url` uses the abstract page (the source page), consistent with the existing
URL convention: prefer the source landing page, fall back to the DOI resolver.
Since the abs page is always available for an arXiv entry, no fallback is needed.

### 3. Wire into `search()`

Add `arxiv_results` to the fan-out. Merge order: `pubmed + semantic + arxiv`.
Dedup stays `_dedup_by_doi` (DOI-only, unchanged). A no-DOI preprint may appear
alongside its later published version; this is accepted behavior. arXiv entries
that carry a `<arxiv:doi>` dedup naturally.

### 4. Per-source count + schema

- `_log_search` gains an `arxiv_count` argument.
- Add an `arxiv_count` column to the `LiteratureSearch` model
  (`schema.py`, near `semantic_scholar_count`): `Integer, nullable=False, default=0`.
- New **migration 020** — `_migration_020_literature_search_arxiv_count`:
  `ALTER TABLE literature_searches ADD COLUMN arxiv_count INTEGER DEFAULT 0`,
  using the same try/except-idempotent pattern as migration 015. Register it in
  `_MIGRATIONS` in `db.py`.

### 5. Register `preprint` as a valid source_type

`source_type` is a free-text column (no DB enum), so this is only updating the
human-facing allowed-values lists so the agents can queue preprints:

- `tutor_agent.py` `queue_source` description → "One of: paper, review,
  preprint, textbook, website."
- `research_agent.py` matching source-type description string.
- `tutor_agent.py` system-prompt resource list — add "preprint".

UI filters that bucket `source_type == "paper"` (RegistryPanel, learning_registry)
are intentionally untouched: preprints are not peer-reviewed papers, so excluding
them from that bucket is correct.

## Testing (TDD)

In `tests/unit/test_literature_client.py` plus a migration test:

- `_parse_arxiv_xml`: title / abstract / year; `url` = abs page;
  `source_type == "preprint"`; `doi` populated when `<arxiv:doi>` present and
  `None` when absent.
- `search()` merges all three backends and logs `arxiv_count`.
- arXiv timeout degrades gracefully (returns the other sources).
- Migration 020: idempotent re-run; `arxiv_count` column exists after apply.

A captured arXiv Atom XML fixture is pinned for the parser tests.

## Out of Scope (YAGNI)

- Title-based cross-source deduplication.
- Citation counts for arXiv results.
- Any UI surface for browsing preprints specifically.

## Notes

The global engineering rule to verify third-party API contracts via context7
applies to packaged libraries. arXiv's API is a plain Atom/HTTP endpoint, so the
response shape is confirmed against captured/live XML and pinned as a test
fixture rather than via context7.
