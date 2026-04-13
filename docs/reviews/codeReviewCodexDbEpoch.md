# Code Review — NeuroDb DB Epoch

**Reviewer:** Codex  
**Date:** 2026-04-12  
**Scope:** Current NeuroDb implementation in `src/`, `scripts/`, `tests/`, and epoch docs aligned to `NeuroDbGoals.md`

---

## Summary

The DB Epoch implementation is close to the intended MVP architecture: local DB, connector-driven ingest, provenance runs, query API, CLI tools, and a Streamlit UI for browse/query are all present. The project already has useful manual testing docs and clear direction.

The current blocking issue is **test/fixture drift** in the OpenNeuro connector contract: one unit test fails and integration fixtures do not represent the connector's current API field mapping. This creates false confidence for mapping correctness. Beyond that, there are medium-priority architectural gaps for multi-source readiness and operational hardening.

---

## Verification Snapshot

Commands run during review:

- `uv run pytest tests/ -v` -> **1 failed, 12 passed**
  - failing: `tests/unit/test_openneuro_connector.py::test_normalize_dataset_maps_fields`
- `uv run ruff check .` -> **fails** (import/order and line-length issues)
- `uv run mypy src` -> **passes**

---

## Findings (Ordered by Severity)

### High

1. **OpenNeuro mapping contract drift (blocking test failure)**
   - **Evidence:** `test_normalize_dataset_maps_fields` expects `numberOfParticipants`-based mapping, but `normalize_dataset` now derives `n_subjects` from `metadata.ages`.
   - **Impact:** Test suite red; integration fixture no longer validates current mapping contract.
   - **Files:** `src/neurodb/connectors/openneuro.py`, `tests/unit/test_openneuro_connector.py`, `tests/fixtures/openneuro_sample.json`
   - **Fix:** Update unit test + fixture to match current API mapping (`metadata.associatedPaperDOI`, `metadata.ages`, `draft.readme`, `draft.description.BIDSVersion`) and assert mapped fields explicitly.

2. **Integration tests currently under-assert critical mapped fields**
   - **Evidence:** integration tests primarily assert counts/title, not `doi`, `n_subjects`, `bids_version`, `description`.
   - **Impact:** Mapping regressions can slip through while tests stay green.
   - **Files:** `tests/integration/test_openneuro_ingest.py`, `tests/fixtures/openneuro_sample.json`
   - **Fix:** Expand assertions to validate all key mapped fields and null-handling behavior.

### Medium

3. **Query layer and UI are single-source-coupled (OpenNeuro only)**
   - **Evidence:** `query.py` directly queries `OpenNeuroDataset`; UI pages assume `openneuro_datasets`.
   - **Impact:** Multi-source add/merge work will require refactor before DB Epoch goals are fully met.
   - **Files:** `src/neurodb/query.py`, `src/neurodb/ui/pages/datasets.py`, `src/neurodb/ui/pages/query.py`
   - **Fix:** Introduce source-agnostic query service over `datasets_index` + adapters for source-specific fields.

4. **Model registration depends on side-effect import order**
   - **Evidence:** `ui/app.py` imports `neurodb.connectors.openneuro` only to register ORM model before `init_db`.
   - **Impact:** Easy to miss when adding new connectors or alternate startup paths.
   - **Files:** `src/neurodb/ui/app.py`, `src/neurodb/connectors/openneuro.py`
   - **Fix:** Add centralized model registry import module (e.g., `neurodb/models.py`) and always import it before `create_all`.

5. **Raw SQL UI allows destructive statements**
   - **Evidence:** SQL page executes `text(sql)` directly without read-only guard.
   - **Impact:** Accidental local data loss (`DROP/DELETE/UPDATE`) is possible via UI.
   - **Files:** `src/neurodb/ui/pages/query.py`
   - **Fix:** Restrict UI to `SELECT` for MVP or run queries through read-only DB connection guard.

6. **Ingest provenance version is hardcoded**
   - **Evidence:** `run_ingest` writes `version="0.1.0"` for every run.
   - **Impact:** Weak auditability across connector/schema changes.
   - **Files:** `src/neurodb/provenance.py`
   - **Fix:** Source version from connector attribute and/or package metadata.

### Low

7. **Lint baseline is not clean**
   - **Evidence:** Ruff reports import sorting and line-length issues in source, scripts, and tests.
   - **Impact:** Noise and inconsistent style; lower signal for new issues.
   - **Files:** multiple (`src/`, `scripts/`, `tests/`)
   - **Fix:** Run `ruff check --fix` + manual cleanup; enforce in CI gate.

8. **README is empty**
   - **Evidence:** `README.md` has no content.
   - **Impact:** Onboarding and reproducibility are harder for new contributors.
   - **Fix:** Add quickstart, ingest/query commands, architecture summary, and known limitations.

9. **No migration path yet (expected but now becoming relevant)**
   - **Evidence:** schema creation is `create_all` only.
   - **Impact:** Schema evolution risk as multi-source work expands.
   - **Fix:** Add lightweight schema version checks now; plan Alembic before Phase 3 expansion.

---

## Strengths Observed

- Clean separation between connector contract, provenance orchestration, storage, and UI.
- Idempotent ingest behavior is implemented and tested.
- Manual test documentation is unusually strong for this stage (`manualTestPlan_phase2.md`, `manualTestIssues.md`).
- Core typing check currently passes (`mypy src`).

---

## Recommended Fix Plan (Current Epoch)

### Phase 1 — Stabilize Contract + Tests (Immediate)

**Goals**
- Restore green test baseline and align fixtures with current connector behavior.

**Actions**
- Update OpenNeuro fixture shape to current fields.
- Update `test_normalize_dataset_maps_fields` expectations.
- Add integration assertions for mapped fields (`doi`, `n_subjects`, `bids_version`, `description`).

**Validation**
- `uv run pytest tests/ -v` must be all green.

### Phase 2 — Hardening and Safety

**Goals**
- Improve operational safety and auditability without major architecture changes.

**Actions**
- Restrict SQL UI to read-only/select-only in MVP mode.
- Replace hardcoded ingest version with connector/package-derived version.
- Add better ingest failure context wrapping for connector/network exceptions.

**Validation**
- New tests for query-page SQL guard and provenance version recording.

### Phase 3 — Multi-Source Readiness Refactor

**Goals**
- Remove OpenNeuro hard-coupling from query/UI pathways.

**Actions**
- Introduce source-agnostic query layer over `datasets_index`.
- Add connector model registry import pattern.
- Define minimal source adapter interface for UI display fields.

**Validation**
- Add a second mock connector fixture path and cross-source query tests.

### Phase 4 — Developer Experience and Governance

**Goals**
- Improve maintainability and onboarding.

**Actions**
- Clean Ruff issues and enforce lint in CI.
- Populate `README.md` with reproducible quickstart.
- Add schema version check and migration roadmap note.

**Validation**
- `uv run ruff check .` green
- `uv run mypy src` green
- `uv run pytest tests/ -v` green

---

## Suggested Next PR Slice

Smallest high-value PR:
1. Fix failing unit test + fixture alignment.
2. Add integration assertions for mapped fields.
3. Add README quickstart section.

This delivers immediate confidence restoration with minimal architecture risk.

