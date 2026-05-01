# Learning Agent Enhancement Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform NeuroDb into a mode-aware learning agent aligned with chapter-by-chapter reading of *Neuroscience, 7th ed.* (Augustine et al.), with a Discovery mode that searches external sources and queues candidates for user review.

**Architecture:** A single `NeuroAgent` instance gains a `mode` attribute (`learning` | `discovery`) and a `chapter_context` attribute. In learning mode, only local-DB tools are passed to Claude. In discovery mode, four additional external tools are added. A `chapter_registry.py` module provides chapter → title + topics lookup for the UI confirmation flow. Three new DuckDB tables (`learning_sources`, `import_queue`, `source_suggestions`) support the registry, import queue, and suggestion queue. Two new Streamlit tabs (Suggestions, Learning Registry) expose these to the user.

**Tech Stack:** Python 3.12, SQLAlchemy ORM, DuckDB via duckdb-engine, Streamlit, httpx, Anthropic SDK, uv for test running.

---

## File Map

### New files
| File | Responsibility |
|---|---|
| `src/neurodb/chapter_registry.py` | Static lookup: book key → chapters → title + topics |
| `src/neurodb/discovery_tools.py` | Four discovery tool implementations + `DISCOVERY_TOOLS` schema list |
| `src/neurodb/ui/pages/suggestions.py` | Suggestions tab: import_queue + source_suggestions rows with action buttons |
| `src/neurodb/ui/pages/learning_registry.py` | Learning Registry tab: learning_sources grouped by type, add/remove |
| `tests/unit/test_chapter_registry.py` | Unit tests for registry lookup |
| `tests/unit/test_discovery_tools.py` | Unit tests for discovery tool write operations |
| `tests/integration/test_agent_modes.py` | Integration tests for mode-aware tool selection |
| `tests/integration/test_learning_sources.py` | Integration tests for DB seeding and idempotency |

### Modified files
| File | Change |
|---|---|
| `src/neurodb/schema.py` | Add `LearningSource`, `ImportQueue`, `SourceSuggestion` ORM models |
| `src/neurodb/db.py` | Add `seed_learning_sources(engine)` called from `init_db` |
| `src/neurodb/connectors/base.py` | Add optional `search_by_keyword` method (default raises NotImplementedError) |
| `src/neurodb/connectors/openneuro.py` | Implement `search_by_keyword(query, limit)` |
| `src/neurodb/agent.py` | Add `mode`, `chapter_context` attributes; `DISCOVERY_TOOLS` list; mode-aware `chat()` |
| `src/neurodb/ui/pages/chat.py` | Add mode toggle + chapter annotation above session controls |
| `src/neurodb/ui/app.py` | Add Suggestions and Learning Registry tabs |
| `NeuroDbGoals.md` | Update primary goal; defer hypothesis testing |
| `docs/projectStatus.md` | Update active focus and phase table |

---

## Task 1: Update Project Goals

**Files:**
- Modify: `NeuroDbGoals.md`
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Update NeuroDbGoals.md**

Replace the Goal Summary and Goal Detail sections with:

```markdown
# Neuro DB Plan

## Primary Goal: "Use NeuroDb as an AI-assisted learning platform grounded in structured reading of Neuroscience, 7th ed. (Augustine et al.), with the agent accumulating chapter-by-chapter knowledge as the user progresses through the book."

### Goal Detail
Real datasets provide evidence for textbook concepts; the agent connects reading to data.
The system is designed to grow beyond a single textbook — additional books, curated papers,
and promoted DB datasets are all first-class learning sources.

## Deferred Goal: Brain Plasticity Hypothesis Testing
The experience-dependent brain plasticity / language-culture hypothesis testing work
(DB Epochs 7–8) is preserved but deferred. It is the natural long-term output of a
mature learning layer: once chapter knowledge and tagged datasets accumulate, hypothesis
testing is the next logical step.
```

Keep all remaining sections (`# DB Epoch`, `## DB Purpose`, etc.) unchanged.

- [ ] **Step 2: Update projectStatus.md active focus and phase table**

Update the `Active focus` line and add the new learning agent phase row:

```markdown
**Active focus:** Learning Agent Enhancement — mode-aware agent, chapter registry, discovery tools, suggestions UI
**Next phase:** Learning Agent Enhancement → Deferred: Entity resolution (Phase 7)
```

Add to the Neuro Learning Agent Phases table:
```markdown
| P5 — Learning Agent Enhancement | ⏳ In progress | — | — |
```

- [ ] **Step 3: Commit**

```bash
git add NeuroDbGoals.md docs/projectStatus.md
git commit -m "docs: update primary goal to learning agent; defer hypothesis testing"
```

---

## Task 2: Chapter Registry Module

**Files:**
- Create: `src/neurodb/chapter_registry.py`
- Create: `tests/unit/test_chapter_registry.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_chapter_registry.py`:

```python
from neurodb.chapter_registry import lookup_chapter, REGISTRY


def test_known_chapter_returns_title_and_topics():
    result = lookup_chapter("augustine_7e", 12)
    assert result is not None
    assert result["title"] == "Central Visual Pathways"
    assert "retinotopy" in result["topics"]


def test_unknown_chapter_returns_none():
    result = lookup_chapter("augustine_7e", 999)
    assert result is None


def test_unknown_book_returns_none():
    result = lookup_chapter("unknown_book", 1)
    assert result is None


def test_registry_has_augustine_7e():
    assert "augustine_7e" in REGISTRY
    assert REGISTRY["augustine_7e"]["display_name"] == "Neuroscience, 7th ed. — Augustine et al."


def test_chapter_11_known():
    result = lookup_chapter("augustine_7e", 11)
    assert result is not None
    assert result["title"] == "Vision: The Eye"
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_chapter_registry.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.chapter_registry'`

- [ ] **Step 3: Create chapter_registry.py**

Create `src/neurodb/chapter_registry.py`:

```python
"""Static lookup for neuroscience textbook chapters and topics.

Add new books by inserting a new top-level key in REGISTRY.
Add new chapters by inserting into the book's 'chapters' dict.
The registry is built incrementally as the user reads — absent chapters
are handled gracefully by lookup_chapter returning None.
"""

REGISTRY: dict = {
    "augustine_7e": {
        "display_name": "Neuroscience, 7th ed. — Augustine et al.",
        "chapters": {
            1: {
                "title": "Studying the Nervous System",
                "topics": [
                    "neurons", "glia", "neural circuits", "brain imaging",
                    "model systems", "neuroanatomy overview",
                ],
            },
            2: {
                "title": "Electrical Signals of Nerve Cells",
                "topics": [
                    "resting membrane potential", "action potential",
                    "ion gradients", "Nernst equation", "Goldman equation",
                ],
            },
            3: {
                "title": "Voltage-Dependent Membrane Permeability",
                "topics": [
                    "voltage-gated channels", "sodium channel",
                    "potassium channel", "hodgkin-huxley", "channel gating",
                ],
            },
            4: {
                "title": "Ion Channels and Transporters",
                "topics": [
                    "ion channel structure", "selectivity filter",
                    "ligand-gated channels", "transporters", "pumps",
                ],
            },
            5: {
                "title": "Synaptic Transmission",
                "topics": [
                    "chemical synapse", "neuromuscular junction",
                    "vesicle release", "quantal transmission",
                    "EPSP", "IPSP", "synaptic delay",
                ],
            },
            6: {
                "title": "Neurotransmitters and Their Receptors",
                "topics": [
                    "glutamate", "GABA", "acetylcholine", "dopamine",
                    "serotonin", "norepinephrine", "ionotropic receptors",
                    "metabotropic receptors", "AMPA", "NMDA",
                ],
            },
            7: {
                "title": "Molecular Signaling within Neurons",
                "topics": [
                    "G proteins", "second messengers", "cAMP", "PKA",
                    "calcium signaling", "MAPK", "gene expression",
                ],
            },
            8: {
                "title": "Synaptic Plasticity",
                "topics": [
                    "LTP", "LTD", "Hebbian plasticity", "NMDA receptor",
                    "AMPA trafficking", "CaMKII", "metaplasticity",
                    "homeostatic plasticity",
                ],
            },
            9: {
                "title": "The Somatic Sensory System",
                "topics": [
                    "mechanoreceptors", "somatosensory cortex",
                    "dorsal column-medial lemniscal pathway",
                    "spinothalamic tract", "two-point discrimination",
                    "somatotopy", "receptive fields",
                ],
            },
            10: {
                "title": "Pain",
                "topics": [
                    "nociceptors", "substance P", "spinothalamic tract",
                    "gate control theory", "opioid receptors",
                    "chronic pain", "central sensitization",
                ],
            },
            11: {
                "title": "Vision: The Eye",
                "topics": [
                    "photoreceptors", "rods", "cones", "retina",
                    "phototransduction", "bipolar cells", "ganglion cells",
                    "optic nerve", "lateral geniculate nucleus",
                ],
            },
            12: {
                "title": "Central Visual Pathways",
                "topics": [
                    "retinotopy", "LGN", "V1 laminar organization",
                    "orientation selectivity", "ocular dominance columns",
                    "dorsal stream", "ventral stream",
                    "critical period plasticity", "V4", "MT",
                ],
            },
            13: {
                "title": "The Auditory System",
                "topics": [
                    "cochlea", "hair cells", "tonotopy", "auditory cortex",
                    "inferior colliculus", "sound localization",
                    "interaural time difference",
                ],
            },
            14: {
                "title": "The Vestibular System",
                "topics": [
                    "semicircular canals", "otolith organs", "vestibular nuclei",
                    "VOR", "balance", "spatial orientation",
                ],
            },
            15: {
                "title": "The Chemical Senses",
                "topics": [
                    "olfactory receptor neurons", "olfactory bulb",
                    "taste receptor cells", "gustatory cortex",
                    "pheromones", "olfactory coding",
                ],
            },
        },
    },
}


def lookup_chapter(book_key: str, chapter: int) -> dict | None:
    """Return {title, topics} for a chapter, or None if not found."""
    book = REGISTRY.get(book_key)
    if book is None:
        return None
    return book["chapters"].get(chapter)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_chapter_registry.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/chapter_registry.py tests/unit/test_chapter_registry.py
git commit -m "feat: add chapter registry with Augustine 7th ed. chapters 1-15"
```

---

## Task 3: New Schema ORM Models

**Files:**
- Modify: `src/neurodb/schema.py`
- Modify: `tests/unit/test_schema.py`

- [ ] **Step 1: Write failing tests**

Open `tests/unit/test_schema.py` and append:

```python
from neurodb.schema import LearningSource, ImportQueue, SourceSuggestion


def test_learning_source_tablename():
    assert LearningSource.__tablename__ == "learning_sources"


def test_import_queue_tablename():
    assert ImportQueue.__tablename__ == "import_queue"


def test_source_suggestion_tablename():
    assert SourceSuggestion.__tablename__ == "source_suggestions"


def test_learning_source_has_metadata_json_column():
    cols = {c.key for c in LearningSource.__table__.columns}
    assert "metadata_json" in cols
    assert "content_json" in cols
    assert "source_type" in cols
    assert "source_key" in cols


def test_import_queue_has_open_status_column():
    cols = {c.key for c in ImportQueue.__table__.columns}
    assert "status" in cols
    assert "metadata_json" in cols
    assert "chapter_ref" in cols


def test_source_suggestion_has_suggestion_type_column():
    cols = {c.key for c in SourceSuggestion.__table__.columns}
    assert "suggestion_type" in cols
    assert "metadata_json" in cols
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_schema.py -v -k "learning_source or import_queue or source_suggestion"
```

Expected: `ImportError: cannot import name 'LearningSource'`

- [ ] **Step 3: Add ORM models to schema.py**

Append to the end of `src/neurodb/schema.py`:

```python
class LearningSource(Base):
    """Registry of textbooks, papers, and datasets used as learning sources.

    One row per source. Books carry full chapter structure in content_json.
    source_type and added_by are open strings — new values require no migration.
    """
    __tablename__ = "learning_sources"

    id: Mapped[int] = mapped_column(Integer, Sequence("learning_sources_id_seq"), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[str] = mapped_column(String(32), nullable=False)
    added_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ImportQueue(Base):
    """Datasets suggested by the discovery agent, pending user confirmation.

    status is an open string: 'pending', 'imported', 'dismissed'.
    Nothing is ingested until the user confirms via the Suggestions UI tab.
    """
    __tablename__ = "import_queue"

    id: Mapped[int] = mapped_column(Integer, Sequence("import_queue_id_seq"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_at: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SourceSuggestion(Base):
    """New connectors or learning sources suggested by the discovery agent.

    suggestion_type and status are open strings.
    Accepted entries for new connectors require a separate engineering step.
    """
    __tablename__ = "source_suggestions"

    id: Mapped[int] = mapped_column(Integer, Sequence("source_suggestions_id_seq"), primary_key=True)
    suggestion_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_at: Mapped[str] = mapped_column(String(32), nullable=False)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_schema.py -v
```

Expected: all pass

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/schema.py tests/unit/test_schema.py
git commit -m "feat: add LearningSource, ImportQueue, SourceSuggestion ORM models"
```

---

## Task 4: DB Seeding from Chapter Registry

**Files:**
- Modify: `src/neurodb/db.py`
- Create: `tests/integration/test_learning_sources.py`

- [ ] **Step 1: Write failing tests**

Create `tests/integration/test_learning_sources.py`:

```python
import json
from sqlalchemy import create_engine, select
from neurodb.db import init_db, seed_learning_sources
from neurodb.schema import LearningSource


def test_seed_creates_augustine_row():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(LearningSource).where(LearningSource.source_key == "augustine_7e")
            ).scalar_one_or_none()
    assert row is not None
    assert row.source_type == "book"
    assert row.added_by == "seed"
    content = json.loads(row.content_json)
    assert "chapters" in content
    assert content["chapters"]["12"]["title"] == "Central Visual Pathways"


def test_seed_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    seed_learning_sources(engine)
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            count = s.query(LearningSource).filter_by(source_key="augustine_7e").count()
    assert count == 1
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_learning_sources.py -v
```

Expected: `ImportError: cannot import name 'seed_learning_sources'`

- [ ] **Step 3: Add seed_learning_sources to db.py**

Add the following function after `create_views` in `src/neurodb/db.py`. All imports are local to the function — no changes to the file header are needed.

```python
def seed_learning_sources(engine: Engine) -> None:
    """Seed learning_sources with the chapter registry. Idempotent — skips existing rows."""
    import json
    from datetime import datetime, timezone
    from sqlalchemy import select
    from sqlalchemy.orm import Session
    from neurodb.schema import LearningSource
    from neurodb.chapter_registry import REGISTRY

    with Session(engine) as session:
        for book_key, book in REGISTRY.items():
            existing = session.execute(
                select(LearningSource).where(LearningSource.source_key == book_key)
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(LearningSource(
                source_type="book",
                source_key=book_key,
                display_name=book["display_name"],
                content_json=json.dumps({
                    "chapters": {
                        str(ch_num): ch_data
                        for ch_num, ch_data in book["chapters"].items()
                    }
                }),
                metadata_json=None,
                added_by="seed",
                added_at=datetime.now(timezone.utc).isoformat(),
            ))
        session.commit()
```

Add `seed_learning_sources(engine)` at the end of `init_db`:

```python
def init_db(engine: Engine) -> None:
    Base.metadata.create_all(engine)
    seed_learning_sources(engine)
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_learning_sources.py -v
```

Expected: 2 passed

- [ ] **Step 5: Run full suite to confirm no regressions**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/db.py tests/integration/test_learning_sources.py
git commit -m "feat: seed learning_sources from chapter registry on init_db"
```

---

## Task 5: External Search on OpenNeuro Connector

**Files:**
- Modify: `src/neurodb/connectors/base.py`
- Modify: `src/neurodb/connectors/openneuro.py`
- Modify: `tests/integration/test_openneuro_ingest.py`

- [ ] **Step 1: Write failing test**

Append to `tests/integration/test_openneuro_ingest.py`:

```python
def test_search_by_keyword_returns_matching_datasets():
    connector = OpenNeuroConnector()
    search_body = {
        "data": {
            "datasets": {
                "edges": [
                    {"node": {
                        "id": "ds003787",
                        "name": "NYU Retinotopy Dataset",
                        "metadata": {"species": "Human", "modalities": ["mri"],
                                     "associatedPaperDOI": None, "ages": []},
                        "draft": {"readme": "Population receptive field mapping.",
                                  "description": {"BIDSVersion": "1.4.0"}},
                    }}
                ]
            }
        }
    }
    mock = MagicMock()
    mock.json.return_value = search_body
    mock.raise_for_status.return_value = None
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        results = connector.search_by_keyword("retinotopy", limit=5)
    assert len(results) == 1
    assert results[0]["id"] == "ds003787"
    assert results[0]["name"] == "NYU Retinotopy Dataset"
```

- [ ] **Step 2: Run test to verify it fails**

```bash
uv run pytest tests/integration/test_openneuro_ingest.py::test_search_by_keyword_returns_matching_datasets -v
```

Expected: `AttributeError: 'OpenNeuroConnector' object has no attribute 'search_by_keyword'`

- [ ] **Step 3: Add optional search_by_keyword to base connector**

In `src/neurodb/connectors/base.py`, append after `normalize_subject`:

```python
def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
    """Search the source API by keyword. Returns list of raw dataset dicts.
    Override in connectors that support keyword search. Default raises NotImplementedError.
    """
    raise NotImplementedError(f"{self.__class__.__name__} does not support keyword search.")
```

- [ ] **Step 4: Add _SEARCH_QUERY and search_by_keyword to openneuro.py**

In `src/neurodb/connectors/openneuro.py`, add after `_DATASET_BY_ID_QUERY`:

```python
_SEARCH_QUERY = """
query SearchDatasets($search: String, $first: Int) {
  datasets(search: $search, first: $first, orderBy: { created: descending }) {
    edges {
      node {
        id
        name
        metadata {
          species
          modalities
          associatedPaperDOI
          ages
        }
        draft {
          readme
          description {
            BIDSVersion
          }
        }
      }
    }
  }
}
"""
```

Add `search_by_keyword` method to `OpenNeuroConnector`, after `fetch_by_id`:

```python
def search_by_keyword(self, query: str, limit: int = 10) -> list[dict]:
    try:
        response = httpx.post(
            GRAPHQL_URL,
            json={"query": _SEARCH_QUERY, "variables": {"search": query, "first": limit}},
            timeout=30,
        )
        response.raise_for_status()
    except httpx.TimeoutException as e:
        raise RuntimeError(f"OpenNeuro request timed out ({GRAPHQL_URL})") from e
    except httpx.HTTPStatusError as e:
        raise RuntimeError(
            f"OpenNeuro API returned {e.response.status_code}: {e.response.text[:200]}"
        ) from e
    body = response.json()
    if body.get("errors"):
        msg = body["errors"][0]["message"]
        raise RuntimeError(f"OpenNeuro GraphQL error: {msg}")
    edges = body["data"]["datasets"]["edges"]
    return [edge["node"] for edge in edges]
```

- [ ] **Step 5: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_openneuro_ingest.py -v
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/connectors/base.py src/neurodb/connectors/openneuro.py tests/integration/test_openneuro_ingest.py
git commit -m "feat: add search_by_keyword to OpenNeuroConnector"
```

---

## Task 6: Discovery Tools Module

**Files:**
- Create: `src/neurodb/discovery_tools.py`
- Create: `tests/unit/test_discovery_tools.py`

- [ ] **Step 1: Write failing tests**

Create `tests/unit/test_discovery_tools.py`:

```python
import json
from unittest.mock import patch, MagicMock
from sqlalchemy import create_engine, select
from neurodb.db import init_db, seed_learning_sources
from neurodb.schema import ImportQueue, SourceSuggestion
from neurodb.discovery_tools import (
    run_search_external,
    run_suggest_import,
    run_suggest_learning_source,
    run_suggest_new_source,
)


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    return engine


def test_suggest_import_writes_pending_row():
    engine = _engine()
    result = json.loads(run_suggest_import(
        source="openneuro",
        source_id="ds003787",
        title="NYU Retinotopy Dataset",
        reason="Matches Ch12 retinotopy topics",
        chapter_ref="Ch12",
        metadata={},
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(select(ImportQueue).where(ImportQueue.source_id == "ds003787")).scalar_one()
    assert row.status == "pending"
    assert row.chapter_ref == "Ch12"


def test_suggest_learning_source_writes_source_suggestion():
    engine = _engine()
    result = json.loads(run_suggest_learning_source(
        suggestion_type="learning_source",
        reference="10.1167/19.10.23",
        display_name="Benson et al. 2018 retinotopy",
        reason="Primary paper for Ch12 retinotopic maps",
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(SourceSuggestion).where(SourceSuggestion.reference == "10.1167/19.10.23")
            ).scalar_one()
    assert row.status == "pending"
    assert row.suggestion_type == "learning_source"


def test_suggest_new_source_writes_new_connector_suggestion():
    engine = _engine()
    result = json.loads(run_suggest_new_source(
        reference="https://human.brain-map.org/",
        display_name="Allen Human Brain Atlas",
        reason="Contains human cortical gene expression data relevant to V1",
        engine=engine,
    ))
    assert result["success"] is True
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(SourceSuggestion).where(SourceSuggestion.suggestion_type == "new_connector")
            ).scalar_one()
    assert row.status == "pending"


def test_search_external_openneuro_returns_results():
    search_body = {
        "data": {
            "datasets": {
                "edges": [{"node": {
                    "id": "ds003787", "name": "NYU Retinotopy Dataset",
                    "metadata": {"modalities": ["mri"], "associatedPaperDOI": None,
                                 "ages": [], "species": "Human"},
                    "draft": {"readme": "pRF mapping", "description": {"BIDSVersion": "1.4.0"}},
                }}]
            }
        }
    }
    mock = MagicMock()
    mock.json.return_value = search_body
    mock.raise_for_status.return_value = None
    with patch("neurodb.connectors.openneuro.httpx.post", return_value=mock):
        result = json.loads(run_search_external("openneuro", "retinotopy"))
    assert len(result) == 1
    assert result[0]["id"] == "ds003787"
    assert result[0]["source"] == "openneuro"


def test_search_external_unknown_source_returns_error():
    result = json.loads(run_search_external("unknown_source", "retinotopy"))
    assert "error" in result
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/unit/test_discovery_tools.py -v
```

Expected: `ModuleNotFoundError: No module named 'neurodb.discovery_tools'`

- [ ] **Step 3: Create discovery_tools.py**

Create `src/neurodb/discovery_tools.py`:

```python
"""Discovery mode tool implementations for NeuroAgent.

These tools are only registered with Claude when the agent is in discovery mode.
They write to import_queue and source_suggestions — nothing is ingested automatically.
"""
import json
from datetime import datetime, timezone

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from neurodb.schema import ImportQueue, SourceSuggestion

_SUPPORTED_CONNECTORS = ("openneuro",)


def run_search_external(source: str, query: str, limit: int = 10) -> str:
    """Search external connector APIs by keyword. Returns JSON list of candidates."""
    if source == "all":
        results = []
        for name in _SUPPORTED_CONNECTORS:
            results.extend(_search_one(name, query, limit))
        return json.dumps(results)
    if source in _SUPPORTED_CONNECTORS:
        return json.dumps(_search_one(source, query, limit))
    return json.dumps({"error": f"Unknown source '{source}'. Supported: {list(_SUPPORTED_CONNECTORS)}"})


def _search_one(source: str, query: str, limit: int) -> list[dict]:
    if source == "openneuro":
        from neurodb.connectors.openneuro import OpenNeuroConnector
        try:
            raw_list = OpenNeuroConnector().search_by_keyword(query, limit=limit)
            return [{"source": "openneuro", **r} for r in raw_list]
        except Exception as exc:
            return [{"source": "openneuro", "error": str(exc)}]
    return []


def run_suggest_import(
    source: str,
    source_id: str,
    title: str,
    reason: str,
    chapter_ref: str | None,
    metadata: dict,
    engine: Engine,
) -> str:
    """Write a dataset candidate to import_queue. Returns JSON with success flag."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(ImportQueue(
            source=source,
            source_id=source_id,
            title=title,
            reason=reason,
            chapter_ref=chapter_ref,
            status="pending",
            metadata_json=json.dumps(metadata) if metadata else None,
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "source": source, "source_id": source_id})


def run_suggest_learning_source(
    suggestion_type: str,
    reference: str,
    display_name: str,
    reason: str,
    engine: Engine,
) -> str:
    """Queue a paper, study, or dataset as a candidate learning source."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type=suggestion_type,
            reference=reference,
            display_name=display_name,
            reason=reason,
            status="pending",
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "reference": reference})


def run_suggest_new_source(
    reference: str,
    display_name: str,
    reason: str,
    engine: Engine,
) -> str:
    """Log an entirely new database or API as a candidate connector."""
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as session:
        session.add(SourceSuggestion(
            suggestion_type="new_connector",
            reference=reference,
            display_name=display_name,
            reason=reason,
            status="pending",
            suggested_at=now,
        ))
        session.commit()
    return json.dumps({"success": True, "reference": reference})


DISCOVERY_TOOLS = [
    {
        "name": "search_external",
        "description": (
            "Search external neuroscience databases by keyword. "
            "Use source='openneuro' for OpenNeuro, or source='all' to search all supported sources. "
            "Returns candidate datasets that can then be queued for import via suggest_import."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {
                    "type": "string",
                    "description": "Connector name ('openneuro') or 'all' to search all supported sources.",
                },
                "query": {
                    "type": "string",
                    "description": "Keyword or phrase to search for.",
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum results per source (default 10).",
                },
            },
            "required": ["source", "query"],
        },
    },
    {
        "name": "suggest_import",
        "description": (
            "Queue a dataset for the user to review and optionally import. "
            "Call this after search_external identifies a relevant dataset. "
            "Nothing is imported automatically — the user confirms in the Suggestions tab."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "source": {"type": "string", "description": "Connector name (e.g. 'openneuro')."},
                "source_id": {"type": "string", "description": "Dataset ID within the source."},
                "title": {"type": "string", "description": "Dataset title from the external API."},
                "reason": {"type": "string", "description": "Why this dataset is relevant to the user's question."},
                "chapter_ref": {"type": "string", "description": "Current chapter context, if set (optional)."},
            },
            "required": ["source", "source_id", "title", "reason"],
        },
    },
    {
        "name": "suggest_learning_source",
        "description": (
            "Queue a paper, study, or dataset as a candidate learning source for the registry. "
            "The user reviews and promotes it in the Suggestions tab."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "suggestion_type": {
                    "type": "string",
                    "description": "Type of learning source: 'learning_source'.",
                },
                "reference": {
                    "type": "string",
                    "description": "DOI, URL, or source_id identifying the source.",
                },
                "display_name": {"type": "string", "description": "Human-readable name."},
                "reason": {"type": "string", "description": "Why this source is relevant."},
            },
            "required": ["suggestion_type", "reference", "display_name", "reason"],
        },
    },
    {
        "name": "suggest_new_source",
        "description": (
            "Log an entirely new database or API as a candidate connector. "
            "Adding it to the system requires a separate engineering step — "
            "this only records the suggestion for the user to review."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reference": {"type": "string", "description": "URL or name of the new source."},
                "display_name": {"type": "string", "description": "Human-readable name."},
                "reason": {"type": "string", "description": "Why this source would be valuable."},
            },
            "required": ["reference", "display_name", "reason"],
        },
    },
]
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/unit/test_discovery_tools.py -v
```

Expected: 5 passed

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/discovery_tools.py tests/unit/test_discovery_tools.py
git commit -m "feat: add discovery tools module with search_external, suggest_import, suggest_learning_source, suggest_new_source"
```

---

## Task 7: Mode-Aware Agent

**Files:**
- Modify: `src/neurodb/agent.py`
- Create: `tests/integration/test_agent_modes.py`

- [ ] **Step 1: Write failing tests**

Create `tests/integration/test_agent_modes.py`:

```python
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from neurodb.db import init_db, seed_learning_sources
from neurodb.agent import NeuroAgent, TOOLS
from neurodb.discovery_tools import DISCOVERY_TOOLS


def _make_agent(mode="learning"):
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    client = MagicMock()
    agent = NeuroAgent(client, engine, mode=mode)
    return agent, client


def test_learning_mode_passes_only_local_tools():
    agent, client = _make_agent(mode="learning")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("what datasets do you have?", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {t["name"] for t in call_kwargs["tools"]}
    discovery_names = {t["name"] for t in DISCOVERY_TOOLS}
    assert tool_names.isdisjoint(discovery_names), "Discovery tools leaked into learning mode"
    assert "query_db" in tool_names


def test_discovery_mode_includes_discovery_tools():
    agent, client = _make_agent(mode="discovery")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("search for retinotopy datasets", []))

    call_kwargs = client.messages.create.call_args[1]
    tool_names = {t["name"] for t in call_kwargs["tools"]}
    assert "search_external" in tool_names
    assert "suggest_import" in tool_names
    assert "query_db" in tool_names


def test_chapter_context_injected_into_system_prompt():
    agent, client = _make_agent()
    agent.chapter_context = "Ch12 — Central Visual Pathways\nTopics: retinotopy, LGN"
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("tell me about V1", []))

    call_kwargs = client.messages.create.call_args[1]
    assert "Central Visual Pathways" in call_kwargs["system"]


def test_mode_can_be_changed_between_calls():
    agent, client = _make_agent(mode="learning")
    stop_response = MagicMock()
    stop_response.stop_reason = "end_turn"
    stop_response.content = [MagicMock(type="text", text="answer")]
    client.messages.create.return_value = stop_response

    list(agent.chat("first message", []))
    call1 = client.messages.create.call_args[1]
    assert "search_external" not in {t["name"] for t in call1["tools"]}

    agent.mode = "discovery"
    list(agent.chat("second message", []))
    call2 = client.messages.create.call_args[1]
    assert "search_external" in {t["name"] for t in call2["tools"]}
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
uv run pytest tests/integration/test_agent_modes.py -v
```

Expected: `TypeError: NeuroAgent.__init__() got an unexpected keyword argument 'mode'`

- [ ] **Step 3: Update agent.py**

In `src/neurodb/agent.py`, update the `NeuroAgent.__init__` signature:

```python
def __init__(
    self,
    client,
    engine: Engine,
    vector_store: VectorStore | None = None,
    model: str = "claude-opus-4-7",
    prior_context: str = "",
    mode: str = "learning",
    chapter_context: str = "",
) -> None:
    self._client = client
    self._engine = engine
    self._vector_store = vector_store
    self._model = model
    self.prior_context = prior_context
    self.mode = mode
    self.chapter_context = chapter_context
```

Update the `chat` method to select tools by mode and inject chapter context:

```python
def chat(self, user_message: str, history: list[dict]) -> Generator[str, None, None]:
    """Run one user turn, executing tools as needed, and yield response text."""
    from neurodb.discovery_tools import DISCOVERY_TOOLS

    active_tools = list(TOOLS)
    if self.mode == "discovery":
        active_tools = active_tools + list(DISCOVERY_TOOLS)

    system = _SYSTEM_PROMPT
    if self.chapter_context:
        system = f"{system}\n\nCurrent reading context:\n{self.chapter_context}"
    if self.prior_context:
        system = f"{system}\n\n{self.prior_context}"

    messages = list(history) + [{"role": "user", "content": user_message}]

    for _ in range(_MAX_TURNS):
        response = self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=system,
            tools=active_tools,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            for block in response.content:
                if block.type == "text":
                    yield block.text
            return

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if block.name in {"search_external", "suggest_import", "suggest_learning_source", "suggest_new_source"}:
                        result_text = _execute_discovery_tool(block.name, block.input, self._engine)
                    else:
                        result_text = execute_tool(
                            block.name, block.input, self._engine, self._vector_store
                        )
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": [{"type": "text", "text": result_text}],
                    })
            messages.append({"role": "user", "content": tool_results})
            continue

        break

    yield "[Agent reached maximum tool iterations without a final answer]"
```

Add the `_execute_discovery_tool` helper at module level (after `execute_tool`):

```python
def _execute_discovery_tool(name: str, inputs: dict, engine: Engine) -> str:
    from neurodb.discovery_tools import (
        run_search_external, run_suggest_import,
        run_suggest_learning_source, run_suggest_new_source,
    )
    if name == "search_external":
        return run_search_external(inputs["source"], inputs["query"], inputs.get("limit", 10))
    if name == "suggest_import":
        return run_suggest_import(
            inputs["source"], inputs["source_id"], inputs["title"],
            inputs["reason"], inputs.get("chapter_ref"), {}, engine,
        )
    if name == "suggest_learning_source":
        return run_suggest_learning_source(
            inputs["suggestion_type"], inputs["reference"],
            inputs["display_name"], inputs["reason"], engine,
        )
    if name == "suggest_new_source":
        return run_suggest_new_source(
            inputs["reference"], inputs["display_name"], inputs["reason"], engine,
        )
    return json.dumps({"error": f"Unknown discovery tool: {name}"})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
uv run pytest tests/integration/test_agent_modes.py -v
```

Expected: 4 passed

- [ ] **Step 5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

Expected: all pass

- [ ] **Step 6: Commit**

```bash
git add src/neurodb/agent.py tests/integration/test_agent_modes.py
git commit -m "feat: mode-aware NeuroAgent with discovery tool set and chapter context injection"
```

---

## Task 8: UI — Mode Toggle and Chapter Annotation

**Files:**
- Modify: `src/neurodb/ui/pages/chat.py`

No automated tests for Streamlit rendering — verify manually after wiring.

- [ ] **Step 1: Add _render_mode_and_chapter helper to chat.py**

Add after `_init_agent` and before `_render_start_session` in `src/neurodb/ui/pages/chat.py`:

```python
def _render_mode_and_chapter() -> None:
    """Render mode toggle and chapter annotation. Always visible regardless of session state."""
    from neurodb.chapter_registry import REGISTRY, lookup_chapter

    st.divider()

    # Mode toggle
    mode = st.radio(
        "Agent mode",
        options=["learning", "discovery"],
        index=0 if st.session_state.get("agent_mode", "learning") == "learning" else 1,
        horizontal=True,
        help="Learning: local DB only. Discovery: searches external sources and queues suggestions.",
    )
    if mode != st.session_state.get("agent_mode"):
        st.session_state["agent_mode"] = mode
        agent = st.session_state.get("neuro_agent")
        if agent:
            agent.mode = mode

    # Chapter annotation
    book_options = {k: v["display_name"] for k, v in REGISTRY.items()}
    book_key = st.selectbox(
        "Textbook",
        options=list(book_options.keys()),
        format_func=lambda k: book_options[k],
        key="selected_book_key",
    )

    chapter_input = st.text_input(
        "Current chapter (optional)",
        placeholder="e.g. Ch12",
        key="chapter_input_raw",
    )

    if chapter_input.strip():
        raw = chapter_input.strip().lstrip("Cc").lstrip("hH").strip()
        try:
            ch_num = int(raw)
        except ValueError:
            ch_num = None

        if ch_num is not None:
            info = lookup_chapter(book_key, ch_num)
            if info:
                st.success(f"**Ch{ch_num} — {info['title']}**\nTopics: {', '.join(info['topics'])}")
                context_str = f"Ch{ch_num} — {info['title']}\nTopics: {', '.join(info['topics'])}"
            else:
                st.warning(f"Ch{ch_num} not yet in registry for this book — using as plain text.")
                context_str = f"Ch{ch_num}"
        else:
            st.warning("Could not parse chapter number — using as plain text.")
            context_str = chapter_input.strip()

        if st.button("Set chapter context", key="set_chapter_btn"):
            st.session_state["chapter_context"] = context_str
            agent = st.session_state.get("neuro_agent")
            if agent:
                agent.chapter_context = context_str
            st.rerun()

    current_ctx = st.session_state.get("chapter_context", "")
    if current_ctx:
        st.caption(f"Active: {current_ctx[:60]}")
        if st.button("Clear chapter context", key="clear_chapter_btn"):
            st.session_state["chapter_context"] = ""
            agent = st.session_state.get("neuro_agent")
            if agent:
                agent.chapter_context = ""
            st.rerun()

    st.divider()
```

- [ ] **Step 2: Call _render_mode_and_chapter from render_panel**

In `render_panel`, add the call after `_init_agent(engine)` and before the session_active check:

```python
def render_panel(engine: Engine) -> None:
    if "chat_history" not in st.session_state:
        st.session_state["chat_history"] = []

    _init_agent(engine)
    _render_mode_and_chapter()   # ← add this line

    agent = st.session_state.get("neuro_agent")
    ...  # rest unchanged
```

- [ ] **Step 3: Restore agent mode and chapter context on init**

In `_init_agent`, after creating the agent, restore any persisted mode and chapter context:

```python
def _init_agent(engine: Engine) -> None:
    if "neuro_agent" in st.session_state:
        return
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        st.warning("ANTHROPIC_API_KEY not found in `.env`. Add it to enable the Research Assistant.")
        return
    import anthropic
    from neurodb.agent import NeuroAgent
    client = anthropic.Anthropic(api_key=api_key)
    vs = st.session_state.get("vector_store")
    agent = NeuroAgent(
        client, engine, vector_store=vs,
        mode=st.session_state.get("agent_mode", "learning"),
        chapter_context=st.session_state.get("chapter_context", ""),
    )
    st.session_state["neuro_agent"] = agent
```

- [ ] **Step 4: Manual verification**

Start the UI and verify:
```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```
- Mode toggle shows Learning / Discovery options
- Typing `Ch12` and selecting the book shows the confirmation block with correct title and topics
- Clicking "Set chapter context" shows the active context caption
- Switching mode updates `agent.mode` (check by asking the agent "what mode are you in?" — it won't know, but the tool list changes)

- [ ] **Step 5: Commit**

```bash
git add src/neurodb/ui/pages/chat.py
git commit -m "feat: add mode toggle and chapter annotation to chat sidebar"
```

---

## Task 9: UI — Suggestions Tab

**Files:**
- Create: `src/neurodb/ui/pages/suggestions.py`

- [ ] **Step 1: Create suggestions.py**

Create `src/neurodb/ui/pages/suggestions.py`:

```python
"""Suggestions tab: import queue and source suggestions from the discovery agent."""
import subprocess

import streamlit as st
from sqlalchemy import Engine, select, text
from sqlalchemy.orm import Session

from neurodb.schema import ImportQueue, SourceSuggestion


def render(engine: Engine) -> None:
    st.subheader("Import Queue")
    _render_import_queue(engine)

    st.divider()
    st.subheader("Source Suggestions")
    _render_source_suggestions(engine)


def _render_import_queue(engine: Engine) -> None:
    with Session(engine) as s:
        rows = s.execute(
            select(ImportQueue).where(ImportQueue.status == "pending")
            .order_by(ImportQueue.suggested_at.desc())
        ).scalars().all()

    if not rows:
        st.caption("No pending import suggestions.")
        return

    for row in rows:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                st.markdown(f"**{row.title or row.source_id}** — `{row.source}:{row.source_id}`")
                if row.chapter_ref:
                    st.caption(f"Suggested while reading: {row.chapter_ref}")
                if row.reason:
                    st.markdown(f"*{row.reason}*")
            with col_actions:
                if st.button("Import", key=f"import_{row.id}", use_container_width=True):
                    _run_import(row, engine)
                if st.button("Dismiss", key=f"dismiss_import_{row.id}", use_container_width=True):
                    _update_status(engine, ImportQueue, row.id, "dismissed")
                    st.rerun()


def _render_source_suggestions(engine: Engine) -> None:
    with Session(engine) as s:
        rows = s.execute(
            select(SourceSuggestion).where(SourceSuggestion.status == "pending")
            .order_by(SourceSuggestion.suggested_at.desc())
        ).scalars().all()

    if not rows:
        st.caption("No pending source suggestions.")
        return

    for row in rows:
        with st.container(border=True):
            col_info, col_actions = st.columns([3, 1])
            with col_info:
                label = row.display_name or row.reference or "—"
                st.markdown(f"**{label}** (`{row.suggestion_type}`)")
                if row.reference:
                    st.caption(row.reference)
                if row.reason:
                    st.markdown(f"*{row.reason}*")
            with col_actions:
                if row.suggestion_type == "learning_source":
                    if st.button("Promote", key=f"promote_{row.id}", use_container_width=True):
                        _promote_to_learning_source(row, engine)
                if st.button("Dismiss", key=f"dismiss_src_{row.id}", use_container_width=True):
                    _update_status(engine, SourceSuggestion, row.id, "dismissed")
                    st.rerun()


def _run_import(row: ImportQueue, engine: Engine) -> None:
    with st.spinner(f"Importing {row.source}:{row.source_id}…"):
        result = subprocess.run(
            ["uv", "run", "scripts/ingest.py",
             "--source", row.source,
             "--dataset-id", row.source_id],
            capture_output=True, text=True,
        )
    if result.returncode == 0:
        _update_status(engine, ImportQueue, row.id, "imported")
        st.success(f"Imported {row.source_id}")
    else:
        st.error(f"Import failed:\n{result.stderr[:400]}")
    st.rerun()


def _promote_to_learning_source(row: SourceSuggestion, engine: Engine) -> None:
    import json
    from datetime import datetime, timezone
    from neurodb.schema import LearningSource
    now = datetime.now(timezone.utc).isoformat()
    with Session(engine) as s:
        existing = s.execute(
            select(LearningSource).where(LearningSource.source_key == row.reference)
        ).scalar_one_or_none()
        if existing is None:
            s.add(LearningSource(
                source_type="paper",
                source_key=row.reference or row.display_name,
                display_name=row.display_name or row.reference,
                content_json=None,
                metadata_json=row.metadata_json,
                added_by="user",
                added_at=now,
            ))
        row_obj = s.get(SourceSuggestion, row.id)
        if row_obj:
            row_obj.status = "accepted"
        s.commit()
    st.success(f"Promoted to Learning Registry: {row.display_name}")
    st.rerun()


def _update_status(engine: Engine, model, row_id: int, status: str) -> None:
    with Session(engine) as s:
        row = s.get(model, row_id)
        if row:
            row.status = status
            s.commit()
```

- [ ] **Step 2: Manual verification (after Task 11 wires the tab)**

Defer until Task 11. Mark complete after wiring and smoke test.

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/pages/suggestions.py
git commit -m "feat: add Suggestions tab for import queue and source suggestion review"
```

---

## Task 10: UI — Learning Registry Tab

**Files:**
- Create: `src/neurodb/ui/pages/learning_registry.py`

- [ ] **Step 1: Create learning_registry.py**

Create `src/neurodb/ui/pages/learning_registry.py`:

```python
"""Learning Registry tab: view and manage learning_sources."""
import json
from datetime import datetime, timezone

import streamlit as st
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from neurodb.schema import LearningSource


def render(engine: Engine) -> None:
    st.subheader("Learning Registry")
    st.caption("All textbooks, papers, and datasets registered as learning sources.")

    with Session(engine) as s:
        rows = s.execute(select(LearningSource).order_by(LearningSource.source_type, LearningSource.display_name)).scalars().all()

    books = [r for r in rows if r.source_type == "book"]
    papers = [r for r in rows if r.source_type == "paper"]
    datasets = [r for r in rows if r.source_type == "dataset"]
    other = [r for r in rows if r.source_type not in {"book", "paper", "dataset"}]

    _render_section("Books", books, engine, show_chapters=True)
    _render_section("Papers & Studies", papers, engine)
    _render_section("Datasets", datasets, engine)
    if other:
        _render_section("Other", other, engine)

    st.divider()
    _render_add_form(engine)


def _render_section(title: str, rows: list, engine: Engine, show_chapters: bool = False) -> None:
    st.markdown(f"**{title}** ({len(rows)})")
    if not rows:
        st.caption(f"No {title.lower()} in registry yet.")
        return

    for row in rows:
        with st.expander(row.display_name, expanded=False):
            st.caption(f"Type: {row.source_type} | Key: `{row.source_key}` | Added by: {row.added_by}")

            if show_chapters and row.content_json:
                try:
                    content = json.loads(row.content_json)
                    chapters = content.get("chapters", {})
                    if chapters:
                        ch_items = sorted(chapters.items(), key=lambda x: int(x[0]))
                        for ch_num, ch_data in ch_items:
                            topics = ", ".join(ch_data.get("topics", []))
                            st.markdown(f"- **Ch{ch_num}** — {ch_data['title']}")
                            if topics:
                                st.caption(f"  Topics: {topics}")
                except (json.JSONDecodeError, KeyError):
                    st.warning("Could not parse chapter data.")
            elif row.content_json:
                try:
                    content = json.loads(row.content_json)
                    topics = content.get("topics", [])
                    if topics:
                        st.caption(f"Topics: {', '.join(topics)}")
                except json.JSONDecodeError:
                    pass

            if st.button("Remove", key=f"remove_{row.id}"):
                _remove_entry(engine, row.id)
                st.rerun()


def _remove_entry(engine: Engine, row_id: int) -> None:
    with Session(engine) as s:
        row = s.get(LearningSource, row_id)
        if row:
            s.delete(row)
            s.commit()


def _render_add_form(engine: Engine) -> None:
    st.markdown("**Add a learning source manually**")
    with st.form("add_learning_source_form", clear_on_submit=True):
        source_type = st.selectbox("Type", options=["paper", "dataset", "book"])
        source_key = st.text_input("Key (DOI, URL, or unique ID)", placeholder="10.1167/19.10.23")
        display_name = st.text_input("Display name", placeholder="Benson et al. 2018 retinotopy")
        topics_raw = st.text_input("Topics (comma-separated)", placeholder="retinotopy, V1, pRF")
        submitted = st.form_submit_button("Add")

    if submitted and source_key.strip() and display_name.strip():
        topics = [t.strip() for t in topics_raw.split(",") if t.strip()]
        content = json.dumps({"topics": topics}) if topics else None
        now = datetime.now(timezone.utc).isoformat()
        with Session(engine) as s:
            existing = s.execute(
                select(LearningSource).where(LearningSource.source_key == source_key.strip())
            ).scalar_one_or_none()
            if existing:
                st.warning(f"Key '{source_key.strip()}' already in registry.")
            else:
                s.add(LearningSource(
                    source_type=source_type,
                    source_key=source_key.strip(),
                    display_name=display_name.strip(),
                    content_json=content,
                    metadata_json=None,
                    added_by="user",
                    added_at=now,
                ))
                s.commit()
                st.success(f"Added: {display_name.strip()}")
                st.rerun()
```

- [ ] **Step 2: Manual verification (after Task 11)**

Defer until Task 11. Mark complete after wiring and smoke test.

- [ ] **Step 3: Commit**

```bash
git add src/neurodb/ui/pages/learning_registry.py
git commit -m "feat: add Learning Registry tab with chapter view, add/remove"
```

---

## Task 11: Wire New Tabs into app.py

**Files:**
- Modify: `src/neurodb/ui/app.py`

- [ ] **Step 1: Update app.py**

Replace the tabs section in `src/neurodb/ui/app.py`:

```python
# Replace this block:
tab_datasets, tab_sql, tab_study = st.tabs(["Dataset Browser", "SQL Query", "Study Log"])

with tab_datasets:
    from neurodb.ui.pages.datasets import render
    render(engine)

with tab_sql:
    from neurodb.ui.pages.query import render
    render(engine)

with tab_study:
    from neurodb.ui.pages.study_log import render
    render(engine)
```

With:

```python
tab_datasets, tab_sql, tab_study, tab_suggestions, tab_registry = st.tabs([
    "Dataset Browser", "SQL Query", "Study Log", "Suggestions", "Learning Registry",
])

with tab_datasets:
    from neurodb.ui.pages.datasets import render
    render(engine)

with tab_sql:
    from neurodb.ui.pages.query import render
    render(engine)

with tab_study:
    from neurodb.ui.pages.study_log import render
    render(engine)

with tab_suggestions:
    from neurodb.ui.pages.suggestions import render
    render(engine)

with tab_registry:
    from neurodb.ui.pages.learning_registry import render
    render(engine)
```

- [ ] **Step 2: Start the UI and manually verify all tabs**

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Verify:
- Five tabs render without error
- Suggestions tab shows "No pending import suggestions" and "No pending source suggestions"
- Learning Registry tab shows the Augustine 7th ed. book with chapters 1–15 expandable
- Mode toggle in sidebar switches between Learning and Discovery
- Typing `Ch12` in chapter field shows confirmation: "Ch12 — Central Visual Pathways / Topics: retinotopy, LGN…"
- Setting chapter context shows active caption

- [ ] **Step 3: Run full test suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

Expected: all pass

- [ ] **Step 4: Commit**

```bash
git add src/neurodb/ui/app.py
git commit -m "feat: add Suggestions and Learning Registry tabs to main UI"
```

---

## Task 12: Update projectStatus.md Test Count and Sign-off

**Files:**
- Modify: `docs/projectStatus.md`

- [ ] **Step 1: Get final test count**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q 2>&1 | tail -3
```

- [ ] **Step 2: Update P5 row in projectStatus.md**

Update the P5 row with the actual test count and today's date:

```markdown
| P5 — Learning Agent Enhancement | ✅ Signed off | <count> | 2026-05-01 |
```

Also add the new source documents to the reference table:

```markdown
| `src/neurodb/chapter_registry.py` | Augustine 7th ed. chapter → title + topics lookup |
| `src/neurodb/discovery_tools.py` | Discovery mode tool implementations and DISCOVERY_TOOLS schema |
| `docs/superpowers/specs/2026-05-01-learning-agent-enhancement-design.md` | Design spec for this phase |
| `docs/superpowers/plans/2026-05-01-learning-agent-enhancement.md` | This implementation plan |
```

- [ ] **Step 3: Commit**

```bash
git add docs/projectStatus.md
git commit -m "docs: sign off P5 learning agent enhancement"
```
