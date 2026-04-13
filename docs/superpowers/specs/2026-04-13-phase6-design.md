# Phase 6 Design — Additional Sources (NeuroVault + DANDI)

**Date:** 2026-04-13
**Author:** Eric Herrmann
**Status:** Approved

---

## Overview

Phase 6 adds two new data source connectors — NeuroVault and DANDI — to the existing NeuroDb pipeline. Both use the established connector pattern (source-specific table + `datasets_index` FK + `run_id` provenance). DANDI adds a second-stage NWB enrichment step that downloads and parses one NWB file per dandiset to extract richer electrophysiology metadata.

**Goal alignment:** Both sources advance the brain plasticity research goal. NeuroVault contributes fMRI statistical maps with cognitive paradigm metadata. DANDI contributes electrophysiology and calcium imaging datasets with electrode and brain region detail.

---

## Architecture

```
scripts/
  ingest.py          ← extended: --source neurovault, --source dandi
  enrich.py          ← NEW: DANDI NWB enrichment pass (stage 2)

src/neurodb/connectors/
  neurovault.py      ← NEW: NeuroVault REST connector + NeuroVaultDataset model
  dandi.py           ← NEW: DANDI REST connector + DandiDataset model

tests/fixtures/
  neurovault_sample.json   ← NEW
  dandi_api_sample.json    ← NEW
  dandi_sample.nwb         ← NEW (minimal real NWB file for enrichment tests)

tests/unit/
  test_neurovault_normalize.py   ← NEW
  test_dandi_normalize.py        ← NEW

tests/integration/
  test_neurovault_ingest.py      ← NEW
  test_dandi_ingest.py           ← NEW
  test_dandi_enrich.py           ← NEW
```

**New dependencies:** `dandi` (DANDI Python client), `pynwb`, `h5py`.

---

## Schema

### `neurovault_datasets`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | Integer PK (sequence) | No | |
| `index_id` | FK → `datasets_index.id` | No | unique |
| `source_id` | String(128) | No | NeuroVault collection ID |
| `title` | Text | No | collection name |
| `doi` | String(256) | Yes | |
| `n_images` | Integer | Yes | number of statistical maps |
| `n_subjects` | Integer | Yes | |
| `cognitive_paradigm` | String(256) | Yes | CogAtlas term from API |
| `tr` | Float | Yes | repetition time in seconds |
| `resolution` | String(32) | Yes | e.g. `"2mm"` |
| `description` | Text | Yes | |
| `metadata_json` | Text | Yes | full API response overflow |
| `run_id` | FK → `ingest_runs.id` | No | |

### `dandi_datasets`

| Column | Type | Nullable | Notes |
|--------|------|----------|-------|
| `id` | Integer PK (sequence) | No | |
| `index_id` | FK → `datasets_index.id` | No | unique |
| `source_id` | String(128) | No | dandiset ID e.g. `"000003"` |
| `title` | Text | No | |
| `doi` | String(256) | Yes | |
| `species` | String(128) | Yes | |
| `modality` | String(64) | Yes | |
| `n_subjects` | Integer | Yes | |
| `cognitive_paradigm` | String(256) | Yes | from NWB session_description (first 256 chars) |
| `brain_regions` | Text | Yes | JSON array e.g. `["CA1","CA3"]` |
| `sampling_rate` | Float | Yes | Hz, from NWB electrode table |
| `electrode_count` | Integer | Yes | row count of NWB electrode table |
| `nwb_version` | String(32) | Yes | |
| `enriched_at` | String(32) | Yes | ISO timestamp of NWB parse; NULL = unenriched; `"ERROR:<msg>"` = parse failed |
| `metadata_json` | Text | Yes | full API response overflow |
| `run_id` | FK → `ingest_runs.id` | No | |

Both tables register with `Base.metadata` in their connector files. The `v_all_datasets` view is extended to UNION in both new sources.

---

## NeuroVault Connector

**API:** `https://neurovault.org/api/collections/` — paginated REST, no auth. Returns `results` array + `next` cursor URL.

**`SOURCE_NAME`:** `"neurovault"` | **`VERSION`:** `"0.1.0"`

**`fetch_datasets(limit)`:** Pages through collections using the `next` cursor until `limit` records are collected or the API is exhausted. Uses `httpx`.

**Field mapping:**

| API field | Model column |
|-----------|--------------|
| `id` | `source_id` |
| `name` | `title` |
| `doi` | `doi` |
| `number_of_images` | `n_images` |
| `number_of_subjects` | `n_subjects` |
| `cognitive_paradigm_cog_atlas` | `cognitive_paradigm` |
| `repetition_time` | `tr` |
| `resolution` | `resolution` |
| `description` | `description` |
| full raw dict as JSON | `metadata_json` |

Empty collections (`n_images=0`) are ingested without special handling — they appear in the DB and can be filtered at query time.

---

## DANDI Connector

**API:** `https://api.dandiarchive.org/api/dandisets/` — paginated REST, no auth.

**`SOURCE_NAME`:** `"dandi"` | **`VERSION`:** `"0.1.0"`

**`fetch_datasets(limit)`:** Pages through `/api/dandisets/?page_size=50` collecting up to `limit` records. Uses `httpx`.

**Field mapping (stage 1 — API only):**

| API field | Model column |
|-----------|--------------|
| `identifier` | `source_id` |
| `metadata.name` | `title` |
| `metadata.doi` | `doi` |
| `metadata.species[0].name` | `species` |
| `assetsSummary.dataStandard[0].name` | `modality` |
| `assetsSummary.numberOfSubjects` | `n_subjects` |
| full raw dict as JSON | `metadata_json` |
| `None` | `brain_regions`, `sampling_rate`, `electrode_count`, `nwb_version`, `cognitive_paradigm`, `enriched_at` |

---

## DANDI Enrichment (`enrich.py`)

```
uv run scripts/enrich.py --source dandi [--limit N] [--db neurodb.duckdb]
```

**Flow per dandiset:**
1. Query DB for `DandiDataset` records where `enriched_at IS NULL`, up to `--limit` (default: all).
2. Use `dandi` Python client to locate the first NWB asset in the dandiset.
3. Download to `tempfile.NamedTemporaryFile`, parse with `pynwb.NWBHDF5IO`.
4. Extract:
   - `nwb_file.electrodes` → `electrode_count` (row count), `sampling_rate` (first electrode rate if present)
   - `nwb_file.electrode_groups` keys → `brain_regions` (JSON array)
   - `nwb_file.session_description` → `cognitive_paradigm` (first 256 chars)
   - `nwb_file.nwb_version` → `nwb_version`
5. Update DB record; set `enriched_at` to current UTC ISO timestamp.
6. Delete temp file immediately after parse.
7. On parse error: log warning, set `enriched_at = "ERROR:<message>"`, continue.

**Idempotency:** Records with non-null `enriched_at` are skipped. Re-running is safe.

---

## Testing

**Unit tests (fixture-based, no network):**
- `test_neurovault_normalize.py` — fixture `neurovault_sample.json`, asserts all mapped fields, checks `metadata_json` is valid JSON, checks `None` for missing optional fields.
- `test_dandi_normalize.py` — fixture `dandi_api_sample.json`, same; confirms all NWB fields are `None` after API-only normalize.

**Integration tests (in-memory DuckDB, mocked HTTP):**
- `test_neurovault_ingest.py` — patches `httpx` with fixture data, full ingest → store, asserts row count and field values, re-run confirms idempotency.
- `test_dandi_ingest.py` — same for DANDI stage 1; confirms `enriched_at IS NULL` post-ingest.
- `test_dandi_enrich.py` — uses `tests/fixtures/dandi_sample.nwb` (minimal: 1 electrode, 1 electrode group, generated once). Patches `dandi` client asset download to return fixture path. Asserts `enriched_at` is set, `brain_regions` is valid JSON, `electrode_count == 1`. Re-run confirms idempotency.

**Regression:** All existing 35 tests must continue to pass. `v_all_datasets` view tests updated to expect 4 sources.

**Expected new test count:** ~12 (4 unit + 8 integration).

---

## Dependencies

Add to `pyproject.toml`:
- `dandi` — DANDI Python client (REST + asset download)
- `pynwb` — NWB file parsing
- `h5py` — HDF5 backend required by pynwb

---

## Success Criteria

- `uv run scripts/ingest.py --source neurovault --limit 50` completes without error
- `uv run scripts/ingest.py --source dandi --limit 50` completes without error; all records have `enriched_at IS NULL`
- `uv run scripts/enrich.py --source dandi --limit 10` populates NWB fields on 10 records
- `uv run scripts/query_cli.py --sql "SELECT source, COUNT(*) FROM v_all_datasets GROUP BY source"` returns 4 rows
- All new and existing tests pass (`uv run pytest tests/ -v`)
- Re-running ingest and enrich produces no duplicate rows
