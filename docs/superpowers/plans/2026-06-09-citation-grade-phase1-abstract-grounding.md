# Citation-Grade Phase 1 — Abstract Grounding Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ground the tutor's Knowledge Library on the real paper abstract (already fetched and currently discarded) instead of a title-derived summary, and tag every source with a data tier, vintage, and currency status the agent discloses.

**Architecture:** Reuse the existing `Paper.abstract`/`year`/`authors_json` columns (currently left null on the tutor path); add two columns (`data_tier`, `currency_status`) via migration 023; capture abstract/year/authors on `queue_source`; feed the abstract into summary generation; carry tier/vintage/currency into the ChromaDB metadata; derive the training-cutoff relation at query time; and instruct the agent to disclose tier, vintage, post-cutoff status, and currency warnings.

**Tech Stack:** Python, SQLAlchemy ORM over DuckDB (SQLite in tests), ChromaDB, pytest.

**Spec:** `docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md` (Phase 1; invariants #1 tier-as-trust-contract, #6 grounding disclosure, #8 temporal trust modifier).

---

## File Structure

| File | Change | Responsibility |
|---|---|---|
| `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md` | Create | Phase-gate manual test plan (browser/approve-flow verification) |
| `docs/projectStatus.md` | Modify | Register the manual test plan; note active focus |
| `src/neurodb/db.py` | Modify | Migration 023 (`data_tier`, `currency_status`) + registry entry |
| `src/neurodb/schema.py` | Modify | `Paper.data_tier`, `Paper.currency_status` ORM columns |
| `src/neurodb/temporal.py` | Create | Pure `temporal_descriptor(year, currency_status)` helper |
| `src/neurodb/agents/tutor_agent.py` | Modify | `queue_source` schema + persistence + tier/currency + merge tier-upgrade + search enrichment + disclosure prompt |
| `src/neurodb/api/routes/knowledge_library.py` | Modify | `_generate_summary`/`_fallback_summary` use abstract; pass tier/year/currency to `add_summary` |
| `src/neurodb/knowledge_store.py` | Modify | `add_summary` records tier/year/currency in Chroma metadata |
| `src/neurodb/api/schemas/knowledge_library.py` | Modify | `PaperItem.data_tier`, `PaperItem.currency_status` |
| `tests/unit/test_temporal.py` | Create | Helper unit tests |
| `tests/unit/test_migration_023_paper_tier_currency.py` | Create | Migration tests |
| `tests/unit/test_tutor_agent.py` | Modify | queue capture, tier, merge upgrade, search enrichment, prompt disclosure |
| `tests/unit/test_knowledge_store.py` | Modify | `add_summary` metadata |
| `tests/unit/test_api_knowledge_library.py` | Modify | `_summary_prompt`/`_fallback_summary` use abstract |

---

## Task 1: Manual test plan (phase-gate artifact, before code)

Per project rule, the manual test plan exists before implementation and is registered in `projectStatus.md` in the same step.

**Files:**
- Create: `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Write the manual test plan**

Create `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md`:

```markdown
# Manual Test Plan — Citation-Grade Phase 1: Abstract Grounding

**Feature:** Abstract-grounded Knowledge Library summaries + data tier / vintage / currency disclosure.
**Spec:** docs/superpowers/specs/2026-06-09-citation-grade-data-access-design.md (Phase 1)

## Prerequisites
1. **Automated suite green.** Run `uv run pytest tests/ -q`. Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.
2. Streamlit/API app running against a local DuckDB with provider keys loaded via `.env`.

## Tests
- **T1 — Abstract captured on queue.** In a tutor chat, run a literature search and have the agent queue a source that has an abstract. Verify in the Knowledge Library that the queued paper row stores the abstract and year, and shows tier "abstract".
- **T2 — Summary grounded in abstract.** Approve the queued source. Verify the generated summary reflects content from the abstract (not just the title) — e.g., mentions a method/finding present in the abstract but not implied by the title.
- **T3 — Metadata-only paper.** Queue a source with no abstract. Verify tier shows "metadata" and the agent, when citing it, says it is orienting from metadata only.
- **T4 — Post-cutoff disclosure.** Ask the agent about an approved source dated 2026 or later. Verify it states it has no training prior and relies on the stored text.
- **T5 — Currency warning.** Flag an approved source as retracted (via update path/DB), then ask the agent about it. Verify it surfaces a retraction warning instead of a clean citation.

## Pass/Fail
All of T1–T5 behave as described; no regression in existing queue/approve/search flows.
```

- [ ] **Step 2: Register the plan in projectStatus.md**

In `docs/projectStatus.md`, under the `**Active Plans / Specs**` reference block, add:

```markdown
| `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md` | Citation-grade Phase 1 manual test plan — T1-T5 abstract capture, abstract-grounded summary, tier/vintage/currency disclosure; pending implementation |
```

- [ ] **Step 3: Commit**

```bash
git add docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md docs/projectStatus.md
git commit -m "docs: add citation-grade Phase 1 manual test plan"
```

---

## Task 2: Migration 023 + ORM columns (`data_tier`, `currency_status`)

**Files:**
- Modify: `src/neurodb/schema.py:244-266` (Paper)
- Modify: `src/neurodb/db.py` (add migration fn after `_migration_022_learning_plans` ~line 842; register in `_MIGRATIONS` ~line 866)
- Test: `tests/unit/test_migration_023_paper_tier_currency.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_023_paper_tier_currency.py`:

```python
"""Unit tests for migration 023: papers.data_tier + papers.currency_status."""
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_023_paper_tier_currency
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def test_migration_023_registered():
    assert _MIGRATIONS.get(23) is _migration_023_paper_tier_currency


def test_adds_columns_idempotently():
    eng = _make_engine()
    with eng.connect() as conn:
        conn.execute(text(
            "CREATE TABLE papers (id INTEGER PRIMARY KEY, title TEXT)"
        ))
        _migration_023_paper_tier_currency(conn)
        _migration_023_paper_tier_currency(conn)  # second run must not raise
        conn.commit()
    cols = {c["name"] for c in inspect(eng).get_columns("papers")}
    assert {"data_tier", "currency_status"} <= cols


def test_full_migration_chain_includes_023():
    eng = _make_engine()
    Base.metadata.create_all(eng)
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 23
    cols = {c["name"] for c in inspect(eng).get_columns("papers")}
    assert {"data_tier", "currency_status"} <= cols
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_023_paper_tier_currency.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_023_paper_tier_currency'`.

- [ ] **Step 3: Add the ORM columns**

In `src/neurodb/schema.py`, inside `class Paper`, after the `year` column (line ~266), add:

```python
    data_tier: Mapped[str] = mapped_column(
        String(16), nullable=False, default="metadata",
        server_default="metadata", index=True,
    )
    currency_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="current",
        server_default="current", index=True,
    )
```

- [ ] **Step 4: Add the migration and register it**

In `src/neurodb/db.py`, after `_migration_022_learning_plans` (line ~842), add:

```python
def _migration_023_paper_tier_currency(conn) -> None:
    """Add data_tier and currency_status to papers (citation-grade Phase 1)."""
    for ddl in (
        "ALTER TABLE papers ADD COLUMN data_tier VARCHAR(16) DEFAULT 'metadata'",
        "ALTER TABLE papers ADD COLUMN currency_status VARCHAR(16) DEFAULT 'current'",
    ):
        try:
            conn.execute(text(ddl))
        except Exception:
            pass  # column already exists
```

In the `_MIGRATIONS` dict (after the `22:` entry, line ~866), add:

```python
    23: _migration_023_paper_tier_currency,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_023_paper_tier_currency.py -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py src/neurodb/db.py tests/unit/test_migration_023_paper_tier_currency.py
git commit -m "feat: add papers.data_tier and currency_status (migration 023)"
```

---

## Task 3: `temporal_descriptor` helper (vintage / cutoff relation / currency warning)

**Files:**
- Create: `src/neurodb/temporal.py`
- Test: `tests/unit/test_temporal.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_temporal.py`:

```python
"""Unit tests for the temporal trust descriptor (spec invariant #8)."""
from neurodb.temporal import CUTOFF_YEAR, temporal_descriptor


def test_pre_cutoff_year():
    d = temporal_descriptor(1982, "current")
    assert d["cutoff_relation"] == "pre_cutoff"
    assert d["vintage"] == "1982"
    assert d["warning"] is None


def test_post_cutoff_year():
    d = temporal_descriptor(CUTOFF_YEAR, "current")
    assert d["cutoff_relation"] == "post_cutoff"


def test_unknown_year():
    d = temporal_descriptor(None, "current")
    assert d["cutoff_relation"] == "unknown"
    assert d["vintage"] == "unknown"


def test_retracted_sets_warning():
    d = temporal_descriptor(2020, "retracted")
    assert d["warning"] is not None
    assert "retracted" in d["warning"]


def test_current_has_no_warning():
    assert temporal_descriptor(2020, "current")["warning"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_temporal.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'neurodb.temporal'`.

- [ ] **Step 3: Write the implementation**

Create `src/neurodb/temporal.py`:

```python
"""Temporal trust descriptor — spec invariant #8.

Vintage and training-cutoff relation are reasoned metadata, never a scalar
"newer is better" score. Currency status modifies the trust contract.
"""

# Model training cutoff is January 2026; year-level granularity is sufficient here.
CUTOFF_YEAR = 2026

_WARNING_STATUSES = ("superseded", "retracted", "contested")


def temporal_descriptor(year: int | None, currency_status: str = "current") -> dict:
    """Return vintage, cutoff relation, and any currency warning for a source."""
    if year is None:
        vintage = "unknown"
        cutoff_relation = "unknown"
    else:
        vintage = str(year)
        cutoff_relation = "post_cutoff" if year >= CUTOFF_YEAR else "pre_cutoff"

    warning = None
    if currency_status in _WARNING_STATUSES:
        warning = (
            f"This source is marked {currency_status}; surface this and do not "
            "present it as a clean citation."
        )

    return {
        "vintage": vintage,
        "cutoff_relation": cutoff_relation,
        "currency_status": currency_status,
        "warning": warning,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_temporal.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/temporal.py tests/unit/test_temporal.py
git commit -m "feat: add temporal_descriptor helper (vintage/cutoff/currency)"
```

---

## Task 4: Capture abstract/year/authors + tier on `queue_source`

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py` — `queue_source` schema (lines ~117-141), `_execute_queue_source` new-row creation (lines ~382-391), `merge_existing_paper_metadata` (lines ~207-219)
- Test: `tests/unit/test_tutor_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tutor_agent.py`:

```python
from neurodb.agents.tutor_agent import merge_existing_paper_metadata


def test_queue_source_persists_abstract_year_and_tier():
    engine = _engine()
    agent = _agent(engine)
    agent._execute_queue_source({
        "title": "Engram allocation in the amygdala",
        "source_type": "paper",
        "topic_context": "memory allocation",
        "abstract": "We show CREB controls engram allocation.",
        "year": 2024,
    })
    with Session(engine) as session:
        row = session.query(Paper).filter_by(
            normalized_title=normalize_title("Engram allocation in the amygdala")
        ).one()
        assert row.abstract == "We show CREB controls engram allocation."
        assert row.year == 2024
        assert row.data_tier == "abstract"
        assert row.currency_status == "current"


def test_queue_source_without_abstract_is_metadata_tier():
    engine = _engine()
    agent = _agent(engine)
    agent._execute_queue_source({
        "title": "Some untitled-abstract paper",
        "source_type": "paper",
        "topic_context": "x",
    })
    with Session(engine) as session:
        row = session.query(Paper).filter_by(
            normalized_title=normalize_title("Some untitled-abstract paper")
        ).one()
        assert row.data_tier == "metadata"


def test_merge_upgrades_tier_when_abstract_added():
    paper = Paper(
        title="t", normalized_title="t", source_type="paper",
        topic_context="c", status="pending", queued_at="now",
        data_tier="metadata", currency_status="current",
    )
    updates = merge_existing_paper_metadata(paper, {"abstract": "real abstract text"})
    assert "abstract" in updates
    assert "data_tier" in updates
    assert paper.data_tier == "abstract"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_tutor_agent.py -k "queue_source_persists or without_abstract or merge_upgrades" -v`
Expected: FAIL — abstract/year not persisted, `data_tier` defaults applied but not "abstract".

- [ ] **Step 3: Extend the `queue_source` schema**

In `src/neurodb/agents/tutor_agent.py`, in the `queue_source` `properties` (after the `topics` property, line ~137), add:

```python
                "abstract": {
                    "type": "string",
                    "description": "Abstract text from the search result, if available.",
                },
                "year": {"type": "integer", "description": "Publication year, if known."},
                "authors": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Author names, if known.",
                },
```

- [ ] **Step 4: Persist the new fields on row creation**

In `_execute_queue_source`, replace the `row = Paper(...)` construction (lines ~382-391) with:

```python
            abstract = (inputs.get("abstract") or "").strip() or None
            authors = inputs.get("authors") or []
            row = Paper(
                title=title,
                normalized_title=normalized,
                doi=doi,
                url=(inputs.get("url") or None),
                source_type=inputs["source_type"],
                topic_context=inputs["topic_context"],
                status="pending",
                queued_at=datetime.now(UTC).isoformat(),
                abstract=abstract,
                year=int(inputs["year"]) if inputs.get("year") else None,
                authors_json=json.dumps(authors) if authors else None,
                data_tier="abstract" if abstract else "metadata",
                currency_status="current",
            )
```

- [ ] **Step 5: Upgrade tier on merge**

In `merge_existing_paper_metadata` (line ~207), before `return updates`, add:

```python
    if "abstract" in updates and paper.data_tier == "metadata":
        paper.data_tier = "abstract"
        updates.append("data_tier")
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_tutor_agent.py -k "queue_source_persists or without_abstract or merge_upgrades" -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py tests/unit/test_tutor_agent.py
git commit -m "feat: capture abstract/year/authors and data_tier on queue_source"
```

---

## Task 5: Ground summary generation in the abstract

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py` — `_generate_summary` (lines ~472-505), `_fallback_summary` (lines ~508-514); add pure `_summary_prompt(row)` helper
- Test: `tests/unit/test_api_knowledge_library.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_api_knowledge_library.py`:

```python
from neurodb.api.routes.knowledge_library import _summary_prompt, _fallback_summary
from neurodb.schema import Paper


def _paper(**kw):
    base = dict(
        title="CREB and engram allocation", normalized_title="creb",
        source_type="paper", topic_context="memory", status="approved",
        queued_at="now",
    )
    base.update(kw)
    return Paper(**base)


def test_summary_prompt_includes_abstract_when_present():
    row = _paper(abstract="CREB overexpression biases engram allocation.")
    prompt = _summary_prompt(row)
    assert "CREB overexpression biases engram allocation." in prompt
    assert "Abstract:" in prompt


def test_summary_prompt_omits_abstract_label_when_absent():
    row = _paper(abstract=None)
    prompt = _summary_prompt(row)
    assert "Abstract:" not in prompt


def test_fallback_summary_uses_abstract_when_present():
    row = _paper(abstract="CREB overexpression biases engram allocation.")
    assert "CREB overexpression biases engram allocation." in _fallback_summary(row)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py -k "summary_prompt or fallback_summary_uses_abstract" -v`
Expected: FAIL — `_summary_prompt` not defined; fallback ignores abstract.

- [ ] **Step 3: Add `_summary_prompt` and use it in `_generate_summary`**

In `src/neurodb/api/routes/knowledge_library.py`, add above `_generate_summary` (line ~472):

```python
def _summary_prompt(row: Paper) -> str:
    lines = [
        "Create a concise structured neuroscience learning summary for this source.",
        f"Title: {row.title}",
        f"Source type: {row.source_type}",
        f"DOI: {row.doi or 'unknown'}",
        f"URL: {row.url or 'unknown'}",
        f"Topic context: {row.topic_context}",
    ]
    if row.abstract:
        lines.append("")
        lines.append("Summarize PRIMARILY from this abstract, not the title:")
        lines.append(f"Abstract: {row.abstract}")
    lines.append("")
    lines.append("Use sections: Key concepts, Relevance to neuroscience, Open questions.")
    return "\n".join(lines)
```

Then in `_generate_summary`, replace the inline prompt string (the `"content": ( ... )` block, lines ~488-496) with:

```python
                "content": _summary_prompt(row),
```

- [ ] **Step 4: Make `_fallback_summary` prefer the abstract**

Replace `_fallback_summary` (lines ~508-514) with:

```python
def _fallback_summary(row: Paper) -> str:
    if row.abstract:
        key = f"Key concepts (from abstract): {row.abstract}"
    else:
        key = (
            f"Key concepts: {row.title} was queued as a {row.source_type} while "
            f"discussing {row.topic_context}."
        )
    return (
        f"{key}\n\n"
        "Relevance to neuroscience: This source was approved for future Neuro-Tutor retrieval.\n\n"
        "Open questions: Add a richer model-generated summary when provider access is available."
    )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py -k "summary_prompt or fallback_summary_uses_abstract" -v`
Expected: PASS (3 tests).

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library.py
git commit -m "feat: ground knowledge-library summary generation in the abstract"
```

---

## Task 6: Record tier/year/currency in ChromaDB metadata

**Files:**
- Modify: `src/neurodb/knowledge_store.py` — `add_summary` (lines ~37-61)
- Modify: `src/neurodb/api/schemas/knowledge_library.py` — `PaperItem` (add two fields)
- Modify: `src/neurodb/api/routes/knowledge_library.py` — both `add_summary` call sites (lines ~77-83 and ~222-228)
- Test: `tests/unit/test_knowledge_store.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_knowledge_store.py`:

```python
def test_add_summary_records_tier_year_currency():
    import uuid
    import chromadb
    from neurodb.knowledge_store import KnowledgeLibraryStore

    class _StubEmbedder:
        def embed(self, texts):
            return [[0.2, 0.3, 0.4, 0.5] for _ in texts]

    store = KnowledgeLibraryStore(
        client=chromadb.EphemeralClient(),
        embedder=_StubEmbedder(),
        collection_name=f"t_meta_{uuid.uuid4().hex}",
    )
    store.add_summary(
        source_id=7, title="T", doi=None, topic_context="memory",
        summary="s", data_tier="abstract", year=2024, currency_status="current",
    )
    results = store.search("memory", n=1)
    meta = results[0]["metadata"]
    assert meta["data_tier"] == "abstract"
    assert meta["year"] == "2024"
    assert meta["currency_status"] == "current"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_knowledge_store.py -k "records_tier_year_currency" -v`
Expected: FAIL — `add_summary()` got an unexpected keyword argument `data_tier`.

- [ ] **Step 3: Extend `add_summary`**

In `src/neurodb/knowledge_store.py`, replace the `add_summary` signature and `metadata` dict (lines ~37-52) with:

```python
    def add_summary(
        self,
        source_id: int,
        title: str,
        doi: str | None,
        topic_context: str,
        summary: str,
        *,
        data_tier: str = "metadata",
        year: int | None = None,
        currency_status: str = "current",
    ) -> str:
        """Add or replace an approved source summary and return the Chroma doc ID."""
        doc_id = f"knowledge_source:{source_id}"
        metadata = {
            "source_id": str(source_id),
            "title": title,
            "doi": doi or "",
            "topic_context": topic_context,
            "data_tier": data_tier,
            "year": str(year) if year else "",
            "currency_status": currency_status,
        }
```

- [ ] **Step 4: Add the fields to `PaperItem`**

In `src/neurodb/api/schemas/knowledge_library.py`, in `class PaperItem` after the `year` field (line ~27), add:

```python
    data_tier: str = "metadata"
    currency_status: str = "current"
```

- [ ] **Step 5: Pass the fields at both approve call sites**

In `src/neurodb/api/routes/knowledge_library.py`, in `approve_source`, replace the `add_summary(...)` call (lines ~77-83) with:

```python
        chroma_id = knowledge_store.add_summary(
            source_id=_id,
            title=_title,
            doi=_doi,
            topic_context=_topic,
            summary=_summary or "",
            data_tier=item.data_tier,
            year=item.year,
            currency_status=item.currency_status,
        )
```

In `_approve_with_summary`, add tier/year/currency to the `values` dict (after line ~219) and pass them to `add_summary` (lines ~222-228):

```python
        "summary": item.summary or "",
        "data_tier": item.data_tier,
        "year": item.year,
        "currency_status": item.currency_status,
    }

    chroma_id = knowledge_store.add_summary(
        source_id=values["id"],
        title=values["title"],
        doi=values["doi"],
        topic_context=values["topic_context"],
        summary=values["summary"],
        data_tier=values["data_tier"],
        year=values["year"],
        currency_status=values["currency_status"],
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_knowledge_store.py tests/unit/test_api_knowledge_library.py -v`
Expected: PASS (no regressions; new metadata test green).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/knowledge_store.py src/neurodb/api/schemas/knowledge_library.py src/neurodb/api/routes/knowledge_library.py tests/unit/test_knowledge_store.py
git commit -m "feat: record data_tier/year/currency in knowledge-library metadata"
```

---

## Task 7: Grounding disclosure — enrich retrieval results + system prompt

**Files:**
- Modify: `src/neurodb/agents/tutor_agent.py` — import `temporal_descriptor`; enrich `_execute_search_knowledge_library` (lines ~427-434); add disclosure rules to `_build_system_prompt` (lines ~309-320)
- Test: `tests/unit/test_tutor_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_tutor_agent.py`:

```python
def test_search_results_carry_temporal_descriptor():
    engine = _engine()
    store = _store()
    store.add_summary(
        source_id=1, title="Recent paper", doi=None, topic_context="memory",
        summary="grounded summary", data_tier="abstract", year=2026,
        currency_status="current",
    )
    agent = NeuroTutorAgent(
        client=MagicMock(), engine=engine, vector_store=None, knowledge_store=store,
    )
    raw = agent._execute_search_knowledge_library({"query": "memory"})
    results = json.loads(raw)
    assert results[0]["temporal"]["cutoff_relation"] == "post_cutoff"
    assert results[0]["temporal"]["vintage"] == "2026"


def test_system_prompt_includes_disclosure_rules():
    agent = _agent()
    prompt = agent._build_system_prompt()
    assert "tier" in prompt.lower()
    assert "post-training-cutoff" in prompt.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/unit/test_tutor_agent.py -k "temporal_descriptor or disclosure_rules" -v`
Expected: FAIL — results lack `temporal`; prompt lacks disclosure text.

- [ ] **Step 3: Import the helper and add the disclosure constant**

In `src/neurodb/agents/tutor_agent.py`, add to the imports near the top:

```python
from neurodb.temporal import temporal_descriptor
```

Add a module-level constant (near `_TUTOR_SYSTEM_PROMPT`):

```python
_TEMPORAL_DISCLOSURE_RULES = (
    "Source disclosure: when you use a Knowledge Library source, state its tier "
    "(full text, abstract, or metadata) and its vintage (year). If a source is "
    "post-training-cutoff (cutoff_relation = post_cutoff), say you have no training "
    "prior for it and are relying on the stored text. If a source carries a temporal "
    "warning (superseded, retracted, or contested), surface that warning instead of "
    "presenting it as a clean citation."
)
```

- [ ] **Step 4: Enrich retrieval results**

Replace `_execute_search_knowledge_library` (lines ~427-434) with:

```python
    def _execute_search_knowledge_library(self, inputs: dict) -> str:
        if self._knowledge_store is None:
            return json.dumps({"error": "Knowledge library not available."})
        results = self._knowledge_store.search(
            inputs["query"],
            n=inputs.get("n_results", 5),
        )
        for result in results:
            meta = result.get("metadata") or {}
            raw_year = str(meta.get("year") or "")
            year = int(raw_year) if raw_year.isdigit() else None
            result["temporal"] = temporal_descriptor(
                year, meta.get("currency_status", "current")
            )
        return json.dumps(results)
```

- [ ] **Step 5: Append disclosure rules to the system prompt**

In `_build_system_prompt`, after `prompt_parts.append(_context_prompt_rules(self._context_mode))` (line ~314), add:

```python
        prompt_parts.append(_TEMPORAL_DISCLOSURE_RULES)
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `uv run pytest tests/unit/test_tutor_agent.py -k "temporal_descriptor or disclosure_rules" -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/agents/tutor_agent.py tests/unit/test_tutor_agent.py
git commit -m "feat: disclose tier/vintage/cutoff/currency in tutor retrieval and prompt"
```

---

## Task 8: Full-suite verification + status sync

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Run the whole suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — no new failures beyond those tracked in `docs/testLog.md`. If any pre-existing failures appear, confirm they are already in `docs/testLog.md` before proceeding.

- [ ] **Step 2: Run lint/compile if the project uses it**

Run: `uv run ruff check src/neurodb/temporal.py src/neurodb/agents/tutor_agent.py src/neurodb/knowledge_store.py src/neurodb/api/routes/knowledge_library.py`
Expected: no errors. (Skip if ruff is not configured.)

- [ ] **Step 3: Update active focus in projectStatus.md**

In `docs/projectStatus.md`, update the `**Active focus:**` line to note: "Citation-Grade Phase 1 (abstract grounding) implemented behind migration 023; manual verification pending via `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md`." Update the backend test count in the relevant phase row.

- [ ] **Step 4: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: mark citation-grade Phase 1 implemented, manual verification pending"
```

- [ ] **Step 5: Manual verification**

Execute `docs/testsPlans/manualTestPlan_citation_phase1_abstract_grounding.md` (T1–T5) against the running app. Record results per the project's manual-test-run process; on sign-off, move the plan to the completed table in `projectStatus.md`.

---

## Notes / coordination

- **Literature source registry overlap:** the `SourceBackend` registry spec (`2026-06-02-literature-source-registry-design.md`) also touches `literature_client` and centralizes `source_type`. This plan does **not** modify `literature_client`; it only consumes the `abstract`/`year` already present in search results. If the registry lands concurrently, no merge conflict is expected in the files this plan touches.
- **Out of scope (deferred to Phase 2):** `paper_chunks`, parse-quality gate, retrieval relevance threshold, quote verification, the embedding-abstraction formalization, version provenance, and the retraction-notice lookup. The `currency_status` field is wired now but is only set manually/by default in Phase 1.
