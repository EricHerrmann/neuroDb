# Tech Debt TD-2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fill unit test coverage gaps for `embedder.py`, `enrichment.py`, and `provenance.py`; add behavioral tests confirming the Clear button in the chat UI requires explicit mouse action and is not triggered by form submission.

**Architecture:** All new tests use mocks at the boundary (model loading, HTTP, file I/O) so the suite runs without live APIs, model downloads, or NWB files. Embedder and enrichment tests require moving lazy function-level imports to module level so they are patchable. Provenance tests use a real SQLite in-memory DB with a minimal FakeDataset ORM class. Clear button tests use AST analysis of chat.py to assert structural constraints — no Streamlit runtime required.

**Tech Stack:** Python, pytest, unittest.mock, SQLite in-memory, pandas, ast (stdlib)

---

## File Map

| File | Action | Purpose |
|------|--------|---------|
| `src/neurodb/embedder.py` | Modify | Move `SentenceTransformer` import to module level so it is patchable |
| `src/neurodb/enrichment.py` | Modify | Move `h5py` and `NWBHDF5IO` imports to module level so they are patchable |
| `tests/unit/test_embedder.py` | Create | Lazy-load behavior, embed() output, model caching, normalize_embeddings kwarg |
| `tests/unit/test_provenance.py` | Create | run_ingest: IngestRun creation, DatasetIndex upsert, idempotency, dataset_ids routing |
| `tests/unit/test_enrichment.py` | Create | _parse_nwb field extraction, run_enrichment success and error paths |
| `tests/unit/test_chat_clear_button.py` | Create | Clear button is outside st.form, uses st.button not form_submit_button |

---

## Task 1: Embedder unit tests

**Files:**
- Modify: `src/neurodb/embedder.py`
- Create: `tests/unit/test_embedder.py`

- [ ] **Step 1.1: Write failing tests**

```python
# tests/unit/test_embedder.py
from unittest.mock import MagicMock, patch
from neurodb.embedder import Embedder


def test_model_not_loaded_on_init():
    embedder = Embedder()
    assert embedder._model is None


def test_embed_loads_model_lazily():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2, 0.3]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        result = embedder.embed(["test text"])

    mock_cls.assert_called_once_with("allenai/specter2_base")
    assert result == [[0.1, 0.2, 0.3]]


def test_embed_does_not_reload_model_on_second_call():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        embedder.embed(["first"])
        embedder.embed(["second"])

    mock_cls.assert_called_once()  # model constructed only once


def test_embed_returns_list_of_float_lists():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1, 0.2], [0.3, 0.4]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model):
        result = embedder.embed(["text one", "text two"])

    assert isinstance(result, list)
    assert len(result) == 2
    assert all(isinstance(v, float) for v in result[0])


def test_embed_passes_normalize_embeddings_true():
    embedder = Embedder()
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.5]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model):
        embedder.embed(["text"])

    _, kwargs = mock_model.encode.call_args
    assert kwargs.get("normalize_embeddings") is True


def test_custom_model_name_passed_to_sentence_transformer():
    embedder = Embedder(model_name="custom/model")
    mock_model = MagicMock()
    mock_result = MagicMock()
    mock_result.tolist.return_value = [[0.1]]
    mock_model.encode.return_value = mock_result

    with patch("neurodb.embedder.SentenceTransformer", return_value=mock_model) as mock_cls:
        embedder.embed(["text"])

    mock_cls.assert_called_once_with("custom/model")
```

- [ ] **Step 1.2: Run test — confirm it fails**

```bash
cd /home/oldha/projects/neuroDb
uv run pytest tests/unit/test_embedder.py -v
```
Expected: FAIL — `AttributeError: module 'neurodb.embedder' has no attribute 'SentenceTransformer'` (import is inside the function, not patchable at module level)

- [ ] **Step 1.3: Move `SentenceTransformer` import to module level in `embedder.py`**

Replace the contents of `src/neurodb/embedder.py`:

```python
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None  # type: ignore[assignment,misc]

MODEL_NAME = "allenai/specter2_base"


class Embedder:
    """Lazy-loading SPECTER2 wrapper. Model is downloaded on first embed() call."""

    def __init__(self, model_name: str = MODEL_NAME):
        self._model_name = model_name
        self._model = None

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self._model is None:
            self._model = SentenceTransformer(self._model_name)
        return self._model.encode(texts, normalize_embeddings=True).tolist()
```

- [ ] **Step 1.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_embedder.py -v
```
Expected: all 6 tests PASS

- [ ] **Step 1.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 1.6: Commit**

```bash
git add src/neurodb/embedder.py tests/unit/test_embedder.py
git commit -m "test: add unit tests for Embedder lazy-load and embed behavior"
```

---

## Task 2: Provenance unit tests

**Files:**
- Create: `tests/unit/test_provenance.py`

Uses SQLite in-memory with a real `FakeDataset` ORM class registered with `Base`. This lets `run_ingest`'s `select(SourceModel)` queries work against a real table without hitting any network.

- [ ] **Step 2.1: Write failing tests**

```python
# tests/unit/test_provenance.py
from typing import Iterator
from sqlalchemy import Integer, String, ForeignKey, Sequence, create_engine, select
from sqlalchemy.orm import Mapped, mapped_column, Session

from neurodb.schema import Base, DatasetIndex, IngestRun
from neurodb.connectors.base import BaseConnector
from neurodb.db import init_db
from neurodb.provenance import run_ingest


class FakeDataset(Base):
    """Minimal source-specific table for provenance test isolation."""
    __tablename__ = "fake_datasets"

    id: Mapped[int] = mapped_column(Integer, Sequence("fake_datasets_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, unique=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class FakeConnector(BaseConnector):
    SOURCE_NAME = "fake"
    VERSION = "0.0.1"

    def __init__(self, datasets: list[dict]):
        self._datasets = datasets

    def fetch_datasets(self, limit: int = 100) -> Iterator[dict]:
        return iter(self._datasets[:limit])

    def get_source_id(self, raw: dict) -> str:
        return raw["id"]

    def normalize_dataset(self, raw: dict, index_id: int, run_id: int) -> FakeDataset:
        return FakeDataset(index_id=index_id, source_id=raw["id"], run_id=run_id)

    def fetch_subjects(self, dataset_source_id: str) -> Iterator[dict]:
        return iter([])

    def normalize_subject(self, raw: dict, index_id: int):
        pass

    def fetch_by_id(self, dataset_id: str) -> dict:
        for d in self._datasets:
            if d["id"] == dataset_id:
                return d
        raise RuntimeError(f"fake: {dataset_id} not found")


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


def test_run_ingest_returns_ingest_run_with_correct_metadata():
    engine = _engine()
    connector = FakeConnector([])  # no datasets — just verify IngestRun creation
    run = run_ingest(engine, connector)
    assert isinstance(run, IngestRun)
    assert run.source == "fake"
    assert run.version == "0.0.1"
    assert run.id is not None


def test_run_ingest_creates_dataset_index_row():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}])
    run_ingest(engine, connector)

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].source_id == "ds001"


def test_run_ingest_is_idempotent():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}])

    run_ingest(engine, connector)
    run_ingest(engine, connector)

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()

    assert len(rows) == 1  # no duplicate DatasetIndex row on second run


def test_run_ingest_dataset_ids_uses_fetch_by_id_not_fetch_datasets():
    engine = _engine()
    connector = FakeConnector([{"id": "ds001"}, {"id": "ds002"}])

    fetch_datasets_calls = []
    fetch_by_id_calls = []
    original_fetch_datasets = connector.fetch_datasets
    original_fetch_by_id = connector.fetch_by_id

    def tracking_fetch_datasets(limit=100):
        fetch_datasets_calls.append(True)
        return original_fetch_datasets(limit)

    def tracking_fetch_by_id(dataset_id):
        fetch_by_id_calls.append(dataset_id)
        return original_fetch_by_id(dataset_id)

    connector.fetch_datasets = tracking_fetch_datasets
    connector.fetch_by_id = tracking_fetch_by_id

    run_ingest(engine, connector, dataset_ids=["ds002"])

    assert fetch_by_id_calls == ["ds002"]
    assert fetch_datasets_calls == []

    with Session(engine) as s:
        rows = s.execute(
            select(DatasetIndex).where(DatasetIndex.source == "fake")
        ).scalars().all()

    assert len(rows) == 1
    assert rows[0].source_id == "ds002"
```

- [ ] **Step 2.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_provenance.py -v
```
Expected: FAIL — `ImportError` or `ModuleNotFoundError: No module named 'neurodb.provenance'`

- [ ] **Step 2.3: Run test — confirm it passes**

No code change needed for provenance.py — the tests work against the existing implementation. If the tests still fail after confirming the import path is correct, read the failure message and diagnose before changing anything.

```bash
uv run pytest tests/unit/test_provenance.py -v
```
Expected: all 4 tests PASS

- [ ] **Step 2.4: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 2.5: Commit**

```bash
git add tests/unit/test_provenance.py
git commit -m "test: add unit tests for run_ingest upsert, idempotency, and dataset_ids routing"
```

---

## Task 3: Enrichment unit tests

**Files:**
- Modify: `src/neurodb/enrichment.py`
- Create: `tests/unit/test_enrichment.py`

- [ ] **Step 3.1: Write failing tests**

```python
# tests/unit/test_enrichment.py
import pandas as pd
from unittest.mock import MagicMock, patch
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.db import init_db
from neurodb.enrichment import _parse_nwb, run_enrichment


def test_parse_nwb_extracts_electrode_count_sampling_rate_and_version():
    mock_hf = MagicMock()
    mock_hf.__enter__.return_value = mock_hf
    mock_hf.attrs.get.return_value = b"2.3.0"

    mock_nwb = MagicMock()
    mock_nwb.electrodes.__len__.return_value = 64
    mock_nwb.electrodes.to_dataframe.return_value = pd.DataFrame(
        {"sampling_rate": [30000.0] * 64}
    )
    mock_nwb.electrode_groups = {}
    mock_nwb.session_description = "Visual cortex recording"

    mock_io = MagicMock()
    mock_io.__enter__.return_value = mock_io
    mock_io.read.return_value = mock_nwb

    with patch("neurodb.enrichment.h5py.File", return_value=mock_hf), \
         patch("neurodb.enrichment.NWBHDF5IO", return_value=mock_io):
        result = _parse_nwb("/fake/path.nwb")

    assert result["electrode_count"] == 64
    assert result["sampling_rate"] == 30000.0
    assert result["nwb_version"] == "2.3.0"
    assert result["cognitive_paradigm"] == "Visual cortex recording"
    assert result["brain_regions"] is None


def test_parse_nwb_handles_no_electrodes():
    mock_hf = MagicMock()
    mock_hf.__enter__.return_value = mock_hf
    mock_hf.attrs.get.return_value = None

    mock_nwb = MagicMock()
    mock_nwb.electrodes = None
    mock_nwb.electrode_groups = {}
    mock_nwb.session_description = None

    mock_io = MagicMock()
    mock_io.__enter__.return_value = mock_io
    mock_io.read.return_value = mock_nwb

    with patch("neurodb.enrichment.h5py.File", return_value=mock_hf), \
         patch("neurodb.enrichment.NWBHDF5IO", return_value=mock_io):
        result = _parse_nwb("/fake/path.nwb")

    assert result["electrode_count"] is None
    assert result["sampling_rate"] is None
    assert result["nwb_version"] is None
    assert result["cognitive_paradigm"] is None


def test_run_enrichment_returns_zero_when_no_unenriched_records():
    from neurodb.connectors.dandi import DandiDataset  # triggers table registration
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    count = run_enrichment(engine, limit=10)
    assert count == 0


def test_run_enrichment_marks_error_on_download_failure():
    from neurodb.connectors.dandi import DandiDataset
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as s:
        ds = DandiDataset(
            index_id=1, source_id="000001", title="Test",
            run_id=1, enriched_at=None,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    with patch("neurodb.enrichment._download_first_nwb", side_effect=RuntimeError("timeout")):
        count = run_enrichment(engine, limit=1)

    assert count == 0
    with Session(engine) as s:
        rec = s.get(DandiDataset, ds_id)
        assert rec.enriched_at is not None
        assert rec.enriched_at.startswith("ERROR:")


def test_run_enrichment_enriches_record_and_returns_count():
    from neurodb.connectors.dandi import DandiDataset
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)

    with Session(engine) as s:
        ds = DandiDataset(
            index_id=1, source_id="000001", title="Test",
            run_id=1, enriched_at=None,
        )
        s.add(ds)
        s.commit()
        ds_id = ds.id

    fake_fields = {
        "electrode_count": 64,
        "sampling_rate": 30000.0,
        "brain_regions": '["V1"]',
        "cognitive_paradigm": "Visual cortex",
        "nwb_version": "2.3.0",
    }

    with patch("neurodb.enrichment._download_first_nwb", return_value="/tmp/fake.nwb"), \
         patch("neurodb.enrichment._parse_nwb", return_value=fake_fields):
        count = run_enrichment(engine, limit=1)

    assert count == 1
    with Session(engine) as s:
        rec = s.get(DandiDataset, ds_id)
        assert rec.electrode_count == 64
        assert rec.sampling_rate == 30000.0
        assert rec.enriched_at is not None
        assert not rec.enriched_at.startswith("ERROR:")
```

- [ ] **Step 3.2: Run test — confirm it fails**

```bash
uv run pytest tests/unit/test_enrichment.py -v
```
Expected: FAIL on `test_parse_nwb_*` — `AttributeError: module 'neurodb.enrichment' has no attribute 'h5py'` (h5py and NWBHDF5IO are imported inside `_parse_nwb`, not at module level)

- [ ] **Step 3.3: Move `h5py` and `NWBHDF5IO` to module level in `enrichment.py`**

Replace `src/neurodb/enrichment.py` with:

```python
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import h5py
from pynwb import NWBHDF5IO

from sqlalchemy import Engine

from neurodb.db import get_session


def _download_first_nwb(source_id: str) -> str | None:
    """Download the first NWB asset for a dandiset to a temp file. Returns path or None."""
    from dandi.dandiapi import DandiAPIClient
    with DandiAPIClient() as client:
        dandiset = client.get_dandiset(source_id)
        for asset in dandiset.get_assets():
            if asset.path.endswith(".nwb"):
                tmp = tempfile.NamedTemporaryFile(suffix=".nwb", delete=False)
                tmp.close()
                asset.download(tmp.name)
                return tmp.name
    return None


def _parse_nwb(path: str) -> dict:
    """Extract enrichment fields from an NWB file. Raises on parse failure."""
    nwb_version = None
    with h5py.File(path, "r") as hf:
        raw_ver = hf.attrs.get("nwb_version")
        if raw_ver is not None:
            nwb_version = raw_ver.decode() if isinstance(raw_ver, bytes) else str(raw_ver)

    electrode_count = None
    sampling_rate = None
    brain_regions = None
    cognitive_paradigm = None

    with NWBHDF5IO(path, "r", load_namespaces=True) as io:
        nwb = io.read()

        if nwb.electrodes is not None:
            electrode_count = len(nwb.electrodes)
            df = nwb.electrodes.to_dataframe()
            if "sampling_rate" in df.columns:
                rates = df["sampling_rate"].dropna()
                if not rates.empty:
                    sampling_rate = float(rates.iloc[0])

        if nwb.electrode_groups:
            locations = [eg.location for eg in nwb.electrode_groups.values() if eg.location]
            if locations:
                brain_regions = json.dumps(list(dict.fromkeys(locations)))

        if nwb.session_description:
            cognitive_paradigm = nwb.session_description[:256]

    return {
        "electrode_count": electrode_count,
        "sampling_rate": sampling_rate,
        "brain_regions": brain_regions,
        "cognitive_paradigm": cognitive_paradigm,
        "nwb_version": nwb_version,
    }


def run_enrichment(engine: Engine, limit: int | None = None) -> int:
    """Enrich unenriched DANDI records with NWB metadata. Returns count enriched."""
    from neurodb.connectors.dandi import DandiDataset

    with get_session(engine) as session:
        query = session.query(DandiDataset).filter(DandiDataset.enriched_at.is_(None))
        if limit is not None:
            query = query.limit(limit)
        records = list(query)

    enriched_count = 0
    for record in records:
        tmp_path = None
        try:
            tmp_path = _download_first_nwb(record.source_id)
            if tmp_path is None:
                print(f"  {record.source_id}: no NWB asset found, skipping")
                continue
            fields = _parse_nwb(tmp_path)
            with get_session(engine) as session:
                rec = session.get(DandiDataset, record.id)
                for k, v in fields.items():
                    setattr(rec, k, v)
                rec.enriched_at = datetime.now(timezone.utc).isoformat()
            enriched_count += 1
            print(f"  {record.source_id}: enriched ({fields['electrode_count']} electrodes)")
        except Exception as e:
            print(f"  WARNING: {record.source_id}: enrichment failed: {e}")
            try:
                with get_session(engine) as session:
                    rec = session.get(DandiDataset, record.id)
                    if rec is not None:
                        rec.enriched_at = f"ERROR:{str(e)[:200]}"
            except Exception:
                pass
        finally:
            if tmp_path is not None:
                p = Path(tmp_path)
                if p.exists() and str(p).startswith(tempfile.gettempdir()):
                    p.unlink()

    return enriched_count
```

- [ ] **Step 3.4: Run test — confirm it passes**

```bash
uv run pytest tests/unit/test_enrichment.py -v
```
Expected: all 5 tests PASS

- [ ] **Step 3.5: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 3.6: Commit**

```bash
git add src/neurodb/enrichment.py tests/unit/test_enrichment.py
git commit -m "test: add unit tests for _parse_nwb and run_enrichment; move h5py/pynwb imports to module level"
```

---

## Task 4: Clear button behavioral tests

**Files:**
- Create: `tests/unit/test_chat_clear_button.py`

The Clear button fix (H1-clear): the button was moved outside `st.form("agent_form")` so Enter/form-submit no longer triggers it. These AST-based tests verify the structural constraint is preserved without needing the Streamlit runtime.

The Clear button in `chat.py` is found by label text (`"Clear"`) not by key (no key is set). The form block is `with st.form("agent_form", ...)` inside `with composer_col:`.

- [ ] **Step 4.1: Write tests**

```python
# tests/unit/test_chat_clear_button.py
"""
Structural tests confirming the Clear button in chat.py:
- Is NOT nested inside the st.form("agent_form") block
- Uses st.button(), not st.form_submit_button()
- Is checked independently from the form's submitted variable
"""
import ast
import pathlib


def _get_chat_source() -> str:
    return (pathlib.Path("src/neurodb/ui/pages/chat.py")).read_text()


def _find_form_blocks(tree: ast.AST) -> list[tuple[int, int]]:
    """Return (start_line, end_line) for every `with st.form(...)` block."""
    blocks = []
    for node in ast.walk(tree):
        if isinstance(node, ast.With):
            for item in node.items:
                expr = item.context_expr
                if (
                    isinstance(expr, ast.Call)
                    and isinstance(expr.func, ast.Attribute)
                    and expr.func.attr == "form"
                ):
                    blocks.append((node.lineno, node.end_lineno))
    return blocks


def _find_clear_button_line(tree: ast.AST) -> int | None:
    """Return the line number of st.button("Clear", ...) — matched by exact label."""
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "button"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and str(node.args[0].value).lower() == "clear"
        ):
            return node.lineno
    return None


def test_clear_button_is_outside_agent_form():
    """Clear button must not be nested inside any st.form(...) block."""
    source = _get_chat_source()
    tree = ast.parse(source)

    form_blocks = _find_form_blocks(tree)
    assert form_blocks, "No st.form(...) block found in chat.py — test assumptions broken"

    clear_btn_line = _find_clear_button_line(tree)
    assert clear_btn_line is not None, (
        'No st.button("Clear", ...) found in chat.py'
    )

    for form_start, form_end in form_blocks:
        assert not (form_start <= clear_btn_line <= form_end), (
            f'Clear button (line {clear_btn_line}) is inside a st.form block '
            f"(lines {form_start}–{form_end}). It must be outside the form."
        )


def test_clear_button_uses_st_button_not_form_submit():
    """Clear action must use st.button(), not st.form_submit_button()."""
    source = _get_chat_source()
    tree = ast.parse(source)

    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "form_submit_button"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and "clear" in str(node.args[0].value).lower()
        ):
            raise AssertionError(
                f"Line {node.lineno}: Clear is implemented as st.form_submit_button — "
                "it will fire on Enter. Use st.button() outside the form instead."
            )

    clear_btn_line = _find_clear_button_line(tree)
    assert clear_btn_line is not None, (
        'No st.button("Clear", ...) found — Clear button may be missing or mislabeled.'
    )


def test_submit_and_clear_are_separate_variables():
    """submitted (form) and clear_clicked (button) must be separate, not OR-combined."""
    source = _get_chat_source()

    assert "clear_clicked" in source, "Expected variable 'clear_clicked' in chat.py"
    assert "submitted" in source, "Expected variable 'submitted' in chat.py"

    for line in source.splitlines():
        if "submitted" in line and "clear_clicked" in line and " or " in line:
            raise AssertionError(
                f"submitted and clear_clicked are combined with 'or': {line!r}. "
                "They must be checked independently."
            )
```

- [ ] **Step 4.2: Run test — confirm it passes (fix is already in place)**

```bash
uv run pytest tests/unit/test_chat_clear_button.py -v
```
Expected: all 3 tests PASS — the H1-clear fix moved the button outside the form in a prior sprint.

If any test fails, inspect `src/neurodb/ui/pages/chat.py` around the form and Clear button before touching code.

- [ ] **Step 4.3: Run full suite**

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```
Expected: all PASS

- [ ] **Step 4.4: Commit**

```bash
git add tests/unit/test_chat_clear_button.py
git commit -m "test: add behavioral tests confirming Clear button is outside form and not triggered by Enter"
```

---

## TD-2 Complete

```bash
uv run pytest --ignore=tests/integration/test_dandi_ingest.py -q
```

All tests must pass. Update `docs/projectStatus.md` test count.
