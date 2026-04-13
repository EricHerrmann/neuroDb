# Manual Test Issues

Tracks bugs and regressions found during manual testing. Reference test steps from `manualTestPlan_phase2.md`.

---

## Issue 1 — `no such table: openneuro_datasets` on UI startup

**Test:** Phase 2 / Test 1 (Empty DB behaviour)
**Date found:** 2026-04-12
**Severity:** Blocker — UI crashes immediately, no page renders

**Steps to reproduce:**
```bash
rm -f neurodb.db
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.db
```
Open `http://localhost:8501`. App crashes before any page is visible.

**Error:**
```
sqlalchemy.exc.OperationalError: (sqlite3.OperationalError) no such table: openneuro_datasets
```

**Root cause:**
`OpenNeuroDataset` (which owns `__tablename__ = "openneuro_datasets"`) is defined in
`src/neurodb/connectors/openneuro.py`. SQLAlchemy only registers a model with
`Base.metadata` when its module is imported. `app.py` called `init_db(engine)` —
which runs `Base.metadata.create_all()` — before any code path that imports the
connector, so the table was never created.

**Fix applied:** `src/neurodb/ui/app.py`
Added an explicit import of the connector module before `init_db` is called:
```python
import neurodb.connectors.openneuro  # noqa: F401 — registers OpenNeuroDataset with Base.metadata
```

**Status:** Fixed

---

## Issue 2 — `use_container_width` deprecation warning on Dataset Browser and SQL Query render

**Test:** Phase 2 / Test 1 step 1.2; Test 4 step 4.1
**Date found:** 2026-04-12
**Severity:** Minor — warning only, no crash

**Symptom:** Streamlit logs the following on every dataframe render:
```
Please replace `use_container_width` with `width`.
`use_container_width` will be removed after 2025-12-31.
```

**Root cause:** Both `src/neurodb/ui/pages/datasets.py` and `src/neurodb/ui/pages/query.py`
used the deprecated `use_container_width=True` parameter on `st.dataframe()`.
Initial fix only caught `datasets.py`; `query.py` was missed on first pass.

**Fix applied:**
- `src/neurodb/ui/pages/datasets.py` — first fix attempt (incomplete)
- `src/neurodb/ui/pages/query.py` — second fix, resolved the warning

```python
# Before (both files)
st.dataframe(df, use_container_width=True)
# After (both files)
st.dataframe(df, width="stretch")
```

**Note:** Both fixes required a full Streamlit server restart to take effect.
Streamlit hot-reload only covers `app.py`; changes to imported modules are not
picked up until the server restarts.

**Status:** Fixed

---

## Issue 4 — Modality filter returns no results due to case mismatch

**Test:** Phase 2 / Test 3, step 3.4
**Date found:** 2026-04-12
**Severity:** Medium — modality filter silently returns no results

**Symptom:** Selecting e.g. `MRI` from the dropdown returns "No datasets found" even though the table shows rows with modality `mri`.

**Root cause:** The dropdown options are uppercase (`MRI`, `fMRI`, `EEG`, `MEG`) but the OpenNeuro API returns modality strings in lowercase. The filter used `==` (exact match), so `MRI != mri`.

**Fix applied:** `src/neurodb/query.py`
```python
# Before
stmt = stmt.where(OpenNeuroDataset.modality == modality)
# After
stmt = stmt.where(OpenNeuroDataset.modality.ilike(modality))
```

**Status:** Fixed

---

## Issue 5 — `no such table: v_all_datasets` on manual test 3

**Test:** Phase 3 / Test 3
**Date found:** 2026-04-13
**Severity:** Blocker — view query fails entirely

**Steps to reproduce:**
```bash
sqlite3 neurodb.db "SELECT source, count(*) from v_all_datasets group by source;"
```

**Error:**
```
Error: in prepare, no such table: v_all_datasets
```

**Root cause:** `scripts/ingest.py` called `init_db(engine)` (creates tables) but never
called `create_views(engine)`. Views (`v_all_datasets`, `v_dataset_summary`,
`v_canonical_subjects`) were only created in tests (in-memory) and in
`scripts/field_coverage_audit.py`. After any normal ingest run the views did not
exist in `neurodb.db`.

**Fix applied:** `scripts/ingest.py`
Added `create_views(engine)` immediately after `init_db(engine)`:
```python
init_db(engine)
create_views(engine)   # added — ensures views exist after every ingest run
```
Also applied `create_views` one-time to the existing `neurodb.db` to unblock the
current test session without requiring a full re-ingest.

**Commit:** `de36451`

**Status:** Fixed

---

## Issue 3 — OpenNeuro GraphQL query uses stale field names (400 Bad Request on ingest)

**Test:** Phase 2 / Test 2 (Ingest from OpenNeuro)
**Date found:** 2026-04-12
**Severity:** Blocker — ingest fails entirely, no data written

**Steps to reproduce:**
```bash
uv run scripts/ingest.py --source openneuro --limit 5 --db neurodb.db
```

**Error:**
```
httpx.HTTPStatusError: Client error '400 Bad Request' for url 'https://openneuro.org/crn/graphql'
```

**Root cause:** The OpenNeuro API (now at v4.47.7) removed or moved several fields since the query was written:

| Field queried | Status |
|---|---|
| `Dataset.description` | Moved to `Dataset.draft.readme` |
| `Dataset.doi` | Moved to `Dataset.metadata.associatedPaperDOI` |
| `Dataset.numFiles` | Removed |
| `Metadata.numberOfParticipants` | Removed — `Metadata.ages` (list of subject ages) is the replacement |
| `Metadata.bidsVersion` | Moved to `Dataset.draft.description.BIDSVersion` |

**Fix applied:** `src/neurodb/connectors/openneuro.py`
- Updated `_DATASETS_QUERY` to use current field paths
- Updated `normalize_dataset` accordingly
- `n_subjects` now derived as `len(ages)` — age distribution also captured in `metadata_json`
- `bids_version` pulled from `draft.description.BIDSVersion`
- `description` mapped to `draft.readme`
- `doi` mapped to `metadata.associatedPaperDOI`

**Status:** Fixed
