# Literature-Search Providers Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Refactor the live literature-search layer into a base-class + registry architecture and add four free scholarly providers (OpenAlex, Europe PMC, Crossref, bioRxiv/medRxiv).

**Architecture:** A `BaseLiteratureProvider` ABC owns all shared plumbing (HTTP, error capture, timeout, polite-pool email, truncation, source-type classification) via a concrete `search()` template method; each provider implements four small hooks. A registry builds the active provider list from env config. `LiteratureSearchClient` fans out concurrently across active providers (thread pool), merges/dedups/ranks results, and logs per-provider counts as JSON.

**Tech Stack:** Python, httpx (sync `Client`), `concurrent.futures.ThreadPoolExecutor`, SQLAlchemy ORM over DuckDB, pytest, python-dotenv.

## Global Constraints

- Common result schema (every `normalize()` returns these keys): `title: str`, `doi: str|None`, `url: str|None`, `abstract: str|None`, `source_type: "review"|"paper"|"preprint"`, `year: int|None`, `citation_count: int|None`, `source: str`, `sources: list[str]`.
- Provider `search(query, limit) -> tuple[list[dict], str|None]` MUST never raise; failures return `([], error_message)`.
- Envelope contract (unchanged for agents): `{"query": str, "result_count": int, "results": list[dict], "providers": {name: {"status": "ok"|"error", "count": int, "error": str|None}}}`.
- `load_dotenv()` already called at entry points; modules read env via `os.environ`/`os.getenv` only (no new entry points added). Per CLAUDE.md, never read secrets without a preceding `load_dotenv()` at the entry point.
- Existing imports `from neurodb.literature_client import LiteratureSearchClient` (in `agents/research_agent.py`, `agents/tutor_agent.py`) MUST keep working — `literature_client.py` becomes a re-export shim.
- httpx pinned `>=0.28.1,<1.0`; no new third-party dependencies.
- Provider `name` values are stable lowercase identifiers: `pubmed`, `semantic_scholar`, `arxiv`, `openalex`, `europepmc`, `crossref`, `biorxiv`.
- Contact email env var: `NEURODB_CONTACT_EMAIL`, falling back to `UNPAYWALL_EMAIL` if set. Disabled providers env var: `LITERATURE_PROVIDERS_DISABLED` (comma-separated names).
- Per-provider HTTP timeout default 10.0s. Each provider fetches `limit` rows; the client trims the merged list to `limit` after ranking.
- Tests use a fake HTTP object exposing `.get(url, params=..., headers=..., timeout=...)` returning an object with `.json()`, `.text`, `.headers`, and `.raise_for_status()` (mirror existing `tests/unit/test_literature_client.py` `_FakeHttp`/`_Response`).

## File Structure

- Create `src/neurodb/literature/__init__.py` — public export of `LiteratureSearchClient`.
- Create `src/neurodb/literature/providers/__init__.py` — empty package marker.
- Create `src/neurodb/literature/providers/base.py` — `BaseLiteratureProvider` ABC + shared helpers.
- Create `src/neurodb/literature/providers/pubmed.py`, `semantic_scholar.py`, `arxiv.py`, `openalex.py`, `europepmc.py`, `crossref.py`, `biorxiv.py`.
- Create `src/neurodb/literature/merge.py` — `dedup_and_merge(results, limit)`.
- Create `src/neurodb/literature/registry.py` — `build_active_providers(http, *, timeout)`.
- Create `src/neurodb/literature/client.py` — `LiteratureSearchClient`.
- Modify `src/neurodb/literature_client.py` — reduce to shim re-exporting from `neurodb.literature`.
- Modify `src/neurodb/schema.py:335-345` — add `provider_counts_json` column.
- Modify `src/neurodb/db.py` — add `_migration_026_literature_provider_counts` + register in `_MIGRATIONS`.
- Modify `src/neurodb/db/__init__.py` — re-export `_migration_026_literature_provider_counts`.
- Create tests under `tests/unit/` and `tests/integration/`.
- Create `tests/manual/check_literature_providers.py` — connectivity helper.
- Create `docs/testsPlans/manualTestPlan_literature_search_providers.md`.
- Modify `docs/projectStatus.md` — register the manual test plan + active focus.

---

### Task 1: Base provider class + shared helpers

**Files:**
- Create: `src/neurodb/literature/__init__.py`
- Create: `src/neurodb/literature/providers/__init__.py`
- Create: `src/neurodb/literature/providers/base.py`
- Test: `tests/unit/test_literature_base.py`

**Interfaces:**
- Consumes: nothing (foundation task).
- Produces:
  - `BaseLiteratureProvider(http, *, timeout=10.0, contact_email=None, api_key=None)` with class attrs `name: str`, `uses_polite_pool: bool = False`.
  - Concrete: `search(query: str, limit: int) -> tuple[list[dict], str|None]`, `_fetch(query, limit) -> response`, `_with_polite_pool(params: dict) -> dict`, static `_truncate(text, limit=300) -> str|None`, static `_doi_url(doi) -> str|None`, static `_error_message(exc) -> str`, static `_classify_source_type(pub_types: list[str], default: str) -> str`.
  - Abstract: `endpoint -> str` (property), `build_params(query, limit) -> dict`, `parse_response(response) -> list[dict]`, `normalize(raw: dict) -> dict`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_literature_base.py
from neurodb.literature.providers.base import BaseLiteratureProvider


class _Resp:
    def __init__(self, json_data=None, text="", headers=None):
        self._json = json_data
        self.text = text
        self.headers = headers or {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp=None, raise_exc=None):
        self.resp = resp
        self.raise_exc = raise_exc
        self.last_params = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.last_params = params
        if self.raise_exc:
            raise self.raise_exc
        return self.resp


class _Fake(BaseLiteratureProvider):
    name = "fake"
    uses_polite_pool = True

    @property
    def endpoint(self):
        return "https://example.test/search"

    def build_params(self, query, limit):
        return {"q": query, "n": limit}

    def parse_response(self, response):
        return response.json()["rows"]

    def normalize(self, raw):
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": self._classify_source_type(raw.get("types", []), "paper"),
            "year": raw.get("year"),
            "citation_count": raw.get("cites"),
            "source": self.name,
            "sources": [self.name],
        }


def test_search_returns_normalized_rows():
    http = _Http(resp=_Resp(json_data={"rows": [{"title": "T", "doi": "10.1/x", "year": 2020}]}))
    provider = _Fake(http, contact_email="me@example.com")
    results, error = provider.search("ltp", 5)
    assert error is None
    assert results[0]["title"] == "T"
    assert results[0]["source"] == "fake"
    assert results[0]["url"] == "https://doi.org/10.1/x"


def test_search_captures_exception_as_error():
    http = _Http(raise_exc=RuntimeError("boom"))
    provider = _Fake(http)
    results, error = provider.search("ltp", 5)
    assert results == []
    assert "boom" in error


def test_polite_pool_adds_mailto_when_email_present():
    http = _Http(resp=_Resp(json_data={"rows": []}))
    provider = _Fake(http, contact_email="me@example.com")
    provider.search("ltp", 5)
    assert http.last_params.get("mailto") == "me@example.com"


def test_polite_pool_absent_without_email():
    http = _Http(resp=_Resp(json_data={"rows": []}))
    provider = _Fake(http, contact_email=None)
    provider.search("ltp", 5)
    assert "mailto" not in http.last_params


def test_classify_source_type_prefers_review():
    assert _Fake.__mro__  # provider class importable
    p = _Fake(_Http(resp=_Resp(json_data={"rows": []})))
    assert p._classify_source_type(["Journal Article", "Review"], "paper") == "review"
    assert p._classify_source_type(["Journal Article"], "paper") == "paper"


def test_truncate_collapses_and_limits():
    assert _Fake._truncate("  a   b  ") == "a b"
    assert _Fake._truncate("x" * 400).endswith("...")
    assert _Fake._truncate("") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_base.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'neurodb.literature'`.

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/literature/__init__.py
"""Live literature-search layer: base-class + registry of search providers."""
from neurodb.literature.client import LiteratureSearchClient

__all__ = ["LiteratureSearchClient"]
```

```python
# src/neurodb/literature/providers/__init__.py
```

```python
# src/neurodb/literature/providers/base.py
"""Base class for live literature-search providers (template-method pattern).

Subclasses implement four hooks (endpoint, build_params, parse_response,
normalize). All HTTP, error capture, timeout, polite-pool, and normalization
helpers live here so adding a provider never duplicates plumbing.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class BaseLiteratureProvider(ABC):
    name: str = "base"
    uses_polite_pool: bool = False

    def __init__(
        self,
        http: Any,
        *,
        timeout: float = 10.0,
        contact_email: str | None = None,
        api_key: str | None = None,
    ) -> None:
        self._http = http
        self._timeout = timeout
        self._contact_email = contact_email
        self._api_key = api_key

    # ---- concrete template method (do not override) ----
    def search(self, query: str, limit: int) -> tuple[list[dict], str | None]:
        try:
            response = self._fetch(query, limit)
            raw_rows = self.parse_response(response)
            return [self.normalize(row) for row in raw_rows], None
        except Exception as exc:  # providers must never raise
            return [], self._error_message(exc)

    # ---- concrete shared helpers ----
    def _fetch(self, query: str, limit: int):
        params = self._with_polite_pool(self.build_params(query, limit))
        response = self._http.get(
            self.endpoint,
            params=params,
            headers=self._headers(),
            timeout=self._timeout,
        )
        response.raise_for_status()
        return response

    def _headers(self) -> dict:
        return {}

    def _with_polite_pool(self, params: dict) -> dict:
        if self.uses_polite_pool and self._contact_email:
            params = {**params, "mailto": self._contact_email}
        return params

    @staticmethod
    def _truncate(text: str, limit: int = 300) -> str | None:
        value = " ".join((text or "").split())
        if not value:
            return None
        if len(value) <= limit:
            return value
        return f"{value[: limit - 3]}..."

    @staticmethod
    def _doi_url(doi: str | None) -> str | None:
        doi = (doi or "").strip()
        return f"https://doi.org/{doi}" if doi else None

    @staticmethod
    def _error_message(exc: Exception) -> str:
        return f"{type(exc).__name__}: {exc}"

    @staticmethod
    def _classify_source_type(pub_types: list[str], default: str) -> str:
        lowered = [str(value).lower() for value in pub_types or []]
        if any("review" in value for value in lowered):
            return "review"
        return default

    # ---- abstract hooks ----
    @property
    @abstractmethod
    def endpoint(self) -> str: ...

    @abstractmethod
    def build_params(self, query: str, limit: int) -> dict: ...

    @abstractmethod
    def parse_response(self, response) -> list[dict]: ...

    @abstractmethod
    def normalize(self, raw: dict) -> dict: ...
```

Note: `__init__.py` imports `client`, which does not exist yet. For this task only, temporarily make `src/neurodb/literature/__init__.py` empty (no import) so the base tests run; Task 6 adds the `client` import. Replace the file content above with just the docstring + `__all__ = []` until Task 6.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_literature_base.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/__init__.py src/neurodb/literature/providers/__init__.py src/neurodb/literature/providers/base.py tests/unit/test_literature_base.py
git commit -m "feat(lit): base literature provider class with shared helpers"
```

---

### Task 2: Migration 026 + schema column for provider_counts_json

**Files:**
- Modify: `src/neurodb/schema.py:335-345`
- Modify: `src/neurodb/db.py` (add `_migration_026_literature_provider_counts`, register at key 26)
- Modify: `src/neurodb/db/__init__.py:50` (re-export)
- Test: `tests/unit/test_migration_026.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `LiteratureSearch.provider_counts_json: Mapped[str|None]` column; migration `_migration_026_literature_provider_counts(conn)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_migration_026.py
from sqlalchemy import create_engine, text

from neurodb import db as dbpkg


def test_migration_026_adds_provider_counts_json_column():
    engine = create_engine("duckdb:///:memory:")
    dbpkg.init_db(engine)  # runs create_all + all migrations
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info('literature_searches')")).fetchall()
    names = {row[1] for row in cols}
    assert "provider_counts_json" in names


def test_migration_026_registered():
    assert 26 in dbpkg._MIGRATIONS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_026.py -q`
Expected: FAIL (`26` not in `_MIGRATIONS`; column missing).

- [ ] **Step 3: Write minimal implementation**

In `src/neurodb/schema.py`, add the column after `results_json` (line ~344):

```python
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    provider_counts_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    searched_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

In `src/neurodb/db.py`, add the migration function near `_migration_025_phase2b`:

```python
def _migration_026_literature_provider_counts(conn) -> None:
    """Add JSON per-provider counts column to literature_searches (dynamic providers)."""
    try:
        conn.execute(
            text("ALTER TABLE literature_searches ADD COLUMN provider_counts_json TEXT")
        )
    except Exception:
        pass  # column already exists
```

Register it in the `_MIGRATIONS` dict (after key 25):

```python
    25: _migration_025_phase2b,
    26: _migration_026_literature_provider_counts,
}
```

In `src/neurodb/db/__init__.py`, after line 50 add:

```python
_migration_026_literature_provider_counts = _db_legacy._migration_026_literature_provider_counts
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_026.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py src/neurodb/db/__init__.py tests/unit/test_migration_026.py
git commit -m "feat(lit): add provider_counts_json column + migration 026"
```

---

### Task 3: Port existing providers (PubMed, Semantic Scholar, arXiv) onto the base class

**Files:**
- Create: `src/neurodb/literature/providers/pubmed.py`
- Create: `src/neurodb/literature/providers/semantic_scholar.py`
- Create: `src/neurodb/literature/providers/arxiv.py`
- Test: `tests/unit/test_providers_existing.py`

**Interfaces:**
- Consumes: `BaseLiteratureProvider` (Task 1).
- Produces: `PubmedProvider`, `SemanticScholarProvider`, `ArxivProvider` (each `name` set; constructor signature inherited).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_providers_existing.py
from neurodb.literature.providers.pubmed import PubmedProvider
from neurodb.literature.providers.semantic_scholar import SemanticScholarProvider
from neurodb.literature.providers.arxiv import ArxivProvider

PUBMED_SEARCH = {"esearchresult": {"idlist": ["123"]}}
PUBMED_XML = """<?xml version="1.0"?>
<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
<ArticleTitle>LTP and memory</ArticleTitle>
<Abstract><AbstractText>LTP is plasticity.</AbstractText></Abstract>
<Journal><JournalIssue><PubDate><Year>2024</Year></PubDate></JournalIssue></Journal>
<PublicationTypeList><PublicationType>Review</PublicationType></PublicationTypeList>
<ELocationID EIdType="doi">10.1000/ltp</ELocationID>
</Article></MedlineCitation></PubmedArticle></PubmedArticleSet>"""

S2_JSON = {"data": [{"title": "S2 paper", "abstract": "abc", "year": 2022,
                     "citationCount": 9, "externalIds": {"DOI": "10.5/s2"},
                     "publicationTypes": ["JournalArticle"], "url": "https://s2/abc"}]}

ARXIV_XML = """<?xml version="1.0"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
<entry><id>http://arxiv.org/abs/2401.01234v1</id><published>2024-01-15T10:00:00Z</published>
<title>Predictive coding</title><summary>preprint</summary>
<arxiv:doi>10.1/arx</arxiv:doi></entry></feed>"""


class _Resp:
    def __init__(self, json_data=None, text=""):
        self._json = json_data
        self.text = text
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _RouteHttp:
    """Routes by URL substring to a queued response."""
    def __init__(self, routes):
        self.routes = routes

    def get(self, url, params=None, headers=None, timeout=None):
        for needle, resp in self.routes.items():
            if needle in url:
                return resp
        raise AssertionError(f"no route for {url}")


def test_pubmed_normalizes_with_review_type():
    http = _RouteHttp({"esearch": _Resp(json_data=PUBMED_SEARCH),
                       "efetch": _Resp(text=PUBMED_XML)})
    results, error = PubmedProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "LTP and memory"
    assert r["doi"] == "10.1000/ltp"
    assert r["source"] == "pubmed"
    assert r["source_type"] == "review"
    assert r["year"] == 2024
    assert r["sources"] == ["pubmed"]


def test_pubmed_empty_idlist_returns_no_rows():
    http = _RouteHttp({"esearch": _Resp(json_data={"esearchresult": {"idlist": []}})})
    results, error = PubmedProvider(http).search("ltp", 5)
    assert results == []
    assert error is None


def test_semantic_scholar_normalizes():
    http = _RouteHttp({"semanticscholar": _Resp(json_data=S2_JSON)})
    results, error = SemanticScholarProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["doi"] == "10.5/s2"
    assert r["citation_count"] == 9
    assert r["source"] == "semantic_scholar"


def test_arxiv_normalizes_preprint():
    http = _RouteHttp({"arxiv": _Resp(text=ARXIV_XML)})
    results, error = ArxivProvider(http).search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["source_type"] == "preprint"
    assert r["doi"] == "10.1/arx"
    assert r["url"] == "https://arxiv.org/abs/2401.01234v1"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_providers_existing.py -q`
Expected: FAIL (`ModuleNotFoundError` for the new provider modules).

- [ ] **Step 3: Write minimal implementation**

PubMed needs two HTTP calls (esearch → efetch), so it overrides `_fetch` to return the efetch XML text wrapped in a response-like object; `parse_response` parses XML.

```python
# src/neurodb/literature/providers/pubmed.py
from __future__ import annotations

import os
import xml.etree.ElementTree as ET

from neurodb.literature.providers.base import BaseLiteratureProvider

_ESEARCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
_EFETCH = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"


class PubmedProvider(BaseLiteratureProvider):
    name = "pubmed"

    @property
    def endpoint(self) -> str:
        return _EFETCH

    def build_params(self, query: str, limit: int) -> dict:
        return {"db": "pubmed", "term": query, "retmode": "json", "retmax": str(limit)}

    def _fetch(self, query: str, limit: int):
        api_key = self._api_key or os.environ.get("NCBI_API_KEY")
        params = self.build_params(query, limit)
        if api_key:
            params["api_key"] = api_key
        search_resp = self._http.get(_ESEARCH, params=params, headers={}, timeout=self._timeout)
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return _EmptyXml()
        fetch_params = {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"}
        if api_key:
            fetch_params["api_key"] = api_key
        fetch_resp = self._http.get(_EFETCH, params=fetch_params, headers={}, timeout=self._timeout)
        fetch_resp.raise_for_status()
        return fetch_resp

    def parse_response(self, response) -> list[dict]:
        text = getattr(response, "text", "") or ""
        if not text.strip():
            return []
        root = ET.fromstring(text)
        rows = []
        for article in root.findall(".//PubmedArticle"):
            title = _text(article.find(".//ArticleTitle")) or "Untitled PubMed result"
            abstract = " ".join(
                p for p in (_text(n) for n in article.findall(".//AbstractText")) if p
            )
            year_text = _text(article.find(".//PubDate/Year"))
            pub_types = [_text(n) for n in article.findall(".//PublicationType") if _text(n)]
            doi = None
            for n in article.findall(".//ELocationID") + article.findall(".//ArticleId"):
                if n.attrib.get("EIdType") == "doi" or n.attrib.get("IdType") == "doi":
                    doi = _text(n)
                    break
            pmid = _text(article.find(".//PMID"))
            rows.append({"title": title, "abstract": abstract, "year": year_text,
                         "pub_types": pub_types, "doi": doi, "pmid": pmid})
        return rows

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("year")
        pmid = (raw.get("pmid") or "").strip()
        url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/" if pmid else self._doi_url(raw.get("doi"))
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": url,
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": self._classify_source_type(raw.get("pub_types", []), "paper"),
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": None,
            "source": self.name,
            "sources": [self.name],
        }


class _EmptyXml:
    text = ""

    def raise_for_status(self):
        return None


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())
```

```python
# src/neurodb/literature/providers/semantic_scholar.py
from __future__ import annotations

import os

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.semanticscholar.org/graph/v1/paper/search"


class SemanticScholarProvider(BaseLiteratureProvider):
    name = "semantic_scholar"

    @property
    def endpoint(self) -> str:
        return _URL

    def _headers(self) -> dict:
        api_key = self._api_key or os.environ.get("SEMANTIC_SCHOLAR_API_KEY")
        return {"x-api-key": api_key} if api_key else {}

    def build_params(self, query: str, limit: int) -> dict:
        return {
            "query": query,
            "limit": limit,
            "fields": "title,abstract,year,citationCount,externalIds,publicationTypes,url",
        }

    def parse_response(self, response) -> list[dict]:
        return response.json().get("data", []) or []

    def normalize(self, raw: dict) -> dict:
        doi = (raw.get("externalIds") or {}).get("DOI")
        return {
            "title": raw.get("title") or "Untitled Semantic Scholar result",
            "doi": doi,
            "url": (raw.get("url") or "").strip() or self._doi_url(doi),
            "abstract": self._truncate(raw.get("abstract") or ""),
            "source_type": self._classify_source_type(raw.get("publicationTypes") or [], "paper"),
            "year": raw.get("year"),
            "citation_count": raw.get("citationCount"),
            "source": self.name,
            "sources": [self.name],
        }
```

```python
# src/neurodb/literature/providers/arxiv.py
from __future__ import annotations

import xml.etree.ElementTree as ET

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://export.arxiv.org/api/query"
_NS = {"atom": "http://www.w3.org/2005/Atom", "arxiv": "http://arxiv.org/schemas/atom"}


class ArxivProvider(BaseLiteratureProvider):
    name = "arxiv"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"search_query": f"all:{query}", "start": 0, "max_results": limit}

    def parse_response(self, response) -> list[dict]:
        root = ET.fromstring(response.text)
        rows = []
        for entry in root.findall("atom:entry", _NS):
            rows.append({
                "title": _text(entry.find("atom:title", _NS)) or "Untitled arXiv result",
                "abstract": _text(entry.find("atom:summary", _NS)) or "",
                "published": _text(entry.find("atom:published", _NS)) or "",
                "doi": _text(entry.find("arxiv:doi", _NS)),
                "id": _text(entry.find("atom:id", _NS)) or "",
            })
        return rows

    def normalize(self, raw: dict) -> dict:
        published = raw.get("published", "")
        year = int(published[:4]) if published[:4].isdigit() else None
        url = raw.get("id", "").replace("http://arxiv.org", "https://arxiv.org") or None
        return {
            "title": raw["title"],
            "doi": raw.get("doi"),
            "url": url,
            "abstract": self._truncate(raw.get("abstract", "")),
            "source_type": "preprint",
            "year": year,
            "citation_count": None,
            "source": self.name,
            "sources": [self.name],
        }


def _text(node) -> str | None:
    if node is None or node.text is None:
        return None
    return " ".join(node.text.split())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_providers_existing.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/providers/pubmed.py src/neurodb/literature/providers/semantic_scholar.py src/neurodb/literature/providers/arxiv.py tests/unit/test_providers_existing.py
git commit -m "feat(lit): port pubmed/semantic_scholar/arxiv onto base provider"
```

---

### Task 4: Merge, dedup & ranking

**Files:**
- Create: `src/neurodb/literature/merge.py`
- Test: `tests/unit/test_literature_merge.py`

**Interfaces:**
- Consumes: common result schema dicts.
- Produces: `dedup_and_merge(results: list[dict], limit: int) -> list[dict]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_literature_merge.py
from neurodb.literature.merge import dedup_and_merge


def _rec(**kw):
    base = {"title": "T", "doi": None, "url": None, "abstract": None,
            "source_type": "paper", "year": None, "citation_count": None,
            "source": "x", "sources": ["x"]}
    base.update(kw)
    return base


def test_dedup_by_doi_merges_metadata():
    a = _rec(doi="10.1/x", abstract="short", citation_count=3, source="pubmed", sources=["pubmed"])
    b = _rec(doi="10.1/X", abstract="a much longer abstract", citation_count=10,
             source="openalex", sources=["openalex"], source_type="review")
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 1
    assert out[0]["abstract"] == "a much longer abstract"
    assert out[0]["citation_count"] == 10
    assert out[0]["source_type"] == "review"
    assert out[0]["sources"] == ["openalex", "pubmed"]


def test_dedup_title_year_fallback_when_no_doi():
    a = _rec(title="Hippocampal LTP!", year=2020, source="arxiv", sources=["arxiv"])
    b = _rec(title="hippocampal  ltp", year=2020, source="europepmc", sources=["europepmc"])
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 1
    assert set(out[0]["sources"]) == {"arxiv", "europepmc"}


def test_distinct_records_kept():
    a = _rec(doi="10.1/a")
    b = _rec(doi="10.1/b")
    out = dedup_and_merge([a, b], limit=10)
    assert len(out) == 2


def test_ranking_citations_desc_then_year_desc():
    a = _rec(doi="10.1/a", citation_count=5, year=2019)
    b = _rec(doi="10.1/b", citation_count=50, year=2018)
    c = _rec(doi="10.1/c", citation_count=None, year=2024)
    out = dedup_and_merge([a, b, c], limit=10)
    assert [r["doi"] for r in out] == ["10.1/b", "10.1/a", "10.1/c"]


def test_trims_to_limit_after_merge():
    recs = [_rec(doi=f"10.1/{i}", citation_count=i) for i in range(5)]
    out = dedup_and_merge(recs, limit=2)
    assert len(out) == 2
    assert out[0]["doi"] == "10.1/4"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_merge.py -q`
Expected: FAIL (`ModuleNotFoundError: neurodb.literature.merge`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/literature/merge.py
"""Dedup, enrich-merge, and rank literature results across providers."""
from __future__ import annotations

import re

_PUNCT = re.compile(r"[^a-z0-9 ]+")
_SPECIFICITY = {"review": 3, "paper": 2, "preprint": 1}


def _norm_title(title: str) -> str:
    lowered = (title or "").lower()
    return " ".join(_PUNCT.sub(" ", lowered).split())


def _key(record: dict) -> str:
    doi = (record.get("doi") or "").strip().lower()
    if doi:
        return f"doi:{doi}"
    return f"ty:{_norm_title(record.get('title', ''))}|{record.get('year')}"


def _merge_pair(base: dict, other: dict) -> dict:
    merged = dict(base)
    # longest abstract wins
    if len(other.get("abstract") or "") > len(merged.get("abstract") or ""):
        merged["abstract"] = other.get("abstract")
    # max citation count
    counts = [c for c in (base.get("citation_count"), other.get("citation_count")) if c is not None]
    merged["citation_count"] = max(counts) if counts else None
    # most specific source_type
    if _SPECIFICITY.get(other.get("source_type"), 0) > _SPECIFICITY.get(merged.get("source_type"), 0):
        merged["source_type"] = other.get("source_type")
    # prefer a real (non-DOI-only) url
    if not merged.get("url") or (merged["url"] or "").startswith("https://doi.org/"):
        if other.get("url"):
            merged["url"] = other["url"]
    # union of sources, sorted/stable
    merged["sources"] = sorted(set(base.get("sources") or []) | set(other.get("sources") or []))
    # keep doi if either has one
    merged["doi"] = base.get("doi") or other.get("doi")
    return merged


def _rank_key(record: dict):
    cites = record.get("citation_count")
    year = record.get("year")
    return (
        0 if cites is not None else 1, -(cites or 0),
        0 if year is not None else 1, -(year or 0),
        record.get("title") or "",
    )


def dedup_and_merge(results: list[dict], limit: int) -> list[dict]:
    merged: dict[str, dict] = {}
    order: list[str] = []
    for record in results:
        key = _key(record)
        if key in merged:
            merged[key] = _merge_pair(merged[key], record)
        else:
            merged[key] = dict(record)
            order.append(key)
    deduped = [merged[k] for k in order]
    deduped.sort(key=_rank_key)
    return deduped[:limit]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_literature_merge.py -q`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/merge.py tests/unit/test_literature_merge.py
git commit -m "feat(lit): dedup + enrich-merge + citation ranking"
```

---

### Task 5: Registry (env toggles + contact email)

**Files:**
- Create: `src/neurodb/literature/registry.py`
- Test: `tests/unit/test_literature_registry.py`

**Interfaces:**
- Consumes: provider classes (Tasks 3 + 7); `BaseLiteratureProvider`.
- Produces: `build_active_providers(http, *, timeout=10.0) -> list[BaseLiteratureProvider]`; module constant `ALL_PROVIDER_CLASSES: list[type]`; helper `_contact_email() -> str|None`; helper `_disabled_names() -> set[str]`.

Note: Task 5 registers only the three existing providers; Task 7 appends the four new ones to `ALL_PROVIDER_CLASSES`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_literature_registry.py
from neurodb.literature import registry


class _Http:
    def get(self, *a, **k):
        raise AssertionError("not called")


def test_builds_all_providers_by_default(monkeypatch):
    monkeypatch.delenv("LITERATURE_PROVIDERS_DISABLED", raising=False)
    providers = registry.build_active_providers(_Http())
    names = {p.name for p in providers}
    assert {"pubmed", "semantic_scholar", "arxiv"} <= names


def test_disabled_providers_excluded(monkeypatch):
    monkeypatch.setenv("LITERATURE_PROVIDERS_DISABLED", "arxiv, pubmed")
    names = {p.name for p in registry.build_active_providers(_Http())}
    assert "arxiv" not in names
    assert "pubmed" not in names
    assert "semantic_scholar" in names


def test_contact_email_from_neurodb_var(monkeypatch):
    monkeypatch.setenv("NEURODB_CONTACT_EMAIL", "a@b.com")
    monkeypatch.delenv("UNPAYWALL_EMAIL", raising=False)
    assert registry._contact_email() == "a@b.com"


def test_contact_email_falls_back_to_unpaywall(monkeypatch):
    monkeypatch.delenv("NEURODB_CONTACT_EMAIL", raising=False)
    monkeypatch.setenv("UNPAYWALL_EMAIL", "u@p.com")
    assert registry._contact_email() == "u@p.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_registry.py -q`
Expected: FAIL (`ModuleNotFoundError: neurodb.literature.registry`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/literature/registry.py
"""Build the active literature-provider list from environment config."""
from __future__ import annotations

import os

from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.literature.providers.arxiv import ArxivProvider
from neurodb.literature.providers.pubmed import PubmedProvider
from neurodb.literature.providers.semantic_scholar import SemanticScholarProvider

# Task 7 appends OpenAlex, EuropePmc, Crossref, Biorxiv here.
ALL_PROVIDER_CLASSES: list[type[BaseLiteratureProvider]] = [
    PubmedProvider,
    SemanticScholarProvider,
    ArxivProvider,
]


def _contact_email() -> str | None:
    return os.environ.get("NEURODB_CONTACT_EMAIL") or os.environ.get("UNPAYWALL_EMAIL")


def _disabled_names() -> set[str]:
    raw = os.environ.get("LITERATURE_PROVIDERS_DISABLED", "")
    return {name.strip() for name in raw.split(",") if name.strip()}


def build_active_providers(http, *, timeout: float = 10.0) -> list[BaseLiteratureProvider]:
    disabled = _disabled_names()
    email = _contact_email()
    providers: list[BaseLiteratureProvider] = []
    for cls in ALL_PROVIDER_CLASSES:
        if cls.name in disabled:
            continue
        providers.append(cls(http, timeout=timeout, contact_email=email))
    return providers
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_literature_registry.py -q`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/registry.py tests/unit/test_literature_registry.py
git commit -m "feat(lit): provider registry with env toggles + contact email"
```

---

### Task 6: Client (concurrent fan-out, logging, envelope) + shim

**Files:**
- Create: `src/neurodb/literature/client.py`
- Modify: `src/neurodb/literature/__init__.py` (add `client` import)
- Modify: `src/neurodb/literature_client.py` (reduce to shim)
- Test: `tests/unit/test_literature_client_fanout.py`

**Interfaces:**
- Consumes: `build_active_providers` (Task 5), `dedup_and_merge` (Task 4), `LiteratureSearch` schema (Task 2), `get_session`.
- Produces: `LiteratureSearchClient(engine, http_client=None, timeout=10.0)` with `search(query, limit=10) -> dict` (envelope). Re-exported from `neurodb.literature_client`.

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_literature_client_fanout.py
import json

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from neurodb import db as dbpkg
from neurodb.literature.client import LiteratureSearchClient
from neurodb.literature import registry
from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.schema import LiteratureSearch


class _StubProvider(BaseLiteratureProvider):
    def __init__(self, name, rows, error=None):
        super().__init__(http=None)
        self.name = name
        self._rows = rows
        self._error = error

    @property
    def endpoint(self):
        return "x"

    def build_params(self, query, limit):
        return {}

    def parse_response(self, response):
        return []

    def normalize(self, raw):
        return raw

    def search(self, query, limit):
        if self._error:
            return [], self._error
        return self._rows, None


def _engine():
    eng = create_engine("duckdb:///:memory:")
    dbpkg.init_db(eng)
    return eng


def _rec(doi, source, cites=None):
    return {"title": "T", "doi": doi, "url": None, "abstract": "a",
            "source_type": "paper", "year": 2020, "citation_count": cites,
            "source": source, "sources": [source]}


def test_envelope_merges_and_reports_providers(monkeypatch):
    eng = _engine()
    providers = [
        _StubProvider("pubmed", [_rec("10.1/x", "pubmed", 2)]),
        _StubProvider("openalex", [_rec("10.1/x", "openalex", 9), _rec("10.1/y", "openalex", 1)]),
        _StubProvider("crossref", [], error="HTTPError: 429"),
    ]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())
    env = client.search("ltp", limit=10)
    assert env["result_count"] == 2  # 10.1/x merged
    assert env["providers"]["pubmed"]["status"] == "ok"
    assert env["providers"]["crossref"]["status"] == "error"
    assert env["providers"]["crossref"]["error"] == "HTTPError: 429"
    merged = next(r for r in env["results"] if r["doi"] == "10.1/x")
    assert merged["citation_count"] == 9
    assert set(merged["sources"]) == {"pubmed", "openalex"}


def test_logs_provider_counts_json(monkeypatch):
    eng = _engine()
    providers = [_StubProvider("pubmed", [_rec("10.1/x", "pubmed", 2)])]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())
    client.search("ltp")
    with Session(eng) as s:
        row = s.execute(select(LiteratureSearch)).scalars().one()
    counts = json.loads(row.provider_counts_json)
    assert counts["pubmed"] == 1
    assert row.pubmed_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_client_fanout.py -q`
Expected: FAIL (`ModuleNotFoundError: neurodb.literature.client`).

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/literature/client.py
"""Orchestrates concurrent fan-out across active literature providers."""
from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import httpx
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.literature import registry
from neurodb.literature.merge import dedup_and_merge
from neurodb.schema import LiteratureSearch

_LEGACY_COUNT_COLUMNS = {
    "pubmed": "pubmed_count",
    "semantic_scholar": "semantic_scholar_count",
    "arxiv": "arxiv_count",
}


class LiteratureSearchClient:
    """Search all active providers concurrently and return a merged envelope."""

    def __init__(self, engine: Engine, http_client: Any | None = None, timeout: float = 10.0) -> None:
        self._engine = engine
        self._http = http_client or httpx.Client(timeout=timeout, follow_redirects=True)
        self._timeout = timeout

    def search(self, query: str, limit: int = 10) -> dict:
        providers = registry.build_active_providers(self._http, timeout=self._timeout)
        per_provider: dict[str, tuple[list[dict], str | None]] = {}
        with ThreadPoolExecutor(max_workers=max(1, len(providers))) as executor:
            futures = {executor.submit(p.search, query, limit): p for p in providers}
            for future in as_completed(futures):
                provider = futures[future]
                try:
                    per_provider[provider.name] = future.result(timeout=self._timeout + 1)
                except Exception as exc:
                    per_provider[provider.name] = ([], f"{type(exc).__name__}: {exc}")

        all_results: list[dict] = []
        for results, _error in per_provider.values():
            all_results.extend(results)
        merged = dedup_and_merge(all_results, limit)

        counts = {name: len(results) for name, (results, _e) in per_provider.items()}
        self._log_search(query, counts, merged)

        return {
            "query": query,
            "result_count": len(merged),
            "results": merged,
            "providers": {
                name: _provider_status(results, error)
                for name, (results, error) in per_provider.items()
            },
        }

    def _log_search(self, query: str, counts: dict[str, int], results: list[dict]) -> None:
        legacy = {col: counts.get(name, 0) for name, col in _LEGACY_COUNT_COLUMNS.items()}
        with get_session(self._engine) as session:
            session.add(
                LiteratureSearch(
                    query=query,
                    results_json=json.dumps(results),
                    provider_counts_json=json.dumps(counts),
                    searched_at=datetime.now(timezone.utc).isoformat(),
                    **legacy,
                )
            )


def _provider_status(results: list[dict], error: str | None) -> dict:
    if error is not None:
        return {"status": "error", "count": 0, "error": error}
    return {"status": "ok", "count": len(results), "error": None}
```

Update `src/neurodb/literature/__init__.py` to its final form:

```python
# src/neurodb/literature/__init__.py
"""Live literature-search layer: base-class + registry of search providers."""
from neurodb.literature.client import LiteratureSearchClient

__all__ = ["LiteratureSearchClient"]
```

Replace `src/neurodb/literature_client.py` entirely with the shim:

```python
# src/neurodb/literature_client.py
"""Back-compat shim. Implementation moved to neurodb.literature.

Existing imports (`from neurodb.literature_client import LiteratureSearchClient`)
keep working; new code should import from `neurodb.literature`.
"""
from neurodb.literature import LiteratureSearchClient

__all__ = ["LiteratureSearchClient"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_literature_client_fanout.py tests/unit/test_literature_client.py -q`
Expected: PASS. If the legacy `tests/unit/test_literature_client.py` asserts the old three-provider-only envelope shape with hardcoded internal method names, update those assertions to the new envelope contract (provider names present, `result_count`, merged `results`); do NOT delete coverage — adapt it.

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/client.py src/neurodb/literature/__init__.py src/neurodb/literature_client.py tests/unit/test_literature_client_fanout.py tests/unit/test_literature_client.py
git commit -m "feat(lit): concurrent fan-out client + back-compat shim"
```

---

### Task 7: Four new providers (OpenAlex, Europe PMC, Crossref, bioRxiv/medRxiv)

**Files:**
- Create: `src/neurodb/literature/providers/openalex.py`
- Create: `src/neurodb/literature/providers/europepmc.py`
- Create: `src/neurodb/literature/providers/crossref.py`
- Create: `src/neurodb/literature/providers/biorxiv.py`
- Modify: `src/neurodb/literature/registry.py` (append the four classes to `ALL_PROVIDER_CLASSES`)
- Test: `tests/unit/test_providers_new.py`

**Interfaces:**
- Consumes: `BaseLiteratureProvider`.
- Produces: `OpenAlexProvider` (`name="openalex"`, `uses_polite_pool=True`), `EuropePmcProvider` (`name="europepmc"`), `CrossrefProvider` (`name="crossref"`, `uses_polite_pool=True`), `BiorxivProvider` (`name="biorxiv"`).

**NOTE — verify API specifics with context7 / live docs before coding (per spec §7.3 and CLAUDE.md library rule).** The endpoints, params, and field names below reflect the documented public APIs; confirm current shapes for: OpenAlex `GET /works` (`search`, `per-page`, `mailto`; fields `title`/`display_name`, `doi`, `publication_year`, `cited_by_count`, `abstract_inverted_index`, `type`), Europe PMC `GET /webservices/rest/search` (`query`, `format=json`, `pageSize`; fields `title`, `doi`, `pubYear`, `citedByCount`, `abstractText`, `pubType`), Crossref `GET /works` (`query`, `rows`, `mailto`; `message.items[*]` `title[]`, `DOI`, `published.date-parts`, `is-referenced-by-count`, `abstract`, `type`), bioRxiv/medRxiv (no general keyword search endpoint — use the `details` API or the bioRxiv-on-OpenAlex/Europe-PMC path; if no keyword endpoint is available, implement bioRxiv as a thin filter over Europe PMC `SRC:PPR` results and document that decision in the module docstring).

- [ ] **Step 1: Write the failing test**

```python
# tests/unit/test_providers_new.py
from neurodb.literature.providers.openalex import OpenAlexProvider
from neurodb.literature.providers.europepmc import EuropePmcProvider
from neurodb.literature.providers.crossref import CrossrefProvider
from neurodb.literature.providers.biorxiv import BiorxivProvider

OPENALEX = {"results": [{
    "display_name": "OA paper", "doi": "https://doi.org/10.7/oa",
    "publication_year": 2023, "cited_by_count": 42, "type": "article",
    "abstract_inverted_index": {"Plasticity": [0], "matters": [1]},
    "id": "https://openalex.org/W1"}]}

EUROPEPMC = {"resultList": {"result": [{
    "title": "EPMC paper", "doi": "10.8/epmc", "pubYear": "2021",
    "citedByCount": 7, "abstractText": "epmc abstract",
    "pubType": "review", "fullTextUrlList": {}}]}}

CROSSREF = {"message": {"items": [{
    "title": ["Crossref paper"], "DOI": "10.9/cr",
    "published": {"date-parts": [[2019, 5]]},
    "is-referenced-by-count": 3, "abstract": "<p>cr abstract</p>",
    "type": "journal-article"}]}}

BIORXIV = {"resultList": {"result": [{
    "title": "Preprint paper", "doi": "10.10/pp", "pubYear": "2024",
    "citedByCount": 0, "abstractText": "pp abstract",
    "pubType": "preprint", "source": "PPR"}]}}


class _Resp:
    def __init__(self, json_data):
        self._json = json_data
        self.text = ""
        self.headers = {}

    def json(self):
        return self._json

    def raise_for_status(self):
        return None


class _Http:
    def __init__(self, resp):
        self.resp = resp
        self.last_params = None

    def get(self, url, params=None, headers=None, timeout=None):
        self.last_params = params
        return self.resp


def test_openalex_normalizes_and_uses_polite_pool():
    http = _Http(_Resp(OPENALEX))
    results, error = OpenAlexProvider(http, contact_email="me@x.com").search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "OA paper"
    assert r["doi"] == "10.7/oa"
    assert r["citation_count"] == 42
    assert r["abstract"] == "Plasticity matters"
    assert r["source"] == "openalex"
    assert http.last_params.get("mailto") == "me@x.com"


def test_europepmc_normalizes_review():
    results, error = EuropePmcProvider(_Http(_Resp(EUROPEPMC))).search("ltp", 5)
    assert error is None
    assert results[0]["source_type"] == "review"
    assert results[0]["doi"] == "10.8/epmc"
    assert results[0]["citation_count"] == 7


def test_crossref_strips_abstract_markup_and_year():
    http = _Http(_Resp(CROSSREF))
    results, error = CrossrefProvider(http, contact_email="me@x.com").search("ltp", 5)
    assert error is None
    r = results[0]
    assert r["title"] == "Crossref paper"
    assert r["year"] == 2019
    assert "<p>" not in (r["abstract"] or "")
    assert http.last_params.get("mailto") == "me@x.com"


def test_biorxiv_marks_preprint():
    results, error = BiorxivProvider(_Http(_Resp(BIORXIV))).search("ltp", 5)
    assert error is None
    assert results[0]["source_type"] == "preprint"
    assert results[0]["source"] == "biorxiv"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_providers_new.py -q`
Expected: FAIL (`ModuleNotFoundError` for the new modules).

- [ ] **Step 3: Write minimal implementation**

```python
# src/neurodb/literature/providers/openalex.py
from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.openalex.org/works"


class OpenAlexProvider(BaseLiteratureProvider):
    name = "openalex"
    uses_polite_pool = True

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"search": query, "per-page": limit}

    def parse_response(self, response) -> list[dict]:
        return response.json().get("results", []) or []

    def normalize(self, raw: dict) -> dict:
        doi = (raw.get("doi") or "").replace("https://doi.org/", "") or None
        return {
            "title": raw.get("display_name") or raw.get("title") or "Untitled OpenAlex result",
            "doi": doi,
            "url": raw.get("id") or self._doi_url(doi),
            "abstract": self._truncate(_invert_abstract(raw.get("abstract_inverted_index"))),
            "source_type": self._classify_source_type([raw.get("type") or ""], "paper"),
            "year": raw.get("publication_year"),
            "citation_count": raw.get("cited_by_count"),
            "source": self.name,
            "sources": [self.name],
        }


def _invert_abstract(index: dict | None) -> str:
    if not index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in index.items():
        for i in idxs:
            positions.append((i, word))
    return " ".join(word for _i, word in sorted(positions))
```

```python
# src/neurodb/literature/providers/europepmc.py
from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class EuropePmcProvider(BaseLiteratureProvider):
    name = "europepmc"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": query, "format": "json", "pageSize": limit, "resultType": "core"}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("resultList", {}) or {}).get("result", []) or []

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("pubYear")
        return {
            "title": raw.get("title") or "Untitled Europe PMC result",
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstractText") or ""),
            "source_type": self._classify_source_type([raw.get("pubType") or ""], "paper"),
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": raw.get("citedByCount"),
            "source": self.name,
            "sources": [self.name],
        }
```

```python
# src/neurodb/literature/providers/crossref.py
from __future__ import annotations

import re

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://api.crossref.org/works"
_TAG = re.compile(r"<[^>]+>")


class CrossrefProvider(BaseLiteratureProvider):
    name = "crossref"
    uses_polite_pool = True

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": query, "rows": limit}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("message", {}) or {}).get("items", []) or []

    def normalize(self, raw: dict) -> dict:
        titles = raw.get("title") or []
        title = titles[0] if titles else "Untitled Crossref result"
        parts = (raw.get("published", {}) or {}).get("date-parts") or [[None]]
        year = parts[0][0] if parts and parts[0] else None
        abstract = _TAG.sub(" ", raw.get("abstract") or "")
        return {
            "title": title,
            "doi": raw.get("DOI"),
            "url": self._doi_url(raw.get("DOI")),
            "abstract": self._truncate(abstract),
            "source_type": self._classify_source_type([raw.get("type") or ""], "paper"),
            "year": int(year) if isinstance(year, int) else None,
            "citation_count": raw.get("is-referenced-by-count"),
            "source": self.name,
            "sources": [self.name],
        }
```

```python
# src/neurodb/literature/providers/biorxiv.py
"""bioRxiv/medRxiv provider.

bioRxiv has no general keyword-search API, so this queries Europe PMC
restricted to preprint sources (SRC:PPR) and tags results as the biorxiv
provider. Confirm SRC filter syntax against current Europe PMC docs.
"""
from __future__ import annotations

from neurodb.literature.providers.base import BaseLiteratureProvider

_URL = "https://www.ebi.ac.uk/europepmc/webservices/rest/search"


class BiorxivProvider(BaseLiteratureProvider):
    name = "biorxiv"

    @property
    def endpoint(self) -> str:
        return _URL

    def build_params(self, query: str, limit: int) -> dict:
        return {"query": f"({query}) AND SRC:PPR", "format": "json", "pageSize": limit,
                "resultType": "core"}

    def parse_response(self, response) -> list[dict]:
        return (response.json().get("resultList", {}) or {}).get("result", []) or []

    def normalize(self, raw: dict) -> dict:
        year_text = raw.get("pubYear")
        return {
            "title": raw.get("title") or "Untitled preprint",
            "doi": raw.get("doi"),
            "url": self._doi_url(raw.get("doi")),
            "abstract": self._truncate(raw.get("abstractText") or ""),
            "source_type": "preprint",
            "year": int(year_text) if year_text and str(year_text).isdigit() else None,
            "citation_count": raw.get("citedByCount"),
            "source": self.name,
            "sources": [self.name],
        }
```

Append to `ALL_PROVIDER_CLASSES` in `src/neurodb/literature/registry.py`:

```python
from neurodb.literature.providers.openalex import OpenAlexProvider
from neurodb.literature.providers.europepmc import EuropePmcProvider
from neurodb.literature.providers.crossref import CrossrefProvider
from neurodb.literature.providers.biorxiv import BiorxivProvider

ALL_PROVIDER_CLASSES: list[type[BaseLiteratureProvider]] = [
    PubmedProvider,
    SemanticScholarProvider,
    ArxivProvider,
    OpenAlexProvider,
    EuropePmcProvider,
    CrossrefProvider,
    BiorxivProvider,
]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_providers_new.py tests/unit/test_literature_registry.py -q`
Expected: PASS (registry default test now sees 7 providers; new-provider tests pass).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature/providers/openalex.py src/neurodb/literature/providers/europepmc.py src/neurodb/literature/providers/crossref.py src/neurodb/literature/providers/biorxiv.py src/neurodb/literature/registry.py tests/unit/test_providers_new.py
git commit -m "feat(lit): add OpenAlex, Europe PMC, Crossref, bioRxiv providers"
```

---

### Task 8: Integration test — full fan-out + idempotency

**Files:**
- Test: `tests/integration/test_literature_fanout_integration.py`

**Interfaces:**
- Consumes: `LiteratureSearchClient`, `registry`, `LiteratureSearch`.

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/test_literature_fanout_integration.py
import json

from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import Session

from neurodb import db as dbpkg
from neurodb.literature.client import LiteratureSearchClient
from neurodb.literature import registry
from neurodb.literature.providers.base import BaseLiteratureProvider
from neurodb.schema import LiteratureSearch


class _Stub(BaseLiteratureProvider):
    def __init__(self, name, rows):
        super().__init__(http=None)
        self.name = name
        self._rows = rows

    @property
    def endpoint(self):
        return "x"

    def build_params(self, q, n):
        return {}

    def parse_response(self, r):
        return []

    def normalize(self, raw):
        return raw

    def search(self, query, limit):
        return self._rows, None


def _rec(doi, source, cites):
    return {"title": "Shared", "doi": doi, "url": None, "abstract": "a",
            "source_type": "paper", "year": 2020, "citation_count": cites,
            "source": source, "sources": [source]}


def test_full_fanout_merges_and_is_idempotent(monkeypatch):
    eng = create_engine("duckdb:///:memory:")
    dbpkg.init_db(eng)
    providers = [
        _Stub("pubmed", [_rec("10.1/x", "pubmed", 1)]),
        _Stub("openalex", [_rec("10.1/x", "openalex", 8)]),
        _Stub("europepmc", [_rec("10.2/y", "europepmc", 4)]),
    ]
    monkeypatch.setattr(registry, "build_active_providers", lambda http, timeout=10.0: providers)
    client = LiteratureSearchClient(eng, http_client=object())

    env1 = client.search("synaptic plasticity", limit=10)
    assert env1["result_count"] == 2
    top = env1["results"][0]
    assert top["doi"] == "10.1/x" and top["citation_count"] == 8

    # Re-run: same merged results; one audit row per call, no duplicated result records.
    env2 = client.search("synaptic plasticity", limit=10)
    assert env2["results"] == env1["results"]
    with Session(eng) as s:
        rows = s.execute(select(func.count()).select_from(LiteratureSearch)).scalar_one()
        last = s.execute(select(LiteratureSearch).order_by(LiteratureSearch.id.desc())).scalars().first()
    assert rows == 2  # two searches logged
    counts = json.loads(last.provider_counts_json)
    assert counts == {"pubmed": 1, "openalex": 1, "europepmc": 1}
```

- [ ] **Step 2: Run test to verify it fails (then passes)**

Run: `uv run pytest tests/integration/test_literature_fanout_integration.py -q`
Expected: PASS immediately if Tasks 4/6 are correct. If it fails, fix the client/merge — do not weaken the test.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those tracked in `docs/testLog.md`.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_literature_fanout_integration.py
git commit -m "test(lit): integration fan-out merge + idempotency"
```

---

### Task 9: Manual test plan + connectivity helper + projectStatus sync

**Files:**
- Create: `tests/manual/check_literature_providers.py`
- Create: `docs/testsPlans/manualTestPlan_literature_search_providers.md`
- Modify: `docs/projectStatus.md`

**Interfaces:**
- Consumes: `build_active_providers`.
- Produces: a CLI script printing per-provider reachability; a manual test plan doc.

- [ ] **Step 1: Write the connectivity helper script**

```python
# tests/manual/check_literature_providers.py
"""Per-provider live connectivity check for the literature-search layer.

Usage: uv run python tests/manual/check_literature_providers.py "synaptic plasticity"
Prints one line per active provider: name, status (ok/error), count, error.
Exit code 0 if every active provider returned status ok, else 1.
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

from neurodb.literature import registry


def main() -> int:
    load_dotenv()
    query = sys.argv[1] if len(sys.argv) > 1 else "synaptic plasticity"
    import httpx

    http = httpx.Client(timeout=15.0, follow_redirects=True)
    providers = registry.build_active_providers(http, timeout=15.0)
    if not providers:
        print("No active providers (check LITERATURE_PROVIDERS_DISABLED).")
        return 1
    all_ok = True
    for provider in providers:
        results, error = provider.search(query, 3)
        status = "ok" if error is None else "error"
        if error is not None:
            all_ok = False
        print(f"{provider.name:16} {status:6} count={len(results):<3} {error or ''}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 2: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_literature_search_providers.md`:

```markdown
# Manual Test Plan — Literature-Search Providers

## Purpose
Verify the live multi-provider literature search end-to-end against real APIs
and the FastAPI/React workbench. Automated tests cover normalization, merge,
registry, and fan-out with fixtures; this plan covers real-network behavior,
polite-pool config, and operator connectivity confirmation.

## Prerequisites
1. **Automated suite (mandatory, first):** run `uv run pytest tests/ -q`.
   Pass = no new failures beyond those tracked in `docs/testLog.md`.
2. **Provider connectivity confirmation (operator):** confirm `.env` has
   `NEURODB_CONTACT_EMAIL` set (OpenAlex/Crossref polite pool); optional
   `NCBI_API_KEY`, `SEMANTIC_SCHOLAR_API_KEY`. Then run:
   `uv run python tests/manual/check_literature_providers.py "synaptic plasticity"`
   - Expected: one line per active provider with `status ok` and `count>0` for
     pubmed, semantic_scholar, arxiv, openalex, europepmc, crossref, biorxiv.
   - Pass: every active provider reports `ok`. For any provider reporting
     `error` (auth/rate-limit/unreachable), record it and add its name to
     `LITERATURE_PROVIDERS_DISABLED` for the functional run; note it in the run log.

## Test Steps
1. **Multi-provider merge (real network):** start the FastAPI API; via the
   research agent / React workbench run `search_literature` with
   "synaptic plasticity LTP".
   - Pass: results returned; at least one result shows multiple providers in
     `sources`; results ordered by citation count (highest first); no provider
     error crashes the call (failed providers appear as status error in the
     envelope, others still return).
2. **Provider toggle:** set `LITERATURE_PROVIDERS_DISABLED=crossref`, restart
   the API, repeat the query.
   - Pass: envelope `providers` has no `crossref` key; other providers present.
3. **Audit row:** confirm a new `literature_searches` row exists with
   `provider_counts_json` populated for all active providers.
   - Pass: JSON contains a count per active provider; legacy
     `pubmed_count/semantic_scholar_count/arxiv_count` match the JSON.

## Pass/Fail
All steps pass = sign off. Record date and any disabled providers.
```

- [ ] **Step 3: Update projectStatus.md**

Add the new manual test plan to the reference table and set active focus. In `docs/projectStatus.md`, add a row to the source-document/reference table:

```markdown
| `docs/testsPlans/manualTestPlan_literature_search_providers.md` | Manual test plan — live multi-provider literature search (OpenAlex, Europe PMC, Crossref, bioRxiv) + connectivity confirmation |
```

Update the active-focus line to reference the literature-provider expansion (match the doc's existing active-focus wording/format).

- [ ] **Step 4: Run the full suite once more**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond `docs/testLog.md`.

- [ ] **Step 5: Commit**

```bash
git add tests/manual/check_literature_providers.py docs/testsPlans/manualTestPlan_literature_search_providers.md docs/projectStatus.md
git commit -m "docs(lit): manual test plan + connectivity helper + projectStatus sync"
```

---

## Self-Review

**Spec coverage:**
- §4.1 base class (template method + shared helpers) → Task 1.
- §4.2 common schema (+`sources`) → enforced in all provider tasks (1, 3, 7) and Global Constraints.
- §4.3 registry + env config (`NEURODB_CONTACT_EMAIL`/`UNPAYWALL_EMAIL` fallback, `LITERATURE_PROVIDERS_DISABLED`, polite pool) → Task 5; polite-pool mechanics in Task 1 + Task 7.
- §4.4 concurrent fan-out (ThreadPoolExecutor, per-provider timeout, no-crash) → Task 6.
- §4.5 merge/dedup/rank (DOI then title+year, enrich rules, citation/year ranking, trim) → Task 4.
- §4.6 envelope (backward compatible, dynamic provider keys) → Task 6.
- §4.7 audit schema (`provider_counts_json`, legacy columns kept, one migration) → Task 2 + logging in Task 6.
- §7.1 unit tests (per provider, base, registry/config, merge, fan-out, idempotency, migration) → Tasks 1–8.
- §7.2 manual test plan (pytest prereq first; per-provider connectivity confirmation; FastAPI/React functional) → Task 9.
- §7.3 API verification at plan/impl time → Task 7 NOTE.
- §8 projectStatus sync → Task 9.
- Back-compat shim for `literature_client.py` → Task 6.

**Placeholder scan:** No TBD/TODO. Task 7 contains a documented conditional (bioRxiv via Europe PMC SRC:PPR) with a concrete fallback, not a placeholder. Legacy test adaptation in Task 6 is an explicit instruction, not a deferral.

**Type consistency:** `search()` returns `tuple[list[dict], str|None]` everywhere; envelope `providers[name]` always `{status, count, error}`; `dedup_and_merge(results, limit)` signature consistent between Task 4 and Task 6; `build_active_providers(http, *, timeout)` consistent between Tasks 5, 6, 9; `provider_counts_json` name consistent across Tasks 2, 6, 8, 9.

## Execution Handoff

After saving, offer the two execution options (subagent-driven vs inline) per the writing-plans skill.
