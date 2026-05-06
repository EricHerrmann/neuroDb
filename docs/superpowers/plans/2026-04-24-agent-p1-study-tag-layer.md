# Study Tag Layer (Agent P1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a `study_notes` table to DuckDB with a Python module for tagging, a CLI script, and a Streamlit Study Log page so datasets can be linked to neuroscience concepts encountered during reading.

**Architecture:** Core tag/list/search logic lives in `src/neurodb/study.py` (following the `provenance.py` pattern). `scripts/study.py` is a thin CLI wrapper. The Streamlit UI adds a Study Log sidebar page and an inline tag expander to the Dataset Browser. `app.py` is updated to connect to DuckDB (it currently points to SQLite) and adds Study Log navigation.

**Tech Stack:** Python 3.12, SQLAlchemy 2.x ORM, DuckDB via duckdb-engine, Streamlit, pytest, uv

**Spec:** `docs/superpowers/specs/2026-04-24-neuro-learning-agent-design.md` — P1 section

**Note:** P2 (embedding layer), P3 (agent), and P4 (context persistence) are separate plans that follow after this plan's manual test plan is signed off.

---

## File Map

| File | Action | Responsibility |
|------|--------|----------------|
| `src/neurodb/schema.py` | Modify | Add `StudyNote` SQLAlchemy model |
| `src/neurodb/study.py` | Create | `tag_dataset`, `list_tags`, `search_tags` — pure functions over a Session |
| `scripts/study.py` | Create | CLI wrapper: `tag`, `list`, `search` subcommands |
| `src/neurodb/ui/app.py` | Modify | Switch SQLite → DuckDB; add all connector imports; add Study Log nav |
| `src/neurodb/ui/pages/study_log.py` | Create | Browse/filter tags; tag-by-ID form |
| `src/neurodb/ui/pages/datasets.py` | Modify | Add inline "Tag a dataset" expander below search results |
| `tests/unit/test_study_notes.py` | Create | Schema and study module unit tests |
| `tests/integration/test_study_tag_flow.py` | Create | Full tag round-trip integration test |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_agent_p1.md` | Create | Manual test plan for phase gate |

---

## Task 1: Add StudyNote model to schema

**Files:**
- Modify: `src/neurodb/schema.py`
- Create: `tests/unit/test_study_notes.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_study_notes.py`:

```python
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, IngestRun, StudyNote


def test_schema_includes_study_notes_table():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    inspector = inspect(engine)
    assert "study_notes" in inspector.get_table_names()


def test_study_note_saves_required_fields():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.flush()
        note = StudyNote(
            index_id=idx.id,
            concept_tag="primary visual cortex",
            tagged_at="2026-04-24T00:00:00+00:00",
        )
        session.add(note)
        session.commit()
        result = session.query(StudyNote).one()
        assert result.concept_tag == "primary visual cortex"
        assert result.section_ref is None
        assert result.note_text is None
        assert result.index_id == idx.id


def test_study_note_saves_optional_fields():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add(idx)
        session.flush()
        note = StudyNote(
            index_id=idx.id,
            concept_tag="retinotopic mapping",
            section_ref="Augustine Ch13 p.312",
            note_text="V1 topographic organization matches discussion",
            tagged_at="2026-04-24T00:00:00+00:00",
        )
        session.add(note)
        session.commit()
        result = session.query(StudyNote).one()
        assert result.section_ref == "Augustine Ch13 p.312"
        assert result.note_text == "V1 topographic organization matches discussion"
```

- [ ] **Step 2: Run tests to confirm they fail**

```bash
uv run pytest tests/unit/test_study_notes.py -v
```

Expected: FAIL — `ImportError: cannot import name 'StudyNote' from 'neurodb.schema'`

- [ ] **Step 3: Add StudyNote to schema.py**

Open `src/neurodb/schema.py`. After the `QualityEvent` class, add:

```python
class StudyNote(Base):
    __tablename__ = "study_notes"

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

No other changes to `schema.py` needed.

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_study_notes.py -v
```

Expected: 3 PASSED

- [ ] **Step 5: Confirm full test suite still passes**

```bash
uv run pytest tests/ -v
```

Expected: all existing tests pass (no regressions)

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_study_notes.py
git commit -m "feat: add StudyNote schema model for study tag layer"
```

---

## Task 2: Create neurodb.study module with tag_dataset

**Files:**
- Create: `src/neurodb/study.py`
- Modify: `tests/unit/test_study_notes.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/unit/test_study_notes.py`:

```python
from neurodb.study import tag_dataset


def test_tag_dataset_creates_study_note():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        session.add(idx)
        session.flush()
        note = tag_dataset(session, "dandi", "000003", "hippocampus", section_ref="Augustine Ch24")
        session.commit()
    assert note is not None
    assert note.concept_tag == "hippocampus"
    assert note.section_ref == "Augustine Ch24"
    assert note.note_text is None


def test_tag_dataset_returns_none_for_unknown_dataset():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        note = tag_dataset(session, "dandi", "does-not-exist", "hippocampus")
    assert note is None
```

- [ ] **Step 2: Run test to confirm failure**

```bash
uv run pytest tests/unit/test_study_notes.py::test_tag_dataset_creates_study_note -v
```

Expected: FAIL — `ImportError: cannot import name 'tag_dataset' from 'neurodb.study'`

- [ ] **Step 3: Create src/neurodb/study.py**

```python
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, StudyNote


def tag_dataset(
    session: Session,
    source: str,
    source_id: str,
    concept_tag: str,
    section_ref: str | None = None,
    note_text: str | None = None,
) -> StudyNote | None:
    """Create a study note linking a dataset to a concept tag.

    Returns the new StudyNote, or None if (source, source_id) is not in datasets_index.
    Caller is responsible for session.commit().
    """
    idx = session.execute(
        select(DatasetIndex).where(
            DatasetIndex.source == source,
            DatasetIndex.source_id == source_id,
        )
    ).scalar_one_or_none()
    if idx is None:
        return None
    note = StudyNote(
        index_id=idx.id,
        concept_tag=concept_tag,
        section_ref=section_ref,
        note_text=note_text,
        tagged_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(note)
    session.flush()
    return note
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_study_notes.py -v
```

Expected: all 5 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/study.py tests/unit/test_study_notes.py
git commit -m "feat: add tag_dataset function to neurodb.study"
```

---

## Task 3: Add list_tags and search_tags to study module

**Files:**
- Modify: `src/neurodb/study.py`
- Modify: `tests/unit/test_study_notes.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/unit/test_study_notes.py`:

```python
from neurodb.study import list_tags, search_tags


def _engine_with_two_tags():
    engine = create_engine("sqlite:///:memory:")
    DatasetIndex.metadata.create_all(engine)
    with Session(engine) as session:
        run = IngestRun(source="test", run_at="2026-01-01T00:00:00", version="0.1")
        session.add(run)
        session.flush()
        idx1 = DatasetIndex(source="dandi", source_id="000003", run_id=run.id)
        idx2 = DatasetIndex(source="openneuro", source_id="ds001", run_id=run.id)
        session.add_all([idx1, idx2])
        session.flush()
        session.add(StudyNote(
            index_id=idx1.id,
            concept_tag="primary visual cortex",
            section_ref="Augustine Ch13",
            note_text="V1 electrode recordings",
            tagged_at="2026-04-24T00:00:00+00:00",
        ))
        session.add(StudyNote(
            index_id=idx2.id,
            concept_tag="auditory cortex",
            tagged_at="2026-04-23T00:00:00+00:00",
        ))
        session.commit()
    return engine


def test_list_tags_returns_all():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session)
    assert len(results) == 2
    concepts = {r["concept_tag"] for r in results}
    assert concepts == {"primary visual cortex", "auditory cortex"}


def test_list_tags_filters_by_concept():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session, concept="visual")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "primary visual cortex"


def test_list_tags_filters_by_source():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = list_tags(session, source="openneuro")
    assert len(results) == 1
    assert results[0]["source_id"] == "ds001"


def test_search_tags_matches_concept():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "visual")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "primary visual cortex"


def test_search_tags_matches_note_text():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "electrode")
    assert len(results) == 1
    assert results[0]["note_text"] == "V1 electrode recordings"


def test_search_tags_no_match_returns_empty():
    engine = _engine_with_two_tags()
    with Session(engine) as session:
        results = search_tags(session, "somatosensory")
    assert results == []
```

- [ ] **Step 2: Run tests to confirm failure**

```bash
uv run pytest tests/unit/test_study_notes.py -v
```

Expected: FAIL — `ImportError: cannot import name 'list_tags' from 'neurodb.study'`

- [ ] **Step 3: Add list_tags and search_tags to src/neurodb/study.py**

Append after `tag_dataset`:

```python
def list_tags(
    session: Session,
    concept: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Return study notes with dataset info, optionally filtered.

    concept: substring match against concept_tag (case-insensitive)
    source: exact match against datasets_index.source
    """
    rows = session.execute(
        select(StudyNote, DatasetIndex)
        .join(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note, idx = row.StudyNote, row.DatasetIndex
        if concept and concept.lower() not in note.concept_tag.lower():
            continue
        if source and source != idx.source:
            continue
        results.append({
            "source": idx.source,
            "source_id": idx.source_id,
            "concept_tag": note.concept_tag,
            "section_ref": note.section_ref,
            "note_text": note.note_text,
            "tagged_at": note.tagged_at,
        })
    return results


def search_tags(session: Session, keyword: str) -> list[dict]:
    """Return notes where keyword appears in concept_tag, note_text, or section_ref."""
    kw = keyword.lower()
    rows = session.execute(
        select(StudyNote, DatasetIndex)
        .join(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note, idx = row.StudyNote, row.DatasetIndex
        in_concept = kw in note.concept_tag.lower()
        in_note = note.note_text and kw in note.note_text.lower()
        in_section = note.section_ref and kw in note.section_ref.lower()
        if in_concept or in_note or in_section:
            results.append({
                "source": idx.source,
                "source_id": idx.source_id,
                "concept_tag": note.concept_tag,
                "section_ref": note.section_ref,
                "note_text": note.note_text,
                "tagged_at": note.tagged_at,
            })
    return results
```

- [ ] **Step 4: Run tests to confirm they pass**

```bash
uv run pytest tests/unit/test_study_notes.py -v
```

Expected: all 11 tests PASSED

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/study.py tests/unit/test_study_notes.py
git commit -m "feat: add list_tags and search_tags to neurodb.study"
```

---

## Task 4: Integration test — full tag round-trip

**Files:**
- Create: `tests/integration/test_study_tag_flow.py`

- [ ] **Step 1: Write the integration test**

Create `tests/integration/test_study_tag_flow.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.db import init_db, get_session
from neurodb.schema import DatasetIndex, IngestRun, StudyNote
from neurodb.study import tag_dataset, list_tags, search_tags


def _engine_with_dataset(source: str, source_id: str):
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    with get_session(engine) as session:
        run = IngestRun(source=source, run_at="2026-04-24T00:00:00+00:00", version="0.1")
        session.add(run)
        session.flush()
        idx = DatasetIndex(source=source, source_id=source_id, run_id=run.id)
        session.add(idx)
    return engine


def test_tag_then_list_round_trip():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source="dandi",
            source_id="000003",
            concept_tag="primary visual cortex",
            section_ref="Augustine Ch13 p.312",
            note_text="V1 electrode recordings confirm retinotopic org",
        )
    assert note is not None
    assert note.id is not None

    with get_session(engine) as session:
        tags = list_tags(session)
    assert len(tags) == 1
    assert tags[0]["concept_tag"] == "primary visual cortex"
    assert tags[0]["source"] == "dandi"
    assert tags[0]["source_id"] == "000003"
    assert tags[0]["section_ref"] == "Augustine Ch13 p.312"


def test_tag_then_search_round_trip():
    engine = _engine_with_dataset("openneuro", "ds003684")
    with get_session(engine) as session:
        tag_dataset(
            session,
            source="openneuro",
            source_id="ds003684",
            concept_tag="auditory cortex",
            note_text="fMRI paradigm matches tonotopy discussion",
        )

    with get_session(engine) as session:
        results = search_tags(session, "tonotopy")
    assert len(results) == 1
    assert results[0]["concept_tag"] == "auditory cortex"


def test_double_tag_creates_two_rows():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        tag_dataset(session, "dandi", "000003", "primary visual cortex")
        tag_dataset(session, "dandi", "000003", "retinotopic mapping")

    with get_session(engine) as session:
        count = session.query(StudyNote).count()
    assert count == 2


def test_tag_unknown_dataset_returns_none():
    engine = _engine_with_dataset("dandi", "000003")
    with get_session(engine) as session:
        result = tag_dataset(session, "dandi", "not-in-db", "some concept")
    assert result is None

    with get_session(engine) as session:
        assert session.query(StudyNote).count() == 0
```

- [ ] **Step 2: Run integration test**

```bash
uv run pytest tests/integration/test_study_tag_flow.py -v
```

Expected: 4 PASSED

- [ ] **Step 3: Run full suite to confirm no regressions**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_study_tag_flow.py
git commit -m "test: integration test for study tag round-trip"
```

---

## Task 5: Create study.py CLI script

**Files:**
- Create: `scripts/study.py`

- [ ] **Step 1: Create scripts/study.py**

```python
#!/usr/bin/env python
"""CLI: study tag operations for NeuroDb.

Usage:
    uv run scripts/study.py tag --source dandi --id 000003 --concept "primary visual cortex"
    uv run scripts/study.py tag --source dandi --id 000003 --concept "V1" --section "Augustine Ch13" --note "electrode recordings"
    uv run scripts/study.py list
    uv run scripts/study.py list --concept "visual" --source dandi
    uv run scripts/study.py search retinotopic
"""
import argparse

from neurodb.db import get_engine, get_session, init_db
from neurodb.study import list_tags, search_tags, tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def cmd_tag(args):
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    with get_session(engine) as session:
        note = tag_dataset(
            session,
            source=args.source,
            source_id=args.id,
            concept_tag=args.concept,
            section_ref=args.section or None,
            note_text=args.note or None,
        )
    if note is None:
        print(f"Dataset not found: {args.source}:{args.id} — run ingest first")
        return
    print(f"Tagged {args.source}:{args.id} → '{args.concept}'")


def cmd_list(args):
    engine = get_engine(f"duckdb:///{args.db}")
    with get_session(engine) as session:
        tags = list_tags(session, concept=args.concept or None, source=args.source or None)
    if not tags:
        print("No tags found.")
        return
    for t in tags:
        print(f"[{t['source']}:{t['source_id']}] {t['concept_tag']}")
        if t["section_ref"]:
            print(f"  Section: {t['section_ref']}")
        if t["note_text"]:
            print(f"  Note:    {t['note_text']}")
        print(f"  Tagged:  {t['tagged_at']}")
        print()


def cmd_search(args):
    engine = get_engine(f"duckdb:///{args.db}")
    with get_session(engine) as session:
        tags = search_tags(session, args.keyword)
    if not tags:
        print(f"No tags matching '{args.keyword}'")
        return
    for t in tags:
        print(f"[{t['source']}:{t['source_id']}] {t['concept_tag']}")
        if t["note_text"]:
            print(f"  Note: {t['note_text']}")
        print()


def main():
    parser = argparse.ArgumentParser(description="Study tag operations for NeuroDb")
    parser.add_argument("--db", default="neurodb.duckdb")
    sub = parser.add_subparsers(dest="cmd", required=True)

    tag_p = sub.add_parser("tag", help="Tag a dataset with a concept")
    tag_p.add_argument("--source", required=True, choices=SOURCES)
    tag_p.add_argument("--id", required=True, dest="id", metavar="SOURCE_ID")
    tag_p.add_argument("--concept", required=True)
    tag_p.add_argument("--section", default="", metavar="SECTION_REF")
    tag_p.add_argument("--note", default="")

    list_p = sub.add_parser("list", help="List study tags")
    list_p.add_argument("--concept", default="", help="Filter by concept substring")
    list_p.add_argument("--source", default="", choices=[""] + SOURCES)

    search_p = sub.add_parser("search", help="Search tags by keyword")
    search_p.add_argument("keyword")

    args = parser.parse_args()
    {"tag": cmd_tag, "list": cmd_list, "search": cmd_search}[args.cmd](args)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Smoke-test CLI (requires existing ingested data in neurodb.duckdb)**

```bash
uv run scripts/study.py list
```

Expected: `No tags found.` (or existing tags if any)

```bash
uv run scripts/study.py --help
```

Expected: help text printed without error

- [ ] **Step 3: Commit**

```bash
git add scripts/study.py
git commit -m "feat: study.py CLI for tag/list/search operations"
```

---

## Task 6: Update app.py — DuckDB connection and Study Log navigation

**Files:**
- Modify: `src/neurodb/ui/app.py`

The current `app.py` connects to SQLite (`sqlite:///neurodb.db`). This must be updated to DuckDB so the Study Log can read from the same database that ingest populates.

- [ ] **Step 1: Replace the full contents of src/neurodb/ui/app.py**

```python
"""
NeuroDb Explorer — local neuroscience dataset browser.

Run with:
    uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
"""
import sys

import streamlit as st

import neurodb.connectors.allen_brain  # noqa: F401 — registers AllenDataset
import neurodb.connectors.dandi  # noqa: F401 — registers DandiDataset
import neurodb.connectors.neurovault  # noqa: F401 — registers NeuroVaultDataset
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset
from neurodb.db import create_views, get_engine, init_db

st.set_page_config(page_title="NeuroDb Explorer", layout="wide")

db_path = "neurodb.duckdb"
for i, arg in enumerate(sys.argv):
    if arg == "--db" and i + 1 < len(sys.argv):
        db_path = sys.argv[i + 1]

engine = get_engine(f"duckdb:///{db_path}")
init_db(engine)
create_views(engine)

st.session_state["engine"] = engine

st.title("NeuroDb Explorer")
st.caption(f"Connected to: `{db_path}`")

page = st.sidebar.radio("Navigate", ["Dataset Browser", "SQL Query", "Study Log"])

if page == "Dataset Browser":
    from neurodb.ui.pages.datasets import render
    render(engine)
elif page == "SQL Query":
    from neurodb.ui.pages.query import render
    render(engine)
elif page == "Study Log":
    from neurodb.ui.pages.study_log import render
    render(engine)
```

- [ ] **Step 2: Confirm the import paths for all connectors exist**

```bash
python -c "import neurodb.connectors.allen_brain; import neurodb.connectors.dandi; import neurodb.connectors.neurovault; import neurodb.connectors.openneuro; print('OK')"
```

Expected: `OK`

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/app.py
git commit -m "fix: update app.py to DuckDB connection and add Study Log navigation"
```

---

## Task 7: Study Log page — browse and filter section

**Files:**
- Create: `src/neurodb/ui/pages/study_log.py`

- [ ] **Step 1: Create src/neurodb/ui/pages/study_log.py with browse section**

```python
import pandas as pd
import streamlit as st
from sqlalchemy import Engine, text

from neurodb.db import get_session
from neurodb.study import tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def _browse_section(engine: Engine) -> None:
    st.subheader("Your Study Tags")

    col1, col2 = st.columns(2)
    concept_filter = col1.text_input("Filter by concept", "")
    source_filter = col2.selectbox("Filter by source", ["All"] + SOURCES)

    conditions = []
    params: dict = {}
    if concept_filter:
        conditions.append("LOWER(sn.concept_tag) LIKE :concept")
        params["concept"] = f"%{concept_filter.lower()}%"
    if source_filter != "All":
        conditions.append("di.source = :source")
        params["source"] = source_filter

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""
    sql = text(f"""
        SELECT
            sn.concept_tag,
            sn.section_ref,
            sn.note_text,
            sn.tagged_at,
            di.source,
            di.source_id
        FROM study_notes sn
        JOIN datasets_index di ON di.id = sn.index_id
        {where}
        ORDER BY sn.tagged_at DESC
    """)  # noqa: S608

    with engine.connect() as conn:
        result = conn.execute(sql, params)
        rows = result.fetchall()
        cols = list(result.keys())

    if not rows:
        st.info("No study tags yet. Tag a dataset from the Dataset Browser or use the form below.")
        return

    df = pd.DataFrame(rows, columns=cols)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(rows)} tag(s)")


def render(engine: Engine) -> None:
    st.header("Study Log")
    _browse_section(engine)
```

- [ ] **Step 2: Start Streamlit and verify the browse section renders**

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`, navigate to **Study Log** in the sidebar.

Expected:
- Study Log header visible
- Filter inputs rendered
- "No study tags yet" info message (if DB is empty) or tag rows in dataframe

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/pages/study_log.py
git commit -m "feat: Study Log page with browse and filter section"
```

---

## Task 8: Study Log page — tag by ID form

**Files:**
- Modify: `src/neurodb/ui/pages/study_log.py`

- [ ] **Step 1: Add _tag_form_section and call it from render**

Replace the `render` function and add `_tag_form_section` in `src/neurodb/ui/pages/study_log.py`:

```python
def _tag_form_section(engine: Engine) -> None:
    st.subheader("Tag a Dataset by ID")
    st.caption("Use source IDs from the Dataset Browser or SQL Query results.")

    with st.form("tag_by_id_form", clear_on_submit=True):
        source = st.selectbox("Source", SOURCES)
        source_id = st.text_input("Source ID", placeholder="e.g. 000003 (DANDI) or ds003684 (OpenNeuro)")
        concept = st.text_input("Concept tag *", placeholder="e.g. primary visual cortex")
        section = st.text_input("Section reference", placeholder="e.g. Augustine Ch13 p.312")
        note = st.text_area("Note", placeholder="What you observed, confirmed, or questioned")
        submitted = st.form_submit_button("Save Tag")

    if submitted:
        if not source_id.strip():
            st.error("Source ID is required.")
        elif not concept.strip():
            st.error("Concept tag is required.")
        else:
            with get_session(engine) as session:
                result = tag_dataset(
                    session,
                    source=source,
                    source_id=source_id.strip(),
                    concept_tag=concept.strip(),
                    section_ref=section.strip() or None,
                    note_text=note.strip() or None,
                )
            if result is None:
                st.error(f"Dataset not found: `{source}:{source_id.strip()}` — run ingest first.")
            else:
                st.success(f"Tagged `{source}:{source_id.strip()}` → '{concept.strip()}'")
                st.rerun()


def render(engine: Engine) -> None:
    st.header("Study Log")
    _browse_section(engine)
    st.divider()
    _tag_form_section(engine)
```

- [ ] **Step 2: Verify the form works end-to-end**

With ingest already run (`uv run scripts/ingest.py --source dandi --limit 5`):

1. Navigate to **Study Log** in the sidebar
2. Fill in: Source = `dandi`, Source ID = (a DANDI ID from the Dataset Browser), Concept tag = `test concept`
3. Click **Save Tag**

Expected: green success message; the Browse section above updates to show the new tag after `st.rerun()`.

Test the error case: enter a source ID that doesn't exist, click Save.
Expected: red error message "Dataset not found".

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/pages/study_log.py
git commit -m "feat: add tag-by-ID form to Study Log page"
```

---

## Task 9: Dataset Browser — inline tag expander

**Files:**
- Modify: `src/neurodb/ui/pages/datasets.py`

- [ ] **Step 1: Replace the full contents of src/neurodb/ui/pages/datasets.py**

```python
import pandas as pd
import streamlit as st
from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.query import search_datasets
from neurodb.study import tag_dataset

SOURCES = ["openneuro", "allen_brain", "neurovault", "dandi"]


def render(engine: Engine) -> None:
    st.header("Dataset Browser")

    col1, col2 = st.columns(2)
    keyword = col1.text_input("Search title/description", "")
    modality = col2.selectbox("Modality", ["Any", "MRI", "fMRI", "EEG", "MEG", "ISH"])

    with get_session(engine) as session:
        results = search_datasets(
            session,
            keyword=keyword or None,
            modality=None if modality == "Any" else modality,
        )

    if not results:
        st.info("No datasets found. Run an ingest first: `uv run scripts/ingest.py --source openneuro`")
        return

    data = [
        {
            "source": r["source"],
            "source_id": r["source_id"],
            "title": r["title"],
            "modality": r["modality"],
            "n_subjects": r["n_subjects"],
        }
        for r in results
    ]
    df = pd.DataFrame(data)
    st.dataframe(df, use_container_width=True)
    st.caption(f"{len(results)} dataset(s) found")

    with st.expander("Tag a dataset from these results"):
        display_options = [f"{r['source']}:{r['source_id']}" for r in results]

        with st.form("inline_tag_form", clear_on_submit=True):
            selected = st.selectbox("Dataset", display_options)
            concept = st.text_input("Concept tag *", placeholder="e.g. retinotopic mapping")
            section = st.text_input("Section reference", placeholder="e.g. Augustine Ch13 p.312")
            note = st.text_area("Note", placeholder="What you observed or confirmed")
            submitted = st.form_submit_button("Save Tag")

        if submitted:
            if not concept.strip():
                st.error("Concept tag is required.")
            else:
                src, sid = selected.split(":", 1)
                with get_session(engine) as session:
                    result = tag_dataset(
                        session,
                        source=src,
                        source_id=sid,
                        concept_tag=concept.strip(),
                        section_ref=section.strip() or None,
                        note_text=note.strip() or None,
                    )
                if result is None:
                    st.error(f"Dataset not found in index: {selected}")
                else:
                    st.success(f"Tagged {selected} → '{concept.strip()}'")
```

- [ ] **Step 2: Verify the inline tag expander works**

1. Run a search that returns results
2. Open the "Tag a dataset from these results" expander
3. Select a dataset, enter a concept tag, click Save Tag

Expected: green success message. Navigate to Study Log to confirm the tag appears.

- [ ] **Step 3: Run the full test suite**

```bash
uv run pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add src/neurodb/ui/pages/datasets.py
git commit -m "feat: add inline tag expander to Dataset Browser"
```

---

## Task 10: Write manual test plan

**Files:**
- Create: `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_agent_p1.md`

- [ ] **Step 1: Create the manual test plan**

```markdown
# Agent P1 Manual Test Plan — Study Tag Layer

**Status:** Pending
**Tester:** Eric Herrmann
**Scope:** StudyNote schema, study.py CLI, Study Log UI, Dataset Browser inline tag
**Date:** <!-- fill in on execution -->

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

```bash
git status        # confirm on main, clean working tree
uv sync           # install dependencies
uv run pytest tests/ -v   # all automated tests must pass before starting
```

Ensure at least one source is ingested:

```bash
uv run scripts/ingest.py --source dandi --limit 10
```

---

## Test 1 — CLI: tag command

```bash
# Get a DANDI source_id from the DB first
uv run scripts/query_cli.py --sql "SELECT source_id FROM dandi_datasets LIMIT 1"
```

Note the source_id returned (e.g. `000003`). Then:

```bash
uv run scripts/study.py tag \
  --source dandi \
  --id <source_id_from_above> \
  --concept "hippocampus spatial navigation" \
  --section "Augustine Ch24 p.580" \
  --note "electrophysiology confirms place cells"
```

| # | Step | Expected |
|---|------|----------|
| 1.1 | Command exits without error | `Tagged dandi:<id> → 'hippocampus spatial navigation'` |
| 1.2 | Tag visible in DB | See query below |

```bash
uv run scripts/query_cli.py --sql "SELECT concept_tag, section_ref, note_text FROM study_notes"
```

| # | Step | Expected |
|---|------|----------|
| 1.3 | Row appears in study_notes | concept_tag = `hippocampus spatial navigation` |
| 1.4 | section_ref populated | `Augustine Ch24 p.580` |
| 1.5 | note_text populated | `electrophysiology confirms place cells` |

---

## Test 2 — CLI: tag unknown dataset

```bash
uv run scripts/study.py tag --source dandi --id NOT-A-REAL-ID --concept "test"
```

| # | Step | Expected |
|---|------|----------|
| 2.1 | Error message printed | `Dataset not found: dandi:NOT-A-REAL-ID — run ingest first` |
| 2.2 | No row created | study_notes count unchanged |

---

## Test 3 — CLI: list command

```bash
uv run scripts/study.py list
```

| # | Step | Expected |
|---|------|----------|
| 3.1 | Tag from Test 1 appears | source, source_id, concept_tag, note visible |

```bash
uv run scripts/study.py list --concept "hippo"
```

| # | Step | Expected |
|---|------|----------|
| 3.2 | Filtered to matching tags | Only tags containing "hippo" in concept_tag shown |

---

## Test 4 — CLI: search command

```bash
uv run scripts/study.py search "place cells"
```

| # | Step | Expected |
|---|------|----------|
| 4.1 | Tag from Test 1 returned | note_text "place cells" match surfaces the tag |

```bash
uv run scripts/study.py search "somatosensory"
```

| # | Step | Expected |
|---|------|----------|
| 4.2 | No match | `No tags matching 'somatosensory'` |

---

## Test 5 — UI: Study Log browse section

```bash
uv run streamlit run src/neurodb/ui/app.py
```

Open `http://localhost:8501`.

| # | Step | Expected |
|---|------|----------|
| 5.1 | App connects to DuckDB | Caption shows `neurodb.duckdb` |
| 5.2 | Study Log appears in sidebar | Third nav option visible |
| 5.3 | Navigate to Study Log | Page loads without error |
| 5.4 | Tag from Test 1 appears in table | Row visible with correct concept_tag and note |
| 5.5 | Concept filter works | Type "hippo" → only matching tags shown |
| 5.6 | Source filter works | Select "openneuro" → dandi tags hidden |

---

## Test 6 — UI: Study Log tag-by-ID form

| # | Step | Expected |
|---|------|----------|
| 6.1 | Tag-by-ID form visible below Browse section | Form with Source, Source ID, Concept tag fields |
| 6.2 | Submit with valid source ID | Green success message; Browse section updates |
| 6.3 | Submit with unknown source ID | Red error: "Dataset not found" |
| 6.4 | Submit with empty concept tag | Red error: "Concept tag is required" |

---

## Test 7 — UI: Dataset Browser inline tag expander

Navigate to **Dataset Browser**. Run a search that returns results.

| # | Step | Expected |
|---|------|----------|
| 7.1 | "Tag a dataset from these results" expander visible | Below the results dataframe |
| 7.2 | Expander opens to form | Dataset selectbox populated with results |
| 7.3 | Submit tag for a dataset | Green success message |
| 7.4 | Navigate to Study Log | New tag appears |

---

## Pass Criteria

- [ ] `uv run pytest tests/ -v` — all tests pass
- [ ] CLI tag creates a row in study_notes with correct fields
- [ ] CLI tag on unknown dataset prints error and creates no row
- [ ] CLI list and search return correct results
- [ ] Streamlit app connects to `neurodb.duckdb` (not SQLite)
- [ ] Study Log browse section shows tags and filters work
- [ ] Study Log tag-by-ID form saves tags and shows errors correctly
- [ ] Dataset Browser inline expander saves tags and they appear in Study Log

**Sign-off:** _________________________________ Date: _____________
```

- [ ] **Step 2: Commit**

```bash
git add docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_agent_p1.md
git commit -m "docs: manual test plan for Agent P1 study tag layer"
```

---

## Self-Review Checklist (complete before handing off)

- [ ] All imports in test files match names exported from `neurodb.schema` and `neurodb.study`
- [ ] `StudyNote` is added to the import in `tests/unit/test_study_notes.py` — confirm the `from neurodb.schema import ..., StudyNote` line is present
- [ ] The `_engine_with_two_tags` helper in unit tests creates an `IngestRun` (required for FK chain: IngestRun → DatasetIndex → StudyNote)
- [ ] Tasks 2 and 3 append `from neurodb.study import ...` mid-file — valid Python, but move these to the top of the file alongside the other imports when implementing to keep linting clean
- [ ] `study.py` CLI imports `neurodb.connectors` — it does NOT; that's correct since the CLI doesn't register connector models (only `init_db` is needed)
- [ ] `app.py` calls `create_views(engine)` — confirmed in Task 6 code
- [ ] Manual test plan references real source IDs obtained from the DB at test time (not hardcoded), because different ingest runs may return different IDs

---

*Plan authored: 2026-04-24. Implements spec: `docs/superpowers/specs/2026-04-24-neuro-learning-agent-design.md` — P1.*
*P2 plan (embedding layer) is written after this plan's manual test plan is signed off.*
