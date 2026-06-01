# Groupings Phase 1 — Unified Tables + Backfill Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce the unified `groupings` / `grouping_links` tables and an idempotent migration that backfills them from the existing `topics`, `concepts`, and their six join tables — with nothing yet reading the new tables.

**Architecture:** Two new ORM models on the shared `Base` (so `init_db`'s `create_all` provisions them everywhere), plus migration `017` that defensively creates the tables and backfills rows from legacy tables. Legacy tables are untouched and remain the source of truth until later phases cut consumers over. Backfill is pure SQL with `WHERE NOT EXISTS` guards, making re-runs no-ops.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 ORM, DuckDB (runtime) / SQLite in-memory (tests), pytest, `uv`.

**Spec:** `docs/superpowers/specs/2026-06-01-unified-groupings-taxonomy-design.md` (Phase 1).

**Conventions discovered in this codebase (follow exactly):**
- Migrations are plain functions `_migration_NNN_name(conn)` in `src/neurodb/db.py`, registered in the `_MIGRATIONS: dict[int, callable]` at the bottom, applied in version order by `apply_migrations` (idempotent; gated by a `schema_migrations` table).
- The latest migration is `016`; this plan adds `017`.
- Migration SQL must run on **both** DuckDB and SQLite (tests use `sqlite:///:memory:`). Use `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and `INSERT ... SELECT ... WHERE NOT EXISTS` — all portable.
- Migration **tests** call the function directly (e.g. `_migration_017_groupings(conn)`), after `Base.metadata.create_all(engine)`, and assert via SQL. Idempotency is tested by calling the function twice. See `tests/unit/test_question_migration_016.py` for the template.
- ORM id columns use `Sequence("..._id_seq")` (DuckDB needs it; SQLite ignores it).
- Run the suite with `uv run pytest tests/ -q`. A single test: `uv run pytest tests/unit/test_x.py::test_y -v`.

**Backfill source → target mapping (reference for Tasks 3–4):**

| Source (legacy) | → `groupings` | → `grouping_links` |
|---|---|---|
| `topics` row | `(type='topic', name, status, description, parent_id=NULL)` | — |
| `concepts` row | `(type='concept', name, status, description, parent_id=NULL)` | — |
| `question_topics(question_id, topic_id, status)` | — | `(grouping=<topic>, anchor_type='question', anchor_id=question_id, status=<preserved>)` |
| `question_concepts(question_id, concept_id, status)` | — | `(grouping=<concept>, anchor_type='question', anchor_id=question_id, status=<preserved>)` |
| `paper_topics(paper_id, topic_id)` | — | `(grouping=<topic>, anchor_type='paper', anchor_id=paper_id, status='confirmed')` |
| `paper_concepts(paper_id, concept_id)` | — | `(grouping=<concept>, anchor_type='paper', anchor_id=paper_id, status='confirmed')` |
| `dataset_packet_topics(packet_id, topic_id)` | — | `(grouping=<topic>, anchor_type='dataset_packet', anchor_id=packet_id, status='confirmed')` |
| `topic_concepts(topic_id, concept_id)` | — | `(grouping=<topic>, anchor_type='grouping', anchor_id=<concept grouping id>, status='confirmed')` |
| `study_notes.topic_id` (non-null) | — | `(grouping=<topic>, anchor_type='study_note', anchor_id=note.id, status='confirmed')` |
| `study_notes.concept_id` (non-null) | — | `(grouping=<concept>, anchor_type='study_note', anchor_id=note.id, status='confirmed')` |

`parent_id` stays NULL in Phase 1 — the `plasticity`/`stroke` hierarchy is seeded in Phase 3, not here.

> **Note on `research_questions.topic_id`:** it is intentionally NOT backfilled directly. Migration `016` already backfills `question_topics` from every non-null `research_questions.topic_id` (as `confirmed`), so the `question_topics` source above fully covers it. Adding a direct path would only create duplicates the `WHERE NOT EXISTS` guard then drops.

Legacy `groupings` ids are resolved by joining on `name` within a `type` (the `UNIQUE(type, name)` constraint guarantees a single match).

---

### Task 1: ORM models for `groupings` and `grouping_links`

**Files:**
- Modify: `src/neurodb/schema.py` (append two model classes; existing imports on line 9 already include `Index`, `Integer`, `Sequence`, `String`, `Text`, `UniqueConstraint`)
- Test: `tests/unit/test_groupings_schema.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_groupings_schema.py`:

```python
"""Unit tests for the unified groupings/grouping_links ORM models (Groupings Phase 1)."""
from datetime import datetime, timezone

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


def test_groupings_table_created_and_insertable():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings (type, name, parent_id, status, description, created_at, updated_at) "
            "VALUES ('topic', 'plasticity', NULL, 'active', NULL, :now, :now)"
        ), {"now": _now()})
        conn.commit()
        row = conn.execute(text(
            "SELECT type, name, status FROM groupings WHERE name='plasticity'"
        )).fetchone()
    assert row == ("topic", "plasticity", "active")


def test_groupings_type_name_unique():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings (type, name, status, created_at, updated_at) "
            "VALUES ('topic', 'stroke', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO groupings (type, name, status, created_at, updated_at) "
                "VALUES ('topic', 'stroke', 'active', :now, :now)"
            ), {"now": _now()})
            conn.commit()


def test_same_name_different_type_allowed():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO groupings (type, name, status, created_at, updated_at) VALUES "
            "('topic', 'memory', 'active', :now, :now), "
            "('concept', 'memory', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings WHERE name='memory'")).fetchone()[0]
    assert n == 2


def test_grouping_links_table_created_and_unique_anchor():
    engine = _make_engine()
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at) "
            "VALUES (1, 'question', 14, 'pending', :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        with pytest.raises(IntegrityError):
            conn.execute(text(
                "INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at) "
                "VALUES (1, 'question', 14, 'confirmed', :now)"
            ), {"now": _now()})
            conn.commit()
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_groupings_schema.py -v`
Expected: FAIL — `OperationalError: no such table: groupings` (models don't exist yet).

- [ ] **Step 3: Add the models**

Append to the end of `src/neurodb/schema.py`:

```python
class Grouping(Base):
    """Unified categorization entity. One row per topic/concept/future type.

    `type` selects the grouping kind ('topic', 'concept', ...). `parent_id`
    is a plain self-reference (no FK constraint — DuckDB rejects UPDATE on
    FK-referenced rows; re-parenting needs UPDATE). NULL parent = top-level.
    """
    __tablename__ = "groupings"
    __table_args__ = (
        UniqueConstraint("type", "name", name="uq_groupings_type_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("groupings_id_seq"), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class GroupingLink(Base):
    """Link from a grouping to an anchor (question, paper, dataset_packet,
    study_note, or another grouping). Carries the pending/confirmed lifecycle.

    No FK constraints by design (DuckDB update limitation); integrity is
    enforced in application code.
    """
    __tablename__ = "grouping_links"
    __table_args__ = (
        UniqueConstraint("grouping_id", "anchor_type", "anchor_id", name="uq_grouping_links_anchor"),
        Index("ix_grouping_links_anchor", "anchor_type", "anchor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("grouping_links_id_seq"), primary_key=True)
    grouping_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_groupings_schema.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_groupings_schema.py
git commit -m "feat(groupings): add Grouping and GroupingLink ORM models"
```

---

### Task 2: Migration 017 — create tables (defensive) + register

**Files:**
- Modify: `src/neurodb/db.py` (add import; add `_migration_017_groupings`; register `17` in `_MIGRATIONS`)
- Test: `tests/unit/test_migration_017_groupings.py`

- [ ] **Step 1: Write the failing test**

Create `tests/unit/test_migration_017_groupings.py`:

```python
"""Unit tests for migration 017 — unified groupings tables + backfill (Groupings Phase 1)."""
from datetime import datetime, timezone

from sqlalchemy import create_engine, text
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base
from neurodb.db import _migration_017_groupings, _MIGRATIONS


def _now():
    return datetime.now(timezone.utc).isoformat()


def _make_engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    return eng


def test_migration_017_registered():
    assert _MIGRATIONS.get(17) is _migration_017_groupings


def test_migration_runs_without_error_and_tables_exist():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        for tbl in ("groupings", "grouping_links"):
            row = conn.execute(text(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=:t"
            ), {"t": tbl}).fetchone()
            assert row is not None, f"{tbl} missing"


def test_migration_is_idempotent_on_empty_db():
    engine = _make_engine()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_017_groupings(conn)  # second run must not raise
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
    assert n == 0
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: FAIL — `ImportError: cannot import name '_migration_017_groupings'`.

- [ ] **Step 3: Add the import**

In `src/neurodb/db.py`, add this import near the top (after the existing `from sqlalchemy import Engine, text` line):

```python
from datetime import datetime, timezone
```

- [ ] **Step 4: Add the migration function**

In `src/neurodb/db.py`, immediately **before** the `_MIGRATIONS: dict[int, callable] = {` line, add:

```python
def _migration_017_groupings(conn) -> None:
    """Create unified groupings/grouping_links tables (defensive) and backfill
    them from topics, concepts, and their join tables. Idempotent."""
    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS groupings (
            id INTEGER PRIMARY KEY,
            type VARCHAR(32) NOT NULL,
            name VARCHAR(256) NOT NULL,
            parent_id INTEGER,
            status VARCHAR(16) NOT NULL DEFAULT 'active',
            description TEXT,
            created_at VARCHAR(32) NOT NULL,
            updated_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_groupings_type_name ON groupings (type, name)"
        ))
    except Exception:
        pass
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_type ON groupings (type)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_parent_id ON groupings (parent_id)"))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_groupings_status ON groupings (status)"))

    conn.execute(text("""
        CREATE TABLE IF NOT EXISTS grouping_links (
            id INTEGER PRIMARY KEY,
            grouping_id INTEGER NOT NULL,
            anchor_type VARCHAR(32) NOT NULL,
            anchor_id INTEGER NOT NULL,
            status VARCHAR(16) NOT NULL DEFAULT 'confirmed',
            created_at VARCHAR(32) NOT NULL
        )
    """))
    try:
        conn.execute(text(
            "CREATE UNIQUE INDEX IF NOT EXISTS uq_grouping_links_anchor "
            "ON grouping_links (grouping_id, anchor_type, anchor_id)"
        ))
    except Exception:
        pass
    conn.execute(text(
        "CREATE INDEX IF NOT EXISTS ix_grouping_links_anchor ON grouping_links (anchor_type, anchor_id)"
    ))
    conn.execute(text("CREATE INDEX IF NOT EXISTS ix_grouping_links_grouping_id ON grouping_links (grouping_id)"))

    # Backfill added in Tasks 3 and 4.
```

- [ ] **Step 5: Register the migration**

In `src/neurodb/db.py`, add the `17:` entry as the last item of the `_MIGRATIONS` dict:

```python
    16: _migration_016_question_topic_tables,
    17: _migration_017_groupings,
}
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS (3 tests).

- [ ] **Step 7: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_017_groupings.py
git commit -m "feat(groupings): migration 017 creates unified tables (no backfill yet)"
```

---

### Task 3: Backfill `groupings` from `topics` and `concepts`

**Files:**
- Modify: `src/neurodb/db.py` (`_migration_017_groupings` — replace the `# Backfill added in Tasks 3 and 4.` line)
- Test: `tests/unit/test_migration_017_groupings.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_migration_017_groupings.py`:

```python
def _seed_topics_concepts(engine):
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO topics (name, description, status, created_at, updated_at) VALUES "
            "('neuroplasticity', 'desc-np', 'active', :now, :now), "
            "('stroke', NULL, 'active', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO concepts (name, description, status, created_at, updated_at) VALUES "
            "('long-term potentiation', NULL, 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()


def test_backfill_groupings_from_topics_and_concepts():
    engine = _make_engine()
    _seed_topics_concepts(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        rows = conn.execute(text(
            "SELECT type, name, status, description FROM groupings ORDER BY type, name"
        )).fetchall()
    assert ("topic", "neuroplasticity", "active", "desc-np") in rows
    assert ("topic", "stroke", "active", None) in rows
    assert ("concept", "long-term potentiation", "active", None) in rows
    assert len(rows) == 3


def test_backfill_groupings_idempotent():
    engine = _make_engine()
    _seed_topics_concepts(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
        n = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
    assert n == 3
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py::test_backfill_groupings_from_topics_and_concepts -v`
Expected: FAIL — `assert len(rows) == 3` fails (0 rows; no backfill yet).

- [ ] **Step 3: Add the groupings backfill**

In `src/neurodb/db.py`, replace the line `    # Backfill added in Tasks 3 and 4.` with:

```python
    # --- Backfill groupings from topics and concepts ---
    conn.execute(text("""
        INSERT INTO groupings (type, name, parent_id, status, description, created_at, updated_at)
        SELECT 'topic', t.name, NULL, t.status, t.description, t.created_at, t.updated_at
        FROM topics t
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings g WHERE g.type = 'topic' AND g.name = t.name
        )
    """))
    conn.execute(text("""
        INSERT INTO groupings (type, name, parent_id, status, description, created_at, updated_at)
        SELECT 'concept', c.name, NULL, c.status, c.description, c.created_at, c.updated_at
        FROM concepts c
        WHERE NOT EXISTS (
            SELECT 1 FROM groupings g WHERE g.type = 'concept' AND g.name = c.name
        )
    """))

    # --- Backfill grouping_links (Task 4) ---
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_017_groupings.py
git commit -m "feat(groupings): backfill groupings rows from topics and concepts"
```

---

### Task 4: Backfill `grouping_links` from the six join tables + study_notes anchors

**Files:**
- Modify: `src/neurodb/db.py` (`_migration_017_groupings` — replace the `# --- Backfill grouping_links (Task 4) ---` line)
- Test: `tests/unit/test_migration_017_groupings.py` (append)

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_migration_017_groupings.py`:

```python
def _seed_links_fixture(engine):
    """Seed topics/concepts + one row in each link source, return key ids."""
    with engine.connect() as conn:
        conn.execute(text(
            "INSERT INTO topics (name, status, created_at, updated_at) "
            "VALUES ('stroke', 'active', :now, :now)"
        ), {"now": _now()})
        conn.execute(text(
            "INSERT INTO concepts (name, status, created_at, updated_at) "
            "VALUES ('LTP', 'active', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        topic_id = conn.execute(text("SELECT id FROM topics WHERE name='stroke'")).fetchone()[0]
        concept_id = conn.execute(text("SELECT id FROM concepts WHERE name='LTP'")).fetchone()[0]
        # research question + its question_topics / question_concepts links
        conn.execute(text(
            "INSERT INTO research_questions (question, topic_context, status, created_at, updated_at) "
            "VALUES ('q?', '', 'open', :now, :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        q_id = conn.execute(text("SELECT id FROM research_questions WHERE question='q?'")).fetchone()[0]
        conn.execute(text(
            "INSERT INTO question_topics (question_id, topic_id, status, created_at) "
            "VALUES (:q, :t, 'pending', :now)"
        ), {"q": q_id, "t": topic_id, "now": _now()})
        conn.execute(text(
            "INSERT INTO question_concepts (question_id, concept_id, status, created_at) "
            "VALUES (:q, :c, 'confirmed', :now)"
        ), {"q": q_id, "c": concept_id, "now": _now()})
        # paper + paper_topics / paper_concepts
        conn.execute(text(
            "INSERT INTO papers (title, normalized_title, source_type, topic_context, status, queued_at) "
            "VALUES ('P', 'p', 'paper', '', 'approved', :now)"
        ), {"now": _now()})
        conn.commit()
    with engine.connect() as conn:
        paper_id = conn.execute(text("SELECT id FROM papers WHERE normalized_title='p'")).fetchone()[0]
        conn.execute(text("INSERT INTO paper_topics (paper_id, topic_id) VALUES (:p, :t)"),
                     {"p": paper_id, "t": topic_id})
        conn.execute(text("INSERT INTO paper_concepts (paper_id, concept_id) VALUES (:p, :c)"),
                     {"p": paper_id, "c": concept_id})
        # topic_concepts (grouping <-> grouping)
        conn.execute(text("INSERT INTO topic_concepts (topic_id, concept_id) VALUES (:t, :c)"),
                     {"t": topic_id, "c": concept_id})
        # study note anchored to both a topic and (separately) a concept
        conn.execute(text(
            "INSERT INTO study_notes (topic_id, concept_tag, tagged_at) VALUES (:t, 'tag', :now)"
        ), {"t": topic_id, "now": _now()})
        conn.execute(text(
            "INSERT INTO study_notes (concept_id, concept_tag, tagged_at) VALUES (:c, 'tag', :now)"
        ), {"c": concept_id, "now": _now()})
        conn.commit()
    return {"q_id": q_id, "topic_id": topic_id, "concept_id": concept_id, "paper_id": paper_id}


def _grouping_id(conn, gtype, name):
    return conn.execute(text(
        "SELECT id FROM groupings WHERE type=:t AND name=:n"
    ), {"t": gtype, "n": name}).fetchone()[0]


def test_backfill_links_all_sources():
    engine = _make_engine()
    ids = _seed_links_fixture(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        gt = _grouping_id(conn, "topic", "stroke")
        gc = _grouping_id(conn, "concept", "LTP")

        def has(grouping_id, anchor_type, anchor_id, status):
            return conn.execute(text(
                "SELECT 1 FROM grouping_links WHERE grouping_id=:g AND anchor_type=:at "
                "AND anchor_id=:ai AND status=:s"
            ), {"g": grouping_id, "at": anchor_type, "ai": anchor_id, "s": status}).fetchone() is not None

        assert has(gt, "question", ids["q_id"], "pending")          # question_topics (status preserved)
        assert has(gc, "question", ids["q_id"], "confirmed")        # question_concepts
        assert has(gt, "paper", ids["paper_id"], "confirmed")       # paper_topics
        assert has(gc, "paper", ids["paper_id"], "confirmed")       # paper_concepts
        assert has(gt, "grouping", gc, "confirmed")                 # topic_concepts -> grouping<->grouping
        # study notes: one note anchored to topic, one to concept
        note_topic = conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links WHERE grouping_id=:g AND anchor_type='study_note'"
        ), {"g": gt}).fetchone()[0]
        note_concept = conn.execute(text(
            "SELECT COUNT(*) FROM grouping_links WHERE grouping_id=:g AND anchor_type='study_note'"
        ), {"g": gc}).fetchone()[0]
        assert note_topic == 1
        assert note_concept == 1


def test_backfill_links_idempotent():
    engine = _make_engine()
    _seed_links_fixture(engine)
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
    with engine.connect() as conn:
        before = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    with engine.connect() as conn:
        _migration_017_groupings(conn)
        conn.commit()
        after = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    assert before == after
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py::test_backfill_links_all_sources -v`
Expected: FAIL — assertions fail (no links inserted yet).

- [ ] **Step 3: Add the grouping_links backfill**

In `src/neurodb/db.py`, replace the line `    # --- Backfill grouping_links (Task 4) ---` with:

```python
    # --- Backfill grouping_links from join tables and study-note anchors ---
    now_iso = datetime.now(timezone.utc).isoformat()

    # question_topics -> (topic grouping, anchor='question'), status preserved
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'question', qt.question_id, qt.status, :now
        FROM question_topics qt
        JOIN topics t ON t.id = qt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'question' AND gl.anchor_id = qt.question_id
        )
    """), {"now": now_iso})

    # question_concepts -> (concept grouping, anchor='question'), status preserved
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'question', qc.question_id, qc.status, :now
        FROM question_concepts qc
        JOIN concepts c ON c.id = qc.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'question' AND gl.anchor_id = qc.question_id
        )
    """), {"now": now_iso})

    # paper_topics -> (topic grouping, anchor='paper')
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'paper', pt.paper_id, 'confirmed', :now
        FROM paper_topics pt
        JOIN topics t ON t.id = pt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'paper' AND gl.anchor_id = pt.paper_id
        )
    """), {"now": now_iso})

    # paper_concepts -> (concept grouping, anchor='paper')
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'paper', pc.paper_id, 'confirmed', :now
        FROM paper_concepts pc
        JOIN concepts c ON c.id = pc.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'paper' AND gl.anchor_id = pc.paper_id
        )
    """), {"now": now_iso})

    # dataset_packet_topics -> (topic grouping, anchor='dataset_packet')
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'dataset_packet', dpt.packet_id, 'confirmed', :now
        FROM dataset_packet_topics dpt
        JOIN topics t ON t.id = dpt.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'dataset_packet' AND gl.anchor_id = dpt.packet_id
        )
    """), {"now": now_iso})

    # topic_concepts -> (topic grouping, anchor='grouping' = concept grouping id)
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT gt.id, 'grouping', gc.id, 'confirmed', :now
        FROM topic_concepts tc
        JOIN topics t ON t.id = tc.topic_id
        JOIN concepts c ON c.id = tc.concept_id
        JOIN groupings gt ON gt.type = 'topic' AND gt.name = t.name
        JOIN groupings gc ON gc.type = 'concept' AND gc.name = c.name
        WHERE NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = gt.id AND gl.anchor_type = 'grouping' AND gl.anchor_id = gc.id
        )
    """), {"now": now_iso})

    # study_notes.topic_id -> (topic grouping, anchor='study_note')
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'study_note', sn.id, 'confirmed', :now
        FROM study_notes sn
        JOIN topics t ON t.id = sn.topic_id
        JOIN groupings g ON g.type = 'topic' AND g.name = t.name
        WHERE sn.topic_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'study_note' AND gl.anchor_id = sn.id
        )
    """), {"now": now_iso})

    # study_notes.concept_id -> (concept grouping, anchor='study_note')
    conn.execute(text("""
        INSERT INTO grouping_links (grouping_id, anchor_type, anchor_id, status, created_at)
        SELECT g.id, 'study_note', sn.id, 'confirmed', :now
        FROM study_notes sn
        JOIN concepts c ON c.id = sn.concept_id
        JOIN groupings g ON g.type = 'concept' AND g.name = c.name
        WHERE sn.concept_id IS NOT NULL
          AND NOT EXISTS (
            SELECT 1 FROM grouping_links gl
            WHERE gl.grouping_id = g.id AND gl.anchor_type = 'study_note' AND gl.anchor_id = sn.id
        )
    """), {"now": now_iso})
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/db.py tests/unit/test_migration_017_groupings.py
git commit -m "feat(groupings): backfill grouping_links from join tables and study-note anchors"
```

---

### Task 5: End-to-end parity + idempotency via the real init path

**Files:**
- Test: `tests/unit/test_migration_017_groupings.py` (append)

This task adds no production code — it proves the migration behaves correctly when applied through the normal `apply_migrations` path (the gated runner, not a direct call) and that a full re-init is a no-op.

- [ ] **Step 1: Write the test**

Append to `tests/unit/test_migration_017_groupings.py`:

```python
from neurodb.migrations import apply_migrations, get_schema_version
from neurodb.db import _MIGRATIONS


def test_full_migration_run_backfills_and_records_version():
    engine = _make_engine()
    _seed_links_fixture(engine)
    # Apply ALL migrations through the gated runner, as init_db would.
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        groupings = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        links = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    # 1 topic + 1 concept seeded
    assert groupings == 2
    # question_topics, question_concepts, paper_topics, paper_concepts,
    # dataset_packet_topics(0), topic_concepts, study_note(topic), study_note(concept) = 7 links
    assert links == 7
    assert get_schema_version(engine) >= 17


def test_reapplying_all_migrations_is_noop():
    engine = _make_engine()
    _seed_links_fixture(engine)
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        g1 = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        l1 = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    # Second run: version gate skips 017 entirely; counts unchanged.
    apply_migrations(engine, _MIGRATIONS)
    with engine.connect() as conn:
        g2 = conn.execute(text("SELECT COUNT(*) FROM groupings")).fetchone()[0]
        l2 = conn.execute(text("SELECT COUNT(*) FROM grouping_links")).fetchone()[0]
    assert (g1, l1) == (g2, l2)
```

> If `test_full_migration_run_backfills_and_records_version` reports a different `links` count, reconcile by printing `SELECT anchor_type, COUNT(*) FROM grouping_links GROUP BY anchor_type` — the expected breakdown is question:2, paper:2, grouping:1, study_note:2. Do not change the assertion to match a wrong number; find why a source row was missed or duplicated.

- [ ] **Step 2: Run the tests**

Run: `uv run pytest tests/unit/test_migration_017_groupings.py -v`
Expected: PASS (9 tests).

- [ ] **Step 3: Run the full suite (no regressions)**

Run: `uv run pytest tests/ -q`
Expected: no new failures beyond those already tracked in `docs/testLog.md`.

- [ ] **Step 4: Commit**

```bash
git add tests/unit/test_migration_017_groupings.py
git commit -m "test(groupings): end-to-end backfill parity and idempotency via apply_migrations"
```

---

## Phase 1 Done When

- `groupings` and `grouping_links` exist as ORM models and are created by `init_db`.
- Migration `017` is registered and backfills both tables idempotently from `topics`, `concepts`, and all six join tables plus `study_notes` anchors.
- No production code reads the new tables yet (legacy tables remain the source of truth).
- `uv run pytest tests/ -q` is green (no new failures vs. `docs/testLog.md`).

## Out of Scope for Phase 1 (later phases)

- The type registry, hierarchy invariant, and any store/engine functions → **Phase 2**.
- Cutting the question workflow over + semantic/proposal matcher + seeding the `plasticity`/`stroke` hierarchy → **Phase 3**.
- Migrating papers/datasets/notes/bundles consumers → **Phase 4**.
- Dropping legacy tables → **Phase 5**.
- `docs/projectStatus.md` phase-row / active-focus updates are made by the implementing session when Phase 1 lands, per CLAUDE.md sync rules.
