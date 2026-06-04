# Groupings Phase 5 — Legacy Table Retirement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove the legacy `topics`/`concepts` tables, their six join tables, and their ORM models, cutting the last live consumers over to the unified groupings engine, so categorization has a single model.

**Status:** Complete — implemented and signed off 2026-06-04. Manual T1-T4 passed in `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_groupings_phase5.md`.

**Architecture:** The DB bootstraps via `Base.metadata.create_all(engine)` then runs ordered migrations. Phase 5 (1) makes migration 017's legacy backfill tolerant of the legacy tables being absent, (2) cuts over the two remaining live consumers (`research_agent`, `knowledge_library`) to the engine, (3) removes the legacy ORM models so `create_all` no longer recreates the tables, then (4) adds migration 021 to hard-`DROP` the eight tables. Order matters: models must be removed *before* the drop migration, or `create_all` resurrects the dropped tables on the next startup.

**Tech Stack:** Python, SQLAlchemy (DuckDB runtime, SQLite in-memory for tests), pytest, ruff. Migrations are plain functions in `src/neurodb/db.py` registered in `_MIGRATIONS` and applied by `apply_migrations` in `src/neurodb/migrations.py`.

---

## File Structure

- `src/neurodb/db.py` — modify `_migration_017_groupings` (guard backfill); add `_migration_021_drop_legacy_groupings_tables`; register `21` in `_MIGRATIONS`.
- `src/neurodb/agents/research_agent.py` — repoint two tool handlers to `run_suggest_groupings`.
- `src/neurodb/api/routes/knowledge_library.py` — remove `PaperTopic`/`PaperConcept` preservation from `_detach_paper_links`/`_restore_paper_links` and their imports.
- `src/neurodb/schema.py` — delete eight legacy ORM models.
- `src/neurodb/db/topic_store.py` — delete.
- `tests/unit/test_migration_017_groupings.py` — add a legacy-absent skip test and a raw-SQL legacy-table helper for backfill tests.
- `tests/unit/test_migration_021_drop_legacy.py` — new.
- Delete: `tests/unit/test_topic_store.py`, `tests/unit/test_question_topic_store.py`, `tests/unit/test_extract_question_topics.py`, `tests/unit/test_topic_concepts_schema.py`, `tests/integration/test_phase2_topic_bundle.py`.
- `tests/unit/test_api_knowledge_library.py` — adjust if the detach/restore simplification shifts behavior.
- `docs/projectStatus.md` — status sync (final task).

---

## Task 1: Make migration 017 backfill tolerant of absent legacy tables

**Files:**
- Modify: `src/neurodb/db.py` (`_migration_017_groupings`, ~lines 443–708)
- Test: `tests/unit/test_migration_017_groupings.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_migration_017_groupings.py`:

```python
def test_backfill_skipped_when_legacy_tables_absent():
    """On a fresh DB with no legacy tables, 017 creates the new tables and
    skips the legacy backfill instead of crashing on `FROM topics`."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    # Deliberately NO Base.metadata.create_all -> legacy tables do not exist.
    with eng.connect() as conn:
        _migration_017_groupings(conn)  # must not raise
        conn.commit()
    with eng.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            row = conn.execute(
                text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
                {"t": tbl},
            ).fetchone()
            assert row is not None, f"{tbl} missing"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py::test_backfill_skipped_when_legacy_tables_absent -v`
Expected: FAIL — `OperationalError: no such table: topics` raised by the backfill.

- [ ] **Step 3: Guard the backfill block**

In `src/neurodb/db.py`, add the import near the other SQLAlchemy imports at the top of the file:

```python
from sqlalchemy import inspect as sqla_inspect
```

In `_migration_017_groupings`, the function first creates `groupings` and `grouping_links` with their indexes (keep all of that unconditional), then runs a series of `INSERT INTO groupings ...` / `INSERT INTO grouping_links ...` backfill statements that read `topics`, `concepts`, and the join tables. Wrap **only the backfill statements** (everything after the last `CREATE INDEX ... ON grouping_links (status)` and before the end of the function) in a single existence guard:

```python
    # --- Legacy backfill: only runs when the legacy tables still exist. ---
    # On a fresh DB built after the Phase 5 model removal, these tables are
    # absent and there is nothing to migrate, so skip the whole block.
    if not sqla_inspect(conn).has_table("topics"):
        return

    conn.execute(text("""
        INSERT INTO groupings (
            id, type, name, parent_id, status, description, created_at, updated_at
        )
        SELECT
        ...
    """))
    # ... all remaining existing backfill statements unchanged ...
```

Indent the existing backfill statements under the guard (or, equivalently, `return` early when the table is absent as shown — early-return avoids re-indenting the whole block; prefer the early `return`). Do not change any backfill SQL.

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py::test_backfill_skipped_when_legacy_tables_absent -v`
Expected: PASS

- [ ] **Step 5: Run the full 017 test module (legacy still present via create_all)**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS — existing backfill tests still pass because the ORM models still exist at this point, so `create_all` makes the legacy tables and the guard passes.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_017_groupings.py
git commit -m "fix(db): guard migration 017 legacy backfill on table existence"
```

---

## Task 2: Cut research_agent tool handlers over to the groupings engine

**Files:**
- Modify: `src/neurodb/agents/research_agent.py` (handlers at ~lines 455–481)
- Test: `tests/unit/test_research_agent.py`

The two handlers currently call legacy `extract_question_topics` from `topic_store`. Repoint both to `run_suggest_groupings`, which resolves the model route internally and persists pending grouping links for `topic` and `concept`.

- [ ] **Step 1: Write the failing test**

Add to `tests/unit/test_research_agent.py` (create the file if it does not exist; mirror the existing agent-test import style — check a sibling like `tests/unit/test_tutor_agent.py` for the `NeuroResearchAgent` construction pattern and reuse it):

```python
from unittest.mock import patch
import json


def test_record_research_question_triggers_grouping_matcher(research_agent_and_engine):
    agent, engine = research_agent_and_engine

    class _Block:
        tool_name = "record_research_question"
        tool_input = {"question": "How does sleep affect plasticity?",
                      "topic_context": "sleep"}

    with patch("neurodb.agents.research_agent.run_suggest_groupings") as mock_run:
        out = json.loads(agent._handle_tool(_Block()))

    assert "id" in out
    mock_run.assert_called_once()
    kwargs = mock_run.call_args.kwargs
    assert kwargs["anchor_type"] == "question"
    assert kwargs["anchor_id"] == out["id"]
    assert kwargs["gtypes"] == ("topic", "concept")
```

> Adjust the dispatch entry point name (`_handle_tool`) and fixture to match the real agent API discovered in `research_agent.py`. If a shared fixture does not exist, build the agent inline with an in-memory engine the way the existing research-agent/tutor-agent tests do.

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_research_agent.py::test_record_research_question_triggers_grouping_matcher -v`
Expected: FAIL — `run_suggest_groupings` is not imported/patched (handler still calls legacy `extract_question_topics`).

- [ ] **Step 3: Repoint the handlers**

In `src/neurodb/agents/research_agent.py`, add the import near the top with the other imports:

```python
from neurodb.research.grouping_matcher import run_suggest_groupings
```

Replace the `record_research_question` handler body (currently lines ~455–472) with:

```python
        if block.tool_name == "record_research_question":
            result = record_research_question(
                self._engine,
                block.tool_input["question"],
                block.tool_input["topic_context"],
                status=block.tool_input.get("status", "open"),
            )
            if "id" in result:
                run_suggest_groupings(
                    self._engine,
                    anchor_type="question",
                    anchor_id=result["id"],
                    anchor_text=block.tool_input["question"],
                    gtypes=("topic", "concept"),
                )
            return json.dumps(result)
```

Replace the `extract_question_topics` handler body (currently lines ~473–481) with:

```python
        if block.tool_name == "extract_question_topics":
            run_suggest_groupings(
                self._engine,
                anchor_type="question",
                anchor_id=block.tool_input["question_id"],
                anchor_text=block.tool_input["question_text"],
                gtypes=("topic", "concept"),
            )
            return json.dumps({
                "status": "suggestions_generated",
                "question_id": block.tool_input["question_id"],
            })
```

Leave the two tool **schemas** (`record_research_question`, `extract_question_topics` in the tool list at lines ~129–153) unchanged — only the handler implementations change. Remove the now-dead `from neurodb.db.topic_store import extract_question_topics` lines inside both handlers and the now-unused `get_session as _gs` import if it is no longer referenced elsewhere in the file (grep before removing).

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_research_agent.py::test_record_research_question_triggers_grouping_matcher -v`
Expected: PASS

- [ ] **Step 5: Confirm no remaining topic_store reference in the agent**

Run: `grep -n "topic_store\|extract_question_topics" src/neurodb/agents/research_agent.py`
Expected: only the unchanged tool-schema `"name": "extract_question_topics"` line, no `topic_store` import.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/agents/research_agent.py tests/unit/test_research_agent.py
git commit -m "feat(agents): cut research_agent question tools over to grouping matcher"
```

---

## Task 3: Remove PaperTopic/PaperConcept preservation from knowledge_library

**Files:**
- Modify: `src/neurodb/api/routes/knowledge_library.py` (`_detach_paper_links` ~282–449, `_restore_paper_links` ~452–467, imports ~24–25)
- Test: `tests/unit/test_api_knowledge_library.py`

Paper↔topic/concept links now live in FK-less `grouping_links`, so the DuckDB-UPDATE workaround no longer needs to preserve `paper_topics`/`paper_concepts` rows.

- [ ] **Step 1: Write/extend the failing test**

In `tests/unit/test_api_knowledge_library.py`, add a regression test that approving a paper with a `grouping_links` row preserves that link and does not reference the legacy tables:

```python
def test_approve_paper_preserves_grouping_links_without_legacy_tables(kl_client_and_engine):
    client, engine = kl_client_and_engine
    paper_id = _seed_pending_paper(engine)  # reuse the file's existing seeding helper
    _seed_grouping_link(engine, anchor_type="paper", anchor_id=paper_id)  # add helper

    resp = client.post(f"/api/knowledge-library/{paper_id}/approve")
    assert resp.status_code == 200

    with get_session(engine) as session:
        rows = session.query(GroupingLink).filter_by(
            anchor_type="paper", anchor_id=paper_id
        ).all()
    assert len(rows) == 1
```

> Match the file's existing fixture/helper names. If a `grouping_links` seeding helper does not exist, add a tiny one that inserts a row via `GroupingLink(...)`.

- [ ] **Step 2: Run test to verify current state**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py::test_approve_paper_preserves_grouping_links_without_legacy_tables -v`
Expected: PASS today (links already preserved) — this test pins the behavior we must keep after simplification. Proceed to simplify and keep it green.

- [ ] **Step 3: Remove the legacy branches**

In `src/neurodb/api/routes/knowledge_library.py`:

Delete the import line fragment for `PaperConcept` and `PaperTopic` (lines ~24–25) from the schema import block.

In `_detach_paper_links`, delete the `has_paper_topics` and `has_paper_concepts` existence checks (lines ~322–331), delete the `"paper_topics"` and `"paper_concepts"` entries from the `links` dict (lines ~374–389), and remove the `(PaperTopic, has_paper_topics)` and `(PaperConcept, has_paper_concepts)` tuples from the delete loop (lines ~439–440). The loop becomes:

```python
    for model, enabled in [
        (DatasetPacketPaper, True),
        (StudyNote, has_study_notes),
        (Claim, has_claims),
    ]:
        if not enabled:
            continue
        for link in session.query(model).filter_by(paper_id=paper_id).all():
            session.delete(link)
```

In `_restore_paper_links`, delete the two loops that re-add `PaperTopic` and `PaperConcept` (lines ~457–460).

Leave the `study_notes` entries untouched — `note.topic_id`/`concept_id` are surviving (deferred) columns.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_api_knowledge_library.py -v`
Expected: PASS — the new test stays green and no test references `PaperTopic`/`PaperConcept`.

- [ ] **Step 5: Confirm imports clean**

Run: `grep -n "PaperTopic\|PaperConcept" src/neurodb/api/routes/knowledge_library.py`
Expected: no matches.

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/api/routes/knowledge_library.py tests/unit/test_api_knowledge_library.py
git commit -m "refactor(knowledge-library): drop paper_topics/paper_concepts preservation"
```

---

## Task 4: Delete topic_store and legacy-only test suites

**Files:**
- Delete: `src/neurodb/db/topic_store.py`
- Delete: `tests/unit/test_topic_store.py`, `tests/unit/test_question_topic_store.py`, `tests/unit/test_extract_question_topics.py`, `tests/unit/test_topic_concepts_schema.py`, `tests/integration/test_phase2_topic_bundle.py`

- [ ] **Step 1: Confirm engine coverage exists before deleting**

Run: `ls tests/unit/test_grouping_*.py tests/unit/test_grouping_matcher*.py 2>/dev/null; grep -rln "suggest_groupings\|grouping_store\|grouping_matcher" tests/`
Expected: grouping engine + matcher suites exist and cover create/link/search/rollup/proposal. If any unique assertion in a to-be-deleted file is NOT covered by an engine test, port it into the matching engine test file first, then continue.

- [ ] **Step 2: Confirm topic_store has no remaining importers**

Run: `grep -rln "topic_store" src/ tests/`
Expected: only the to-be-deleted test files (no `src/` references — `research_agent.py` was cut over in Task 2).

- [ ] **Step 3: Delete the files**

```bash
git rm src/neurodb/db/topic_store.py \
       tests/unit/test_topic_store.py \
       tests/unit/test_question_topic_store.py \
       tests/unit/test_extract_question_topics.py \
       tests/unit/test_topic_concepts_schema.py \
       tests/integration/test_phase2_topic_bundle.py
```

- [ ] **Step 4: Run the full suite (models still present)**

Run: `uv run pytest tests/ -q`
Expected: PASS — no remaining test imports the deleted module. (ORM models still exist, so `create_all` still builds legacy tables for the 017 backfill tests.)

- [ ] **Step 5: Commit**

```bash
git commit -m "chore: remove legacy topic_store and superseded legacy-only tests"
```

---

## Task 5: Make the 017 backfill tests build legacy tables via raw SQL

**Files:**
- Modify: `tests/unit/test_migration_017_groupings.py`

Once the ORM models are deleted (Task 6), `Base.metadata.create_all` will no longer create the legacy tables, so the backfill tests that `INSERT INTO topics` would fail. Add a raw-SQL helper now and call it in the backfill tests so they are independent of the models. (`CREATE TABLE IF NOT EXISTS` is harmless while the models still exist.)

- [ ] **Step 1: Add the legacy-table helper**

Add to `tests/unit/test_migration_017_groupings.py`:

```python
def _create_legacy_tables(conn):
    """Create the legacy source tables the 017 backfill reads, for tests that
    exercise backfill after the ORM models have been removed."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY, name VARCHAR(256) NOT NULL,
            description TEXT, status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS concepts (
            id INTEGER PRIMARY KEY, name VARCHAR(256) NOT NULL,
            description TEXT, status VARCHAR(16) NOT NULL DEFAULT 'active',
            created_at VARCHAR(32) NOT NULL, updated_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_topics (
            id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS question_concepts (
            id INTEGER PRIMARY KEY, question_id INTEGER NOT NULL,
            concept_id INTEGER NOT NULL, status VARCHAR(16) NOT NULL DEFAULT 'pending',
            created_at VARCHAR(32) NOT NULL)
    """))
    conn.execute(text("CREATE TABLE IF NOT EXISTS paper_topics (id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL, topic_id INTEGER NOT NULL)"))
    conn.execute(text("CREATE TABLE IF NOT EXISTS paper_concepts (id INTEGER PRIMARY KEY, paper_id INTEGER NOT NULL, concept_id INTEGER NOT NULL)"))
    conn.execute(text("CREATE TABLE IF NOT EXISTS topic_concepts (id INTEGER PRIMARY KEY, topic_id INTEGER NOT NULL, concept_id INTEGER NOT NULL)"))
    conn.execute(text("CREATE TABLE IF NOT EXISTS dataset_packet_topics (id INTEGER PRIMARY KEY, packet_id INTEGER NOT NULL, topic_id INTEGER NOT NULL)"))
```

> Confirm column names/types against the model definitions in `schema.py` before they are deleted; match them exactly so the backfill SELECTs resolve.

- [ ] **Step 2: Call the helper in every backfill test**

In each test that inserts legacy rows or runs the full migration chain expecting backfill (`test_backfill_groupings_from_topics_and_concepts`, `test_backfill_groupings_idempotent`, `test_backfill_links_all_sources`, `test_backfill_links_idempotent`, `test_full_migration_run_backfills_and_records_version`), call `_create_legacy_tables(conn)` on the connection **before** the first `INSERT INTO topics/...` (and, for the full-migration test, before `apply_migrations`, using a short-lived connection on the same engine). Leave `test_backfill_skipped_when_legacy_tables_absent`, `test_migration_017_registered`, `test_migration_runs_without_error_and_tables_exist`, and `test_migration_is_idempotent_on_empty_db` unchanged.

- [ ] **Step 3: Run the module**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS (models still present, so helper just no-ops over already-created tables).

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_migration_017_groupings.py
git commit -m "test(db): make 017 backfill tests build legacy tables independently"
```

---

## Task 6: Remove the eight legacy ORM models

**Files:**
- Modify: `src/neurodb/schema.py` (delete classes `QuestionTopic` ~348, `QuestionConcept` ~362, `Topic` ~446, `Concept` ~458, `PaperTopic` ~470, `PaperConcept` ~480, `TopicConcept` ~490, `DatasetPacketTopic` ~500)

- [ ] **Step 1: Delete the eight classes**

Remove the eight class definitions listed above from `src/neurodb/schema.py`. Do not touch `study_notes`/`research_questions` models or their `topic_id`/`concept_id` columns (deferred). Do not touch the `groupings`/`grouping_links` models.

- [ ] **Step 2: Confirm no source references remain**

Run: `grep -rn -E "\b(QuestionTopic|QuestionConcept|PaperTopic|PaperConcept|TopicConcept|DatasetPacketTopic)\b|class Topic\b|class Concept\b" src/`
Expected: no matches in `src/`.

- [ ] **Step 3: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — Tasks 1–5 removed every dependency on the models. The 017 backfill tests now build the legacy tables themselves; the skip test exercises the model-absent path.

- [ ] **Step 4: Lint**

Run: `uv run ruff check src/ tests/`
Expected: clean (fix any unused-import fallout in `schema.py` or callers).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py
git commit -m "refactor(schema): remove legacy topics/concepts ORM models"
```

---

## Task 7: Add migration 021 — hard drop of the legacy tables

**Files:**
- Modify: `src/neurodb/db.py` (add `_migration_021_drop_legacy_groupings_tables`; register `21` in `_MIGRATIONS` ~line 800)
- Test: `tests/unit/test_migration_021_drop_legacy.py` (new)

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_021_drop_legacy.py`:

```python
"""Unit tests for migration 021: drop legacy topics/concepts tables."""
from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.db import _MIGRATIONS, _migration_021_drop_legacy_groupings_tables
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.schema import Base

_LEGACY = (
    "topics", "concepts", "question_topics", "question_concepts",
    "paper_topics", "paper_concepts", "topic_concepts", "dataset_packet_topics",
)


def _make_engine():
    return create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )


def _table_exists(conn, name):
    return conn.execute(
        text("SELECT name FROM sqlite_master WHERE type='table' AND name=:t"),
        {"t": name},
    ).fetchone() is not None


def test_migration_021_registered():
    assert _MIGRATIONS.get(21) is _migration_021_drop_legacy_groupings_tables


def test_drops_existing_legacy_tables():
    eng = _make_engine()
    with eng.connect() as conn:
        for name in _LEGACY:
            conn.execute(text(f"CREATE TABLE {name} (id INTEGER PRIMARY KEY)"))
        conn.commit()
        _migration_021_drop_legacy_groupings_tables(conn)
        conn.commit()
        for name in _LEGACY:
            assert not _table_exists(conn, name), f"{name} not dropped"


def test_fresh_full_migration_run_succeeds_with_legacy_absent():
    eng = _make_engine()
    Base.metadata.create_all(eng)  # legacy models gone -> legacy tables not created
    apply_migrations(eng, _MIGRATIONS)
    assert get_schema_version(eng) >= 21
    with eng.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            assert _table_exists(conn, tbl)
        for name in _LEGACY:
            assert not _table_exists(conn, name)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_021_drop_legacy.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_021_drop_legacy_groupings_tables'`.

- [ ] **Step 3: Implement migration 021 and register it**

In `src/neurodb/db.py`, after `_migration_020_literature_search_arxiv_count`:

```python
def _migration_021_drop_legacy_groupings_tables(conn) -> None:
    """Drop the legacy topics/concepts tables and their six join tables.

    Data was backfilled into groupings/grouping_links by migration 017. No
    surviving table holds a foreign key to these (removed in migrations 010/012),
    so the drop is unblocked. The legacy ORM models were removed in Phase 5, so
    create_all no longer recreates these tables on startup.
    """
    for table in (
        "question_topics", "question_concepts",
        "paper_topics", "paper_concepts",
        "topic_concepts", "dataset_packet_topics",
        "topics", "concepts",
    ):
        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
```

Register it in `_MIGRATIONS` (after the `20:` entry):

```python
    20: _migration_020_literature_search_arxiv_count,
    21: _migration_021_drop_legacy_groupings_tables,
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_021_drop_legacy.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_021_drop_legacy.py
git commit -m "feat(db): migration 021 drops legacy topics/concepts tables"
```

---

## Task 8: Final gate — grep, full suite, lint, status sync

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Prove no non-historical legacy references remain**

Run:
```bash
grep -rn -E "\b(paper_topics|paper_concepts|topic_concepts|dataset_packet_topics|question_topics|question_concepts)\b" src/ --include=*.py | grep -v -E "_migration_01[67]|_migration_021"
grep -rn -E "\b(PaperTopic|PaperConcept|TopicConcept|DatasetPacketTopic|QuestionTopic|QuestionConcept)\b" src/ --include=*.py
grep -rln "topic_store" src/
```
Expected: the only matches are inside migrations 016/017/021 (the guarded backfill and the drop) — the immutable history. No model references, no `topic_store`.

- [ ] **Step 2: Run the full suite**

Run: `uv run pytest tests/ -q`
Expected: PASS — no new failures beyond those tracked in `docs/testLog.md`.

- [ ] **Step 3: Lint**

Run: `uv run ruff check src/ tests/`
Expected: clean.

- [ ] **Step 4: Restart-safety sanity check**

Run:
```bash
uv run python -c "
from sqlalchemy import create_engine, inspect
from neurodb.db import init_db
e = create_engine('duckdb:///:memory:')
init_db(e)            # create_all + seed + migrations (incl. 021)
init_db(e)            # second init must NOT resurrect legacy tables
names = set(inspect(e).get_table_names())
legacy = {'topics','concepts','paper_topics','paper_concepts','topic_concepts','dataset_packet_topics','question_topics','question_concepts'}
assert not (names & legacy), names & legacy
assert {'groupings','grouping_links'} <= names
print('restart-safe: legacy absent, groupings present')
"
```
Expected: prints `restart-safe: ...` with no assertion error. (Confirms `create_all` does not recreate the dropped tables on a second init.)

- [ ] **Step 5: Sync the status doc**

In `docs/projectStatus.md`: mark Unified Groupings Phase 5 complete in the Research epoch row and update the **Active focus** and **Next** lines (Phase 5 done; legacy tables retired; single groupings model). Update the backend test count to the new total from Step 2. Add to the reference table: `docs/superpowers/specs/2026-06-04-groupings-phase5-legacy-drop-design.md` and `docs/superpowers/plans/2026-06-04-groupings-phase5-legacy-drop.md`.

- [ ] **Step 6: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: complete Groupings Phase 5 (legacy table retirement); status sync"
```

---

## Self-Review Notes

- **Spec coverage:** §Scope items 1–7 map to Tasks 1 (017 guard), 7 (migration 021), 6 (model removal), 2+3 (straggler cutover), 4 (topic_store + test deletion), 5+others (tests), 8 (grep gate + suite). Preserved/deferred items (API contract, dead columns) are explicitly left untouched. Restart-safety and fresh-build-parity from §Testing are covered by Task 8 Step 4 and Task 1 / Task 7 tests respectively.
- **Ordering invariant:** model removal (Task 6) precedes the drop migration (Task 7) so `create_all` cannot resurrect dropped tables; the 017 guard (Task 1) and test independence (Task 5) precede model removal so nothing breaks mid-sequence.
- **Portability:** the 017 guard uses `sqlalchemy.inspect(conn).has_table(...)` (dialect-aware) rather than `information_schema`, so it works under both SQLite (tests) and DuckDB (runtime).
