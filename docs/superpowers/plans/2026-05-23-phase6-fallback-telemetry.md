# Phase 6 Implementation Plan - Provider Fallback and Telemetry Surface

**Date:** 2026-05-23
**Epoch:** Config Control
**Design spec:** `docs/superpowers/specs/2026-05-23-phase6-fallback-telemetry-design.md`
**Manual test plan:** `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md`
**Status:** Complete - manual T1-T5 passed and signed off 2026-05-23

## Scope

Implement Config Control Phase 6:

- provider fallback lists and capability flags in `neurodb_models.toml`
- `TaskRouter` fallback chain with persisted routing warnings
- `system_warnings` schema and migration 013
- telemetry formatting and `neurodb-telemetry` CLI
- React active-provider chip
- expandable session summaries in chat history

## Out of Scope

- Provider Responses API adapter work
- UI telemetry dashboard
- Automatic model quality promotion
- Full provider-by-provider live validation matrix

## Implementation Tasks

| Task | Status | Files |
|---|---|---|
| T1 - Manual plan and project status sync | Complete | `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md`, `docs/projectStatus.md`, `docs/ConfigControl_EpochPlan.md` |
| T2 - Config parsing and TOML fallback metadata | Complete | `neurodb_models.toml`, `src/neurodb/config/model_config.py`, tests |
| T3 - `SystemWarning` schema, migration, write helper | Complete | `src/neurodb/schema.py`, `src/neurodb/db.py`, `src/neurodb/model_telemetry.py`, tests |
| T4 - `TaskRouter` fallback chain | Complete | `src/neurodb/config/task_router.py`, tests |
| T5 - Route call-site persistence | Complete | API and Streamlit route construction call sites |
| T6 - Telemetry formatter and CLI | Complete | `src/neurodb/config/telemetry_format.py`, `src/neurodb/cli/telemetry.py`, `pyproject.toml`, tests |
| T7 - React active-provider chip and session-summary expanders | Complete | `frontend/src/components/`, `frontend/src/pages/`, frontend tests |
| T8 - Verification and status closeout | Complete | focused tests, status docs |

## Task Details

### T1 - Manual plan and project status sync

- Create the manual test plan before implementation.
- Mark Config Control Phase 6 active in `docs/projectStatus.md` and `docs/ConfigControl_EpochPlan.md`.
- Add the new plan/spec references to `docs/projectStatus.md`.

### T2 - Config parsing and TOML fallback metadata

- Add `economy_fallback`, `standard_fallback`, and `premium_fallback` lists.
- Add capability flags for degraded Gemini economy and Groq premium.
- Add typed helper functions that return task config, tier provider config, and fallback order without breaking existing `get_model_for_task()` call sites.
- Keep existing direct helpers stable for `/api/model-info`.

### T3 - `SystemWarning` schema, migration, write helper

- Add `SystemWarning` ORM class with indexes.
- Add migration 013 that creates `system_warnings` idempotently.
- Add `record_system_warning()` helper that swallows DB-write failures like model-call telemetry.
- Cover the migration and helper with unit tests.

### T4 - `TaskRouter` fallback chain

- Add `RoutingError`.
- Infer task capabilities from task-type prefixes.
- Walk provider candidates in primary-plus-fallback order with deduplication.
- Persist skip rows and fallback/failed outcome rows when `engine` is supplied.
- Preserve no-DB behavior when `engine` is omitted.

### T5 - Route call-site persistence

- Pass `engine` to router calls in API and Streamlit paths where an engine is already available.
- Keep tests and mocked router compatibility by using keyword-only `engine`.

### T6 - Telemetry formatter and CLI

- Add `format_recorded_at()` with `HH:MM:SS DD/MM/YY` output.
- Add `neurodb-telemetry` console script.
- Print model-call rows and system-warning rows with filters for tail, provider, task prefix, and warnings-only mode.

### T7 - React active-provider chip and session-summary expanders

- Add a read-only provider chip using existing `/api/model-info` data.
- Move session summaries behind an expander in chat history and hide the affordance when no summary exists.
- Add focused frontend tests.

### T8 - Verification and status closeout

- Run focused Python and frontend tests for changed surfaces.
- Update task statuses in this plan as tasks complete.
- Update status docs with final test counts and remaining manual verification state.

## Verification

Focused automated checks:

```bash
uv run pytest tests/unit/test_model_config.py tests/unit/test_task_router.py tests/unit/test_system_warnings.py tests/unit/test_telemetry_format.py tests/unit/test_telemetry_cli.py tests/unit/test_migrations.py -q
cd frontend && npm test -- ChatPanel.test.tsx StudyLogPanel.test.tsx
```

Manual verification is complete in `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md`.

## Implementation Results

Implementation completed 2026-05-23.

Automated checks run:

```bash
env NEURODB_DB_PATH=/tmp/neurodb_phase6_pytest.duckdb uv run pytest tests/unit/test_model_config.py tests/unit/test_task_router.py tests/unit/test_system_warnings.py tests/unit/test_telemetry_format.py tests/unit/test_telemetry_cli.py tests/unit/test_migrations.py -q
```

Result: 43 passed.

```bash
env NEURODB_DB_PATH=/tmp/neurodb_phase6_pytest.duckdb uv run pytest tests/unit/test_api_chat.py tests/unit/test_api_knowledge_library.py tests/unit/test_api_research.py tests/unit/test_knowledge_library_page.py tests/unit/test_research_ui.py tests/unit/test_telemetry.py tests/unit/test_session_manager.py -q
```

Result: 95 passed.

```bash
cd frontend && npm test -- ChatPanel.test.tsx StudyLogPanel.test.tsx --run
```

Result: 21 passed.

```bash
cd frontend && npm test
```

Result: 91 passed.

```bash
uv run ruff check src/neurodb/config/model_config.py src/neurodb/config/task_router.py src/neurodb/config/telemetry_format.py src/neurodb/model_telemetry.py src/neurodb/cli/telemetry.py tests/unit/test_model_config.py tests/unit/test_task_router.py tests/unit/test_system_warnings.py tests/unit/test_telemetry_format.py tests/unit/test_telemetry_cli.py tests/unit/test_migrations.py
```

Result: all checks passed.

```bash
uv run python -m py_compile src/neurodb/config/model_config.py src/neurodb/config/task_router.py src/neurodb/config/telemetry_format.py src/neurodb/model_telemetry.py src/neurodb/cli/telemetry.py
```

Result: passed.

```bash
uv run neurodb-telemetry --db sqlite:///:memory: --warnings-only --tail 1
```

Result: passed; printed the empty warnings state.

Manual verification:

- Phase 6 T1-T5 passed and signed off 2026-05-23.
