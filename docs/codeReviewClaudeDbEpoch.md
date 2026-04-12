# Code Review — NeuroDb DB Epoch (Phases 0–2)

**Reviewer:** Claude (claude-sonnet-4-6)
**Date:** 2026-04-12
**Commit range:** `841b0a2` (base, pre-Phase-2 fixes) → `4cdcfb7` (HEAD)
**Test run result:** 12 passed, 1 failed (`test_normalize_dataset_maps_fields`)

---

## Summary

The DB Epoch MVP is substantially complete and correctly implements the architecture
described in `docs/ClaudeDbEpochPlan.md`. The schema, provenance model, connector
pattern, upsert logic, query helpers, CLI tools, and Streamlit UI are all present and
aligned with the plan. The manual-testing cycle caught and fixed three real bugs (see
`docs/manualTestIssues.md`). The remaining work is confined to one failing test, the
stale fixture that caused it, and a handful of lower-priority design concerns. Nothing
in this review represents a safety or data-integrity regression from the plan; all
issues are actionable and bounded.

---

## 1. Bugs

### 1.1 (Critical) — `test_normalize_dataset_maps_fields` fails; fixture is stale

**File:** `tests/unit/test_openneuro_connector.py`, `tests/fixtures/openneuro_sample.json`

The connector was correctly updated to match OpenNeuro API v4.47.7. The test and
fixture were not updated to match. The specific mismatch is:

- Test passes `"numberOfParticipants": 16` under `metadata` and expects `ds.n_subjects == 16`.
- The updated `normalize_dataset` now derives `n_subjects` from `len(metadata.ages)`, not
  `metadata.numberOfParticipants`. Since the test fixture omits `ages`, `n_subjects` resolves
  to `None` and the assertion fails.
- Test also passes a top-level `"doi"` field and expects `ds.doi` to equal it. The connector
  now reads `metadata.associatedPaperDOI`; the top-level `"doi"` key is silently ignored,
  so `ds.doi` is `None`.

The fixture `tests/fixtures/openneuro_sample.json` has the same problem for the
integration tests: it uses `"numberOfParticipants"`, top-level `"doi"`, and top-level
`"description"` — none of which the updated connector reads. The integration tests
happen to pass because they do not assert on `n_subjects`, `doi`, or `description`
values. This creates false confidence: the integration fixture no longer represents
what the live API returns.

**Consequence:** One test fails on every run. The fixture divergence means integration
tests pass but do not validate actual API field mapping.

---

### 1.2 (Important) — `neurodb.db` committed to the repository

**File:** `neurodb.db` (binary blob, 110,592 bytes, added in commit `4cdcfb7`)

A live database file was committed to the repo. This is problematic for three reasons:

1. It contains real data from the OpenNeuro API, making the repo non-reproducible
   (the "clean clone + run ingest" baseline is obscured by a pre-populated file).
2. SQLite binary diffs are not readable, making git history harder to audit.
3. Any future schema change will silently conflict with the on-disk file for developers
   who pull without deleting it, triggering the silent `create_all` no-op described
   in section 2.1 below.

`neurodb.db` should be added to `.gitignore` and the committed file removed.

---

### 1.3 (Important) — `run_ingest` propagates network exceptions without context

**File:** `src/neurodb/provenance.py`

`httpx.post` inside `fetch_datasets` can raise `httpx.HTTPStatusError`,
`httpx.TimeoutException`, or `httpx.NetworkError`. These propagate uncaught through
`run_ingest`. When they do, the `IngestRun` row has already been flushed to the
session, and the session's `except` block rolls back the transaction — so the
`IngestRun` row is not committed. However, the caller (e.g. `scripts/ingest.py`)
receives a raw httpx exception with no context about which source failed or what
partial state was attempted. For a CLI tool meant to be run by a human, an
unhandled httpx traceback is poor UX and makes diagnosing rate-limit or auth failures
harder.

---

### 1.4 (Minor) — `get_dataset_by_id` returns by ORM PK, not `source_id`

**File:** `src/neurodb/query.py`, `tests/unit/test_query.py`

`get_dataset_by_id` accepts an integer and calls `session.get(OpenNeuroDataset, dataset_id)`,
which is the internal autoincrement PK. The CLI and Streamlit UI expose `source_id`
(e.g. `ds000001`) to users, not the internal integer. A user who copies `ds000001`
from the browser and calls `get_dataset_by_id` will get nothing. The function name
implies a dataset identifier lookup but delivers an ORM row lookup. The intent is
probably `source_id` lookup; at minimum the docstring and parameter name should be
clarified, or a second function added.

The test `test_get_by_id` passes `1` as the argument and asserts `source_id == "ds001"`,
which only works because the seed inserts rows with predictable auto-PK values. This
test would break if row insertion order changed or if rows were deleted.

---

## 2. Design Issues

### 2.1 (Important) — No schema migration mechanism

**File:** `src/neurodb/db.py`

`init_db` calls `Base.metadata.create_all(engine)`, which is idempotent for the
initial creation but does nothing if tables already exist with different columns.
If a developer runs `scripts/ingest.py` after pulling a schema update, the existing
`neurodb.db` silently retains the old structure. Queries against new columns will
return `None` or raise `OperationalError` with no warning.

This is acknowledged in the known-issues brief. For MVP scope, an acceptable mitigation
is a startup check that detects schema version mismatch and either errors with a clear
message or drops-and-recreates in development mode. Alembic is the correct Phase 3
solution but adds setup overhead; even a simple `PRAGMA user_version` check in
`init_db` would be a substantial improvement for this epoch.

---

### 2.2 (Important) — `query.py` is hard-coded to `OpenNeuroDataset`

**File:** `src/neurodb/query.py`

Both `search_datasets` and `get_dataset_by_id` import and query `OpenNeuroDataset`
directly. The `DatasetIndex` + source-specific table design was explicitly chosen to
allow sources to be added without touching cross-cutting code. As soon as a second
connector (Allen Brain Atlas) is added, these helpers will need to be duplicated or
refactored. The type annotations also return `OpenNeuroDataset`, not a protocol or
union type, which will cause mypy failures when a second model is added.

For the current single-source MVP this is acceptable, but the coupling should be
noted as a pre-requisite fix before Phase 3 work begins.

---

### 2.3 (Minor) — Source-specific model defined in connector module

**File:** `src/neurodb/connectors/openneuro.py`

`OpenNeuroDataset` is defined in the connector module. `src/neurodb/ui/app.py` imports
the connector module solely to register the ORM class with `Base.metadata` before
`init_db` is called (documented with a `# noqa: F401` comment following the manual
testing fix). This side-effect coupling is fragile: any code path that calls `init_db`
without having imported the connector first will silently omit `openneuro_datasets`
from the schema.

The plan (section "Project Structure" in `ClaudeDbEpochPlan.md`) shows source-specific
models as part of the connector module, so this is not a plan deviation — but the
import-order dependency it creates is a known fragility. Adding a central `models.py`
registry or using SQLAlchemy's `configure_mappers` pattern would eliminate it.

---

### 2.4 (Minor) — `run_ingest` version is hardcoded

**File:** `src/neurodb/provenance.py`, line 18

```python
version="0.1.0",
```

The `IngestRun.version` field is intended to record the connector/pipeline version for
auditability. Hardcoding `"0.1.0"` means every run records the same version regardless
of code changes. `IngestRun.version` should derive from the connector's `VERSION`
attribute or the package version (`importlib.metadata.version("neurodb")`).

---

### 2.5 (Minor) — SQL query page accepts arbitrary DDL/DML

**File:** `src/neurodb/ui/pages/query.py`

The SQL query page executes `text(sql)` directly against the engine without any
filtering. A user could run `DROP TABLE openneuro_datasets` or `DELETE FROM datasets_index`
and destroy the local database. For a single-user local MVP the risk is low, but
the UI caption says "Run raw SQL" with no caveat about destructive queries. A read-only
connection or a simple check for `DROP`/`DELETE`/`UPDATE`/`INSERT` would be prudent.

---

### 2.6 (Minor) — `datasets.py` uses `width="stretch"` which is also deprecated

**File:** `src/neurodb/ui/pages/datasets.py`, `src/neurodb/ui/pages/query.py`

The manual test fix replaced `use_container_width=True` with `width="stretch"`.
However, `width` accepts an integer (pixels) or `None` in Streamlit's current API;
`"stretch"` is not a documented valid value. Streamlit may silently ignore it or
warn in future versions. The correct replacement for `use_container_width=True` is
`use_container_width=True` with Streamlit >= 1.25 (where it remains valid) or
simply omitting the parameter to accept the default. The fix is not incorrect enough
to break rendering, but it should be verified against the installed Streamlit version.

---

## 3. Test Gaps

### 3.1 (Critical) — Fixture does not match current API shape

**File:** `tests/fixtures/openneuro_sample.json`

The fixture uses fields that no longer exist in the API: top-level `"description"`,
top-level `"doi"`, `"numFiles"`, and `metadata.numberOfParticipants`. It is missing
fields the connector now reads: `metadata.associatedPaperDOI`, `metadata.ages`,
`draft.readme`, and `draft.description.BIDSVersion`.

Because `normalize_dataset` uses `raw.get(...)` with fallback defaults, the integration
tests that use this fixture pass — but they validate the fallback-path behavior, not
the actual API field mapping. If the connector's `normalize_dataset` had a bug in
reading `metadata.ages`, no existing test would catch it.

---

### 3.2 (Important) — No test for `normalize_dataset` with new API fields

**File:** `tests/unit/test_openneuro_connector.py`

After the API shape was updated, `test_normalize_dataset_maps_fields` was not updated
to cover the new paths. There is no test that:

- Passes `metadata.associatedPaperDOI` and asserts `ds.doi` is set.
- Passes `metadata.ages` as a list and asserts `ds.n_subjects == len(ages)`.
- Passes `draft.readme` and asserts `ds.description` is set.
- Passes `draft.description.BIDSVersion` and asserts `ds.bids_version` is set.
- Passes a `raw` with all fields absent and asserts graceful nulls (no KeyError).

---

### 3.3 (Important) — No test for `fetch_datasets` error paths

**File:** `tests/unit/test_openneuro_connector.py`

There is one test for the happy-path fetch. No test covers:

- `httpx.HTTPStatusError` (e.g. 400 or 429 from the API) — the `raise_for_status()`
  call in the connector should propagate, but this is untested.
- `response.json()["data"]` key missing or malformed — would raise a `KeyError`
  with no user-facing message.
- Empty `edges` list — should yield nothing; untested.

---

### 3.4 (Minor) — Integration tests assert only record counts, not field values for new API shape

**Files:** `tests/integration/test_openneuro_ingest.py`, `tests/integration/test_idempotent.py`

`test_full_ingest_stores_datasets` asserts `ds.title == "Balloon Analog Risk Task"` and
`idx.source == "openneuro"`, which are correct. It does not assert `ds.doi`, `ds.n_subjects`,
`ds.bids_version`, or `ds.description`. Since the fixture does not supply the new API
fields, these would all be `None` — but the test does not verify whether `None` is
correct or a sign of a broken mapping.

Once the fixture is updated to the new API shape, the integration test assertions
should be expanded to cover the mapped fields.

---

### 3.5 (Minor) — No test for `run_ingest` version field propagation

**File:** `tests/integration/test_openneuro_ingest.py`

`IngestRun.version` is hardcoded to `"0.1.0"` in `provenance.py`. No test asserts that
the `IngestRun` row records the expected version. This means if `run_ingest` were
changed to omit the version field, no test would catch the regression.

---

### 3.6 (Minor) — `test_get_by_id` relies on implicit PK ordering

**File:** `tests/unit/test_query.py`

The test seeds two rows and then calls `get_dataset_by_id(session, 1)`, assuming the
first inserted row gets PK 1. This assumption is valid for SQLite in-memory but is
not guaranteed across databases. The test should capture the seeded row's `id` from
the session and use that value, or look up by `source_id`.

---

### 3.7 (Minor) — `test_base_connector.py` covers only abstract instantiation

**File:** `tests/unit/test_base_connector.py`

The single test confirms `BaseConnector()` raises `TypeError`. There are no tests that
instantiate a concrete stub connector and exercise the contract methods to verify the
abstract interface is enforced correctly. A minimal stub connector test would document
the expected method signatures and catch future regressions if the abstract base
changes.

---

## 4. Enhancements (This Epoch)

### 4.1 — Add `ages` list to fixture and update integration assertions

This is the direct fix for issues 1.1 and 3.1–3.4. The fixture should be updated to
the v4.47.7 API shape, the failing unit test updated with the corrected inline `raw`
dict, and the integration test assertions expanded.

### 4.2 — Add `.gitignore` entry for `neurodb.db`

Remove the committed `neurodb.db` and add `neurodb.db` to `.gitignore`. Include a
`neurodb.db.example` comment in the runbook explaining that the database is created
on first ingest.

### 4.3 — Add `VERSION` attribute to `OpenNeuroConnector`

Add `VERSION = "0.1.0"` to the connector class and pass it to `IngestRun.version` via
`connector.VERSION`. This makes version tracking per-connector and verifiable in tests.

### 4.4 — Add error wrapping in `run_ingest` for network failures

Wrap the `connector.fetch_datasets` loop in a `try/except` that catches
`httpx.HTTPStatusError` and re-raises as a `RuntimeError` with a message of the form
`"Ingest failed for source={source}: {status_code} {url}"`. This gives the CLI a
readable error instead of a raw httpx traceback.

### 4.5 — Clarify or rename `get_dataset_by_id`

Either rename to `get_dataset_by_pk` and document that it accepts the internal integer
PK, or change the implementation to accept `source_id: str` and filter on
`OpenNeuroDataset.source_id`. The latter is more useful for callers who have
a dataset identifier from the UI or CLI output.

---

## 5. Out of Scope (Defer to Later Phases)

The following items were noted during review but are intentionally deferred per the
phased plan in `docs/ClaudeDbEpochPlan.md`:

- **Schema migrations (Alembic):** Appropriate at Phase 3 when multiple developers and
  multiple schema versions are likely. For a single-developer MVP, the `create_all`
  no-op is an acceptable known limitation.
- **Modality normalization / controlled vocabulary:** The plan defers this to Phase 3
  field-coverage review. The `modality` column stores raw API strings; normalizing
  `"mri"` vs `"MRI"` vs `"T1w"` requires a vocabulary decision that belongs at Phase 3.
- **Allen Brain Atlas connector:** Phase 3 scope. `allen_brain.py` does not exist and
  is not expected in the current phase.
- **`transforms/` package (`normalize.py`, `merge.py`):** The plan included these
  modules in the project structure but they were not created. For a single-source MVP,
  normalization lives in `OpenNeuroConnector.normalize_dataset` and the omission is
  reasonable. They become necessary when a second source is added.
- **`v_all_datasets` SQL view:** Phase 3 scope per the merge strategy plan.
- **Subject ingest via BIDS sidecar:** Stubbed correctly in `fetch_subjects`; deferral
  is documented in the source comment.
- **Read-only SQL query page:** Low priority for single-user local use; appropriate
  to harden before any shared deployment.
- **DuckDB migration:** Phase 3 decision gate as designed.

---

## 6. What Was Done Well

- **Plan alignment:** The implementation follows the Approach A architecture
  (`datasets_index` + source-specific tables) exactly as specified. No premature
  abstractions were introduced.
- **Provenance from day one:** Every `OpenNeuroDataset` row carries `run_id` linking
  back to the `IngestRun` record. The `IngestRun` table records source, timestamp, and
  version.
- **Upsert idempotency:** `run_ingest` correctly implements a SELECT-then-insert-or-update
  pattern for both `DatasetIndex` and source-specific records. The idempotency integration
  test passes and covers the double-ingest case.
- **Defensive field access:** `normalize_dataset` uses `raw.get("field") or {}` at every
  level, so a missing `metadata` or `draft` block does not raise a `KeyError`.
- **Manual testing was done and issues were recorded:** The `docs/manualTestIssues.md`
  log is thorough and accurately traces the root cause and fix for each issue found.
  The import-order fix for `OpenNeuroDataset` registration is particularly well explained.
- **Schema design quality:** The `UniqueConstraint` on `DatasetIndex(source, source_id)`
  provides a database-level guard against duplicates independent of the application-level
  upsert logic. The `Subject` table's unique constraint on `(index_id, source_subject_id)`
  follows the same pattern.
- **`get_session` context manager:** The session factory correctly commits on success
  and rolls back on exception, with `expire_on_commit=False` preventing detached-instance
  errors when ORM objects are used after the session closes.
- **CLI usability:** Both CLI scripts accept `--db` to override the default path and
  print clean output. The ingest script prints `run_id`, source, and timestamp on
  completion, which is the minimum needed for a reproducible audit trail.

---

## 7. Prioritised Action List

### Critical (block the test suite; must fix before merging further work)

| # | Issue | File | Action |
|---|-------|------|--------|
| C1 | `test_normalize_dataset_maps_fields` fails — fixture and test use old API shape | `tests/fixtures/openneuro_sample.json`, `tests/unit/test_openneuro_connector.py` | Update fixture to v4.47.7 shape (`ages`, `associatedPaperDOI`, `draft.readme`, `draft.description.BIDSVersion`). Update inline `raw` dict in the unit test. Add assertions for all new mapped fields. |

### Important (addressable in this epoch; each is isolated)

| # | Issue | File | Action |
|---|-------|------|--------|
| I1 | `neurodb.db` committed to repo | `neurodb.db`, `.gitignore` | Add `neurodb.db` to `.gitignore`. Remove the file from git history or at minimum from the index. |
| I2 | Integration fixture diverges from real API shape — integration tests give false confidence | `tests/fixtures/openneuro_sample.json`, `tests/integration/test_openneuro_ingest.py` | Update fixture (same change as C1). Expand integration assertions to cover `doi`, `n_subjects`, `bids_version`, `description`. |
| I3 | `query.py` hard-coupled to `OpenNeuroDataset` — will break at Phase 3 | `src/neurodb/query.py` | Document coupling explicitly; add a TODO noting this must be refactored before a second source is added. No structural change required this epoch. |
| I4 | Network errors in `run_ingest` surface as raw httpx tracebacks | `src/neurodb/provenance.py` | Wrap `fetch_datasets` iteration in a `try/except` and re-raise with a human-readable message. |

### Minor (low risk; clean up when convenient)

| # | Issue | File | Action |
|---|-------|------|--------|
| M1 | `get_dataset_by_id` accepts internal PK, not `source_id` | `src/neurodb/query.py` | Rename to `get_dataset_by_pk` or change to accept `source_id: str`. |
| M2 | `run_ingest` hardcodes version `"0.1.0"` | `src/neurodb/provenance.py` | Add `VERSION` class attribute to connectors; pass `connector.VERSION` to `IngestRun`. |
| M3 | `test_get_by_id` depends on implicit PK value | `tests/unit/test_query.py` | Capture seeded row's `id` from the session; use that in the assertion. |
| M4 | `width="stretch"` is not a valid Streamlit `width` value | `src/neurodb/ui/pages/datasets.py`, `src/neurodb/ui/pages/query.py` | Verify against installed Streamlit version; use `use_container_width=True` if still supported, or remove the parameter. |
| M5 | No tests for `fetch_datasets` error paths | `tests/unit/test_openneuro_connector.py` | Add tests for `HTTPStatusError`, empty `edges`, and malformed response. |
| M6 | `test_base_connector.py` covers only abstract instantiation | `tests/unit/test_base_connector.py` | Add a stub concrete connector test to exercise the interface contract. |
