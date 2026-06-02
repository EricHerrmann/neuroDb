# arXiv Literature Search Backend Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add arXiv as a third live literature-search backend alongside PubMed and Semantic Scholar, labeling its results as `preprint`.

**Architecture:** Mirror the existing backend pattern in `LiteratureSearchClient` — a self-contained `_search_arxiv` method plus a pure `_parse_arxiv_xml` normalizer, fanned out from `search()`. Add an `arxiv_count` column (migration 020) for per-source audit logging. Register `preprint` as a valid `source_type` in the agent tool descriptions.

**Tech Stack:** Python, SQLAlchemy, DuckDB/SQLite, `xml.etree.ElementTree`, httpx, pytest.

**Spec:** `docs/superpowers/specs/2026-06-02-arxiv-search-backend-design.md`

---

## File Structure

- `src/neurodb/schema.py` — add `arxiv_count` column to `LiteratureSearch`.
- `src/neurodb/db.py` — add `_migration_020_literature_search_arxiv_count`, register in `_MIGRATIONS`.
- `src/neurodb/literature_client.py` — add `_search_arxiv`, `_parse_arxiv_xml`, arXiv constants; wire into `search()` and `_log_search`.
- `src/neurodb/agents/tutor_agent.py` — add `preprint` to `queue_source` allowed values + system prompt.
- `src/neurodb/agents/research_agent.py` — add `preprint` to source-type description.
- `tests/unit/test_literature_client.py` — arXiv parser + merge tests.
- `tests/unit/test_migrations.py` — migration 020 test.

---

## Task 1: Add `arxiv_count` column + migration 020

**Files:**
- Modify: `src/neurodb/schema.py` (LiteratureSearch, near `semantic_scholar_count`)
- Modify: `src/neurodb/db.py` (new migration fn + `_MIGRATIONS` registration)
- Test: `tests/unit/test_migrations.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_migrations.py`:

```python
def test_migration_020_adds_arxiv_count_column():
    from sqlalchemy import create_engine, inspect, text
    from neurodb.db import _migration_020_literature_search_arxiv_count

    engine = create_engine("sqlite:///:memory:")
    with engine.connect() as conn:
        conn.execute(text(
            "CREATE TABLE literature_searches ("
            "id INTEGER PRIMARY KEY, query TEXT, pubmed_count INTEGER, "
            "semantic_scholar_count INTEGER, results_json TEXT, searched_at TEXT)"
        ))
        conn.commit()
        # Idempotent: applying twice must not raise.
        _migration_020_literature_search_arxiv_count(conn)
        _migration_020_literature_search_arxiv_count(conn)
        conn.commit()

    cols = {c["name"] for c in inspect(engine).get_columns("literature_searches")}
    assert "arxiv_count" in cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migrations.py::test_migration_020_adds_arxiv_count_column -q`
Expected: FAIL — `ImportError: cannot import name '_migration_020_literature_search_arxiv_count'`

- [ ] **Step 3: Add the migration function and register it**

In `src/neurodb/db.py`, after `_migration_019_resync_grouping_sequences`:

```python
def _migration_020_literature_search_arxiv_count(conn) -> None:
    """Add per-source arXiv count column to literature_searches."""
    try:
        conn.execute(
            text("ALTER TABLE literature_searches ADD COLUMN arxiv_count INTEGER DEFAULT 0")
        )
    except Exception:
        pass  # column already exists
```

In the `_MIGRATIONS` dict, add after the `19:` entry:

```python
    20: _migration_020_literature_search_arxiv_count,
```

- [ ] **Step 4: Add the model column**

In `src/neurodb/schema.py`, in `LiteratureSearch`, immediately after the `semantic_scholar_count` line:

```python
    arxiv_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migrations.py::test_migration_020_adds_arxiv_count_column -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py tests/unit/test_migrations.py
git commit -m "feat(literature): add arxiv_count column + migration 020"
```

---

## Task 2: arXiv XML parser (`_parse_arxiv_xml`)

**Files:**
- Modify: `src/neurodb/literature_client.py` (constants + parser fn)
- Test: `tests/unit/test_literature_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_literature_client.py` (top-level, near `PUBMED_XML`):

```python
ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom" xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.01234v1</id>
    <published>2024-01-15T10:00:00Z</published>
    <title>Predictive coding and synaptic plasticity</title>
    <summary>A preprint on plasticity mechanisms.</summary>
    <arxiv:doi>10.1000/arxivpublished</arxiv:doi>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2402.05678v2</id>
    <published>2024-02-20T10:00:00Z</published>
    <title>Cortical maps without a DOI</title>
    <summary>An unpublished preprint.</summary>
  </entry>
</feed>
"""
```

And the parser test:

```python
def test_parse_arxiv_xml_normalizes_entries():
    from neurodb.literature_client import _parse_arxiv_xml

    results = _parse_arxiv_xml(ARXIV_XML)

    assert len(results) == 2
    first = results[0]
    assert first["title"] == "Predictive coding and synaptic plasticity"
    assert first["source"] == "arxiv"
    assert first["source_type"] == "preprint"
    assert first["year"] == 2024
    assert first["url"] == "https://arxiv.org/abs/2401.01234v1"
    assert first["doi"] == "10.1000/arxivpublished"
    assert first["citation_count"] is None
    # Preprint without a DOI: doi is None, url still built from id.
    assert results[1]["doi"] is None
    assert results[1]["url"] == "https://arxiv.org/abs/2402.05678v2"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_client.py::test_parse_arxiv_xml_normalizes_entries -q`
Expected: FAIL — `ImportError: cannot import name '_parse_arxiv_xml'`

- [ ] **Step 3: Add constants and the parser**

In `src/neurodb/literature_client.py`, add after the existing URL constants (near line 21):

```python
_ARXIV_API_URL = "http://export.arxiv.org/api/query"
_ARXIV_NS = {
    "atom": "http://www.w3.org/2005/Atom",
    "arxiv": "http://arxiv.org/schemas/atom",
}
```

Add this module-level function next to `_parse_pubmed_xml`:

```python
def _parse_arxiv_xml(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    results = []
    for entry in root.findall("atom:entry", _ARXIV_NS):
        title = _text(entry.find("atom:title", _ARXIV_NS)) or "Untitled arXiv result"
        abstract = _text(entry.find("atom:summary", _ARXIV_NS))
        published = _text(entry.find("atom:published", _ARXIV_NS)) or ""
        year = int(published[:4]) if published[:4].isdigit() else None
        doi = _text(entry.find("arxiv:doi", _ARXIV_NS))
        entry_id = _text(entry.find("atom:id", _ARXIV_NS)) or ""
        url = entry_id.replace("http://arxiv.org", "https://arxiv.org") or None
        results.append(
            {
                "title": title,
                "doi": doi,
                "url": url,
                "abstract": _truncate(abstract or ""),
                "source_type": "preprint",
                "year": year,
                "citation_count": None,
                "source": "arxiv",
            }
        )
    return results
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_literature_client.py::test_parse_arxiv_xml_normalizes_entries -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/literature_client.py tests/unit/test_literature_client.py
git commit -m "feat(literature): add arXiv Atom XML parser"
```

---

## Task 3: arXiv backend + wire into `search()`

**Files:**
- Modify: `src/neurodb/literature_client.py` (`_search_arxiv`, `search`, `_log_search`)
- Test: `tests/unit/test_literature_client.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_literature_client.py`. This drives all three backends through the fake HTTP client. Call order in `search()` is: PubMed esearch, PubMed efetch, Semantic Scholar, arXiv.

```python
def test_search_merges_arxiv_and_logs_arxiv_count():
    engine = _engine()
    fake = _FakeHttp([
        _Response({"esearchresult": {"idlist": ["123"]}}),
        _Response(text=PUBMED_XML),
        _Response({"data": []}),
        _Response(text=ARXIV_XML),
    ])

    results = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    arxiv_rows = [row for row in results if row["source"] == "arxiv"]
    assert len(arxiv_rows) == 2
    assert arxiv_rows[1]["url"] == "https://arxiv.org/abs/2402.05678v2"

    with Session(engine) as session:
        row = session.query(LiteratureSearch).one()
        assert row.arxiv_count == 2


def test_search_degrades_gracefully_when_arxiv_fails():
    engine = _engine()
    fake = _FakeHttp([
        _Response({"esearchresult": {"idlist": []}}),
        _Response({"data": []}),
        httpx.TimeoutException("arxiv down"),
    ])

    results = LiteratureSearchClient(engine, http_client=fake).search("plasticity")

    assert results == []
    with Session(engine) as session:
        assert session.query(LiteratureSearch).one().arxiv_count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_literature_client.py::test_search_merges_arxiv_and_logs_arxiv_count -q`
Expected: FAIL — `TypeError: _log_search() takes ... arguments` / no arXiv rows (arXiv not wired in yet)

- [ ] **Step 3: Add `_search_arxiv`**

In `src/neurodb/literature_client.py`, add as a method on `LiteratureSearchClient` after `_search_semantic_scholar`:

```python
    def _search_arxiv(self, query: str, limit: int) -> list[dict]:
        try:
            response = self._http.get(
                _ARXIV_API_URL,
                params={
                    "search_query": f"all:{query}",
                    "start": 0,
                    "max_results": limit,
                },
                timeout=self._timeout,
            )
            response.raise_for_status()
            return _parse_arxiv_xml(response.text)
        except Exception:
            return []
```

- [ ] **Step 4: Wire into `search()` and `_log_search`**

Replace the body of `search()`:

```python
    def search(self, query: str, limit: int = 10) -> list[dict]:
        pubmed_results = self._search_pubmed(query, limit)
        semantic_results = self._search_semantic_scholar(query, limit)
        arxiv_results = self._search_arxiv(query, limit)
        results = _dedup_by_doi(pubmed_results + semantic_results + arxiv_results)
        self._log_search(
            query,
            len(pubmed_results),
            len(semantic_results),
            len(arxiv_results),
            results,
        )
        return results
```

Update `_log_search` signature and the `LiteratureSearch(...)` construction:

```python
    def _log_search(
        self,
        query: str,
        pubmed_count: int,
        semantic_scholar_count: int,
        arxiv_count: int,
        results: list[dict],
    ) -> None:
        with get_session(self._engine) as session:
            session.add(
                LiteratureSearch(
                    query=query,
                    pubmed_count=pubmed_count,
                    semantic_scholar_count=semantic_scholar_count,
                    arxiv_count=arxiv_count,
                    results_json=json.dumps(results),
                    searched_at=datetime.now(timezone.utc).isoformat(),
                )
            )
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_literature_client.py -q`
Expected: PASS (all tests in the file, including the existing ones, pass)

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/literature_client.py tests/unit/test_literature_client.py
git commit -m "feat(literature): wire arXiv backend into search() with arxiv_count logging"
```

---

## Task 4: Register `preprint` source_type in agents

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py` (`queue_source` description + system prompt)
- Modify: `src/neurodb/agents/research_agent.py` (source-type description)
- Test: `tests/unit/test_tutor_agent.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_tutor_agent.py`:

```python
def test_queue_source_tool_lists_preprint_type():
    from neurodb.agents.tutor_agent import _TUTOR_TOOLS

    queue_tool = next(t for t in _TUTOR_TOOLS if t["name"] == "queue_source")
    desc = queue_tool["input_schema"]["properties"]["source_type"]["description"]
    assert "preprint" in desc.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_tutor_agent.py::test_queue_source_tool_lists_preprint_type -q`
Expected: FAIL — `assert 'preprint' in 'one of: paper, review, textbook, website.'`

- [ ] **Step 3: Update the descriptions**

In `src/neurodb/agents/tutor_agent.py`, the `queue_source` `source_type` description:

```python
                    "description": "One of: paper, review, preprint, textbook, website.",
```

In the tutor system prompt string (the "Whenever you cite or recommend an external resource such as a paper, review, textbook, ..." line), include preprint:

```python
    "Whenever you cite or recommend an external resource such as a paper, review, preprint, textbook, "
```

In `src/neurodb/agents/research_agent.py`, update the source-type description:

```python
                    "description": "paper, review, preprint, textbook, or website",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_tutor_agent.py::test_queue_source_tool_lists_preprint_type -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py src/neurodb/agents/research_agent.py tests/unit/test_tutor_agent.py
git commit -m "feat(agents): allow preprint source_type for arXiv results"
```

---

## Task 5: Full-suite verification

- [ ] **Step 1: Run the full test suite**

Run: `uv run pytest tests/ -q`
Expected: No new failures beyond those already tracked in `docs/testLog.md`.

- [ ] **Step 2: If green, done.** If any new failure appears, stop and investigate before claiming completion (systematic-debugging).
