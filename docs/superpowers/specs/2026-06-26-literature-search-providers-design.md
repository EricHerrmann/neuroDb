# Literature-Search Providers: Pluggable Provider Registry + 4 New Sources

- **Date:** 2026-06-26
- **Status:** Design — approved in brainstorming, pending spec review
- **Scope:** Live literature search layer (`literature_client.py`), consumed by the tutor and research agents via the `search_literature` tool.
- **Related (distinct) docs:** `2026-06-02-literature-source-registry-design.md` is the *learning-source catalog* (registered textbooks/papers/datasets), NOT this live-search layer. `2026-06-02-arxiv-search-backend-design.md` added arXiv to the current hardcoded client.

## 1. Problem & Motivation

The tutor and research agents call a single live literature search (`LiteratureSearchClient.search()`) that fans out to three hardcoded providers: PubMed (NCBI E-utilities), Semantic Scholar Graph API, and arXiv. These three are frequently rate-limited or blocked, narrowing recall and producing empty/error envelopes.

We will **broaden coverage** by adding four legitimate, free, programmatic scholarly APIs:

| Provider | Free API | Auth | Citations | Full text / OA | Neuro relevance |
|---|---|---|---|---|---|
| **OpenAlex** | Yes | none (polite pool via `mailto`) | Yes (citation counts) | OA links | High |
| **Europe PMC** | Yes | none | Yes | Yes (OA/PMC full text) | High |
| **Crossref** | Yes | none (polite pool via `mailto`) | Refs (no counts) | OA links via license | High |
| **bioRxiv / medRxiv** | Yes | none | No | Yes (preprint PDFs) | Very high |

Explicitly rejected (technical/legal dead ends or paywalled): Google Scholar, ResearchGate, nature.com, academic.oup.com (scraping/ToS), Web of Science, Scopus (paid institutional licenses).

The current code makes adding a provider expensive: each provider is a private method manually wired into `search()`, into the envelope `providers` dict, and into the `LiteratureSearch` table as a dedicated count column (requiring a migration per provider). This design removes that cost.

## 2. Goals

1. Add OpenAlex, Europe PMC, Crossref, bioRxiv/medRxiv to live search.
2. Refactor to a **base-class + registry** architecture so adding any future provider is a single small subclass with **no duplicated plumbing**. The architecture assumes providers are added regularly; minimizing per-provider effort and duplicate code is a primary design constraint.
3. Keep the agent-facing envelope contract backward compatible.
4. Concurrent fan-out so total latency ≈ slowest provider, not the sum.
5. Merge duplicate records across providers into enriched, citation-ranked results.
6. Env-driven configuration (toggle providers, polite-pool contact email) honoring the `.env`/`load_dotenv()` rule.

## 3. Non-Goals (YAGNI)

- Scraping Google Scholar / ResearchGate / publisher sites.
- Web of Science / Scopus paid APIs.
- Async/`httpx.AsyncClient` refactor.
- Per-provider relevance scoring beyond citation + year ranking.
- UI changes beyond what the existing envelope already renders.

## 4. Architecture

New package `src/neurodb/literature/` (sibling to `connectors/`, mirroring its registry pattern):

```
src/neurodb/literature/
  __init__.py            # public: LiteratureSearchClient
  client.py              # LiteratureSearchClient orchestrator (fan-out, merge, log)
  merge.py               # dedup + enrich-merge + ranking (pure functions)
  registry.py            # build_active_providers(env) -> list[BaseLiteratureProvider]
  providers/
    base.py              # BaseLiteratureProvider (ABC, template method + shared helpers)
    pubmed.py
    semantic_scholar.py
    arxiv.py
    openalex.py          # NEW
    europepmc.py         # NEW
    crossref.py          # NEW
    biorxiv.py           # NEW (bioRxiv + medRxiv)
```

`literature_client.py` is reduced to a thin re-export shim (`from neurodb.literature import LiteratureSearchClient`) so existing imports in `agents/research_agent.py` and `agents/tutor_agent.py` keep working unchanged.

### 4.1 Base class (template-method pattern — eliminates duplicate code)

`BaseLiteratureProvider(ABC)` owns **all shared plumbing as concrete inherited methods**. A new provider implements only the abstract hooks; it never re-writes HTTP, error handling, timeout, polite-pool, truncation, or source-type logic.

```python
class BaseLiteratureProvider(ABC):
    name: str                       # class attribute, e.g. "openalex"

    def __init__(self, http, *, timeout, contact_email=None, api_key=None): ...

    # ---- concrete template method (NOT overridden) ----
    def search(self, query: str, limit: int) -> tuple[list[dict], str | None]:
        """Build request -> fetch -> parse -> normalize, with uniform error capture.
        Returns (results, error). Never raises."""
        try:
            response = self._fetch(query, limit)      # shared HTTP, raise_for_status
            raw = self.parse_response(response)        # provider hook (format-specific)
            return [self.normalize(r) for r in raw], None
        except Exception as exc:
            return [], self._error_message(exc)

    # ---- concrete shared helpers (inherited, reused by every provider) ----
    def _fetch(self, query, limit): ...               # httpx GET; injects mailto/api_key; timeout
    def _with_polite_pool(self, params): ...           # add ?mailto=<contact_email> where applicable
    @staticmethod
    def _truncate(text, limit=300): ...                # moved from current module-level helper
    @staticmethod
    def _doi_url(doi): ...
    @staticmethod
    def _error_message(exc): ...
    @staticmethod
    def _classify_source_type(pub_types, default): ... # review/paper/preprint

    # ---- abstract hooks (the ONLY things a new provider must write) ----
    @property
    @abstractmethod
    def endpoint(self) -> str: ...
    @abstractmethod
    def build_params(self, query: str, limit: int) -> dict: ...
    @abstractmethod
    def parse_response(self, response) -> list[dict]: ...   # XML or JSON -> raw rows
    @abstractmethod
    def normalize(self, raw: dict) -> dict: ...             # raw row -> common schema
```

**Adding a new provider checklist (the design's core success metric):**
1. Create `providers/<name>.py` with a subclass setting `name` + the four hooks.
2. Add the class to the registry list in `registry.py`.
3. Add a unit test with a captured fixture.

No changes to the client, envelope, schema, or a migration. No duplicated HTTP/error/merge code.

### 4.2 Common result schema

Each `normalize()` returns the existing contract plus `sources`:

```python
{
  "title": str,
  "doi": str | None,
  "url": str | None,
  "abstract": str | None,         # truncated via shared helper
  "source_type": "review" | "paper" | "preprint",
  "year": int | None,
  "citation_count": int | None,
  "source": str,                  # the originating provider name (pre-merge)
  "sources": list[str],           # all contributing providers (populated by merge)
}
```

### 4.3 Registry & configuration (env-driven)

`registry.build_active_providers()`:
- Reads (after `load_dotenv()` at entry points, per CLAUDE.md):
  - `NEURODB_CONTACT_EMAIL` — polite-pool contact for OpenAlex (`mailto` query param) and Crossref (`mailto` in params/User-Agent). Falls back to the existing Unpaywall email env var if set.
  - `LITERATURE_PROVIDERS_DISABLED` — comma-separated provider names to exclude.
  - Existing `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY` — passed to the respective providers.
- Instantiates the full provider list, filters out any whose `name` is in the disabled set, returns the active list.
- A disabled or unconfigured provider is simply **absent** from the active list (not an error entry).

### 4.4 Concurrent fan-out

`LiteratureSearchClient.search()`:
- Builds the active provider list once (cached on the client).
- Submits `provider.search(query, over_fetch_limit)` to a `concurrent.futures.ThreadPoolExecutor`, one future per provider, with a per-future timeout (default 10s, reusing `self._timeout`). Retains the sync `httpx.Client`.
- Each provider returns `(results, error)`; a raise or timeout becomes `(results=[], error=<message>)` — one bad provider never fails the batch.
- `over_fetch_limit` = caller `limit` per provider (we trim after merge).

### 4.5 Merge, dedup & ranking (`merge.py`, pure functions)

1. **Dedup key:** normalized DOI if present; else `normalize(title) + "|" + str(year)`. `normalize(title)` = lowercased, whitespace-collapsed, punctuation-stripped.
2. **Enrich-merge** of records sharing a key:
   - `abstract`: longest non-empty.
   - `citation_count`: `max` of non-null values (else None).
   - `source_type`: most specific (`review` > `paper` > `preprint`).
   - `url`: prefer a non-None, non-DOI-only URL; else DOI URL.
   - `sources`: union of all contributing provider names (sorted, stable).
   - `source`: kept as the first contributor for back-compat.
3. **Ranking:** `citation_count` desc (None sorts last), then `year` desc (None last), then title asc for stability.
4. **Trim** to caller `limit` after ranking.

### 4.6 Envelope contract (backward compatible)

```python
{
  "query": str,
  "result_count": int,            # post-merge, post-trim
  "results": list[dict],          # merged, ranked, trimmed
  "providers": {                  # built dynamically from active providers
     "<name>": {"status": "ok"|"error", "count": int, "error": str|None},
     ...
  },
}
```

Agents already read `result_count`, `results`, and `providers[*].status`; no agent change required. The `providers` dict simply gains keys for newly active providers.

### 4.7 Audit schema (`LiteratureSearch`)

- **Add** nullable `provider_counts_json` (TEXT): `{"pubmed": 5, "openalex": 8, ...}` for every active provider that ran.
- **Keep** existing `pubmed_count`, `semantic_scholar_count`, `arxiv_count` nullable for back-compat; populate them when those providers run (mirrored from the JSON), else null.
- One additive migration registered in the `db/` migration registry. No per-provider column is ever added again.
- `results_json` continues to store the merged result list.
- `research_tools.py` (`session.query(LiteratureSearch).count()`) is unaffected.

## 5. Data Flow

```
agent.search_literature(query)
  -> LiteratureSearchClient.search(query, limit)
       -> registry.build_active_providers(env)            # cached
       -> ThreadPoolExecutor: provider.search() x N       # concurrent, per-provider timeout
            -> base.search(): _fetch -> parse_response -> normalize  (per provider)
       -> merge.dedup_and_merge(all_results)              # DOI/title key, enrich, rank, trim
       -> _log_search(query, provider_counts, merged)     # provider_counts_json + results_json
       -> envelope{query, result_count, results, providers}
  -> agent indexes results (existing _index_literature_results path)
```

## 6. Error Handling

- Provider-level: any exception/timeout → `([], error)`; surfaced in `providers[name]` as `status:"error"`. Empty-but-successful is `status:"ok", count:0` (preserves the existing "no matches" vs "failed" distinction).
- Client-level: if the executor itself fails, return an envelope with all providers marked error rather than raising into the agent loop.
- Missing contact email: OpenAlex/Crossref still work (common pool) but without polite-pool benefits; not an error.

## 7. Testing (contracts -> failing tests -> implementation, per CLAUDE.md)

### 7.1 Automated (unit)

- **Per provider (7):** captured fixture (XML for pubmed/arxiv/crossref; JSON for the rest) → assert `parse_response` + `normalize` produce the common schema, correct `source`, `source_type`, `year`, `citation_count`, DOI extraction. No live network. Extends existing `tests/unit/test_literature_client.py` style.
- **Base class:** `search()` template captures provider exceptions as `([], error)`; `_with_polite_pool` adds `mailto` only when email present; shared helpers (`_truncate`, `_doi_url`, `_classify_source_type`) behavior.
- **Registry/config:** `LITERATURE_PROVIDERS_DISABLED` removes named providers; missing email → no `mailto`; active-provider set drives envelope keys.
- **Merge (`merge.py`):** dedup by DOI; dedup by title+year fallback when DOI absent; enrich-merge picks longest abstract / max citation_count / union of sources / most-specific source_type; ranking order (citation desc, year desc); trim to limit.
- **Fan-out:** one provider raising and one timing out → both `status:"error"`, remaining providers still contribute (batch does not fail).
- **Idempotency (CLAUDE.md):** re-running the same search does not duplicate indexed result records via the existing `_index_literature_results` path; `provider_counts_json` is overwritten/append-row consistently.
- **Migration:** `provider_counts_json` column present after migration; old rows readable (column nullable).

### 7.2 Manual test plan (phase-gate artifact)

Create `docs/testsPlans/manualTestPlan_literature_search_providers.md` **before** implementation. Requirements:
- **Prerequisites step 1 (mandatory):** run `uv run pytest tests/ -q`; pass = no new failures beyond `docs/testLog.md`.
- **Prerequisites — provider connectivity confirmation (operator):** before functional steps, the operator confirms live reachability of **each** provider and that any required account/email/API key is present and valid:
  - `NEURODB_CONTACT_EMAIL` set (OpenAlex/Crossref polite pool); `NCBI_API_KEY` (optional, PubMed); `SEMANTIC_SCHOLAR_API_KEY` (optional).
  - A one-line reachability check per provider (PubMed, Semantic Scholar, arXiv, OpenAlex, Europe PMC, Crossref, bioRxiv/medRxiv), via a checked-in helper script under `tests/manual/`. Record HTTP 200 + non-empty response per provider; note any provider returning auth/rate-limit errors so it can be set in `LITERATURE_PROVIDERS_DISABLED` for the run.
- **Functional (browser/real-wiring, not duplicating units):** run a real neuroscience query (e.g., "synaptic plasticity LTP") through the tutor/research agent; verify merged cross-provider results, citation-ranked ordering, `sources` provenance showing multiple contributors, and graceful behavior when one provider is disabled.
- Long/multi-line commands live in `tests/manual/` helper scripts; the plan references them by short command and documents inputs, expected output, pass/fail.

### 7.3 API verification at plan time

Exact endpoints, params, and response fields for OpenAlex, Europe PMC, Crossref, and bioRxiv/medRxiv will be confirmed via context7 / live API docs during the implementation-plan step — not assumed from memory. Current rate limits and terms re-checked then.

## 8. Project-State Sync (CLAUDE.md rules)

In the implementing commits:
- Add `docs/testsPlans/manualTestPlan_literature_search_providers.md` to `docs/projectStatus.md` when the plan file is first created (source-document + active-test-plan sync).
- Update phase row / test count / active focus as those change.
- On terminal (passing/signed-off) state of the manual plan, move it to the archived plans table and update phase row + active focus in the same step.

## 9. Open Questions

None blocking. Endpoint/field specifics deferred to plan-time API verification (§7.3).
