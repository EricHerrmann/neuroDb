# Manual Test Plan - Config Control Phase 6: Fallback and Telemetry

**Status:** Complete - T1-T5 passed and signed off 2026-05-23
**Date created:** 2026-05-23
**Design spec:** `docs/superpowers/specs/2026-05-23-phase6-fallback-telemetry-design.md`
**Implementation plan:** `docs/superpowers/plans/2026-05-23-phase6-fallback-telemetry.md`

---

## Prerequisites

1. Run automated tests:

```bash
uv run pytest tests/ -q
```

Pass criterion: no new failures beyond those already tracked in `docs/testLog.md`.

2. Run frontend tests:

```bash
cd frontend
npm test
```

Pass criterion: all Vitest tests pass.

3. Stop any running API, Streamlit app, or manual SQL process that is using
`neurodb.duckdb`, then prepare a loaded disposable copy of the primary DB:

```bash
uv run python tests/manual/phase6_prepare_manual_db.py --force
```

Pass criterion: the helper prints `PASS: Phase 6 disposable manual DB is ready.`
The helper copies `neurodb.duckdb` to `/tmp/neurodb_phase6_manual.duckdb` and,
when present, copies `neurodb_chroma` to `/tmp/neurodb_phase6_manual_chroma`.
This gives the manual run real project data while keeping Phase 6 test artifacts
out of the primary DB.

4. Start the API against the loaded disposable manual DB:

```bash
NEURODB_DB_PATH=/tmp/neurodb_phase6_manual.duckdb uv run uvicorn neurodb.api.app:app_factory --factory --port 8001
```

Pass criterion: API starts and initializes schema migration 013 without error.

5. Start React:

```bash
cd frontend
npm run dev
```

Open `http://localhost:5173`.

---

## T1 - Fallback warning rows are persisted

**Setup:**
Temporarily route the standard tier to a configured provider whose API key is
not present in `.env`, while leaving at least one fallback provider key
configured. Example: set `standard = "openai"` in `neurodb_models.toml`, ensure
`OPENAI_API_KEY` is absent or renamed in `.env`, and keep `ANTHROPIC_API_KEY`
configured. Restart the API after editing TOML or `.env`. Do not recreate the
manual DB copy unless you intentionally want to discard prior Phase 6 test
artifacts.

**Steps:**
1. Open Chat.
2. Select Neuro Tutor.
3. Send: `What is long-term potentiation?`
4. Stop the API before CLI/DB inspection if DuckDB is locked.
5. Run:

```bash
uv run neurodb-telemetry --db /tmp/neurodb_phase6_manual.duckdb --tail 20 --warnings-only
```

**Pass criteria:**
- Chat still receives a response from a fallback provider.
- Telemetry output includes a `provider_missing` warning for the skipped primary provider.
- Telemetry output includes a `routing_fallback` row naming the selected fallback provider.

---

## T2 - Capability mismatch is visible

**Setup:**
Temporarily route `premium = "groq"` in `neurodb_models.toml` and ensure Groq is configured. Restart the API.
Use the loaded disposable DB prepared in Prerequisite 3 so Research panel data
from the primary DB is available without writing test artifacts back to the
primary DB.

**Steps:**
1. Trigger a premium task, such as a hypothesis review from the Research panel if data is available.
2. Stop the API before CLI/DB inspection if DuckDB is locked.
3. Run:

```bash
uv run neurodb-telemetry --db /tmp/neurodb_phase6_manual.duckdb --tail 20 --warnings-only --task-type research
```

**Pass criteria:**
- The router skips Groq premium because it is degraded or capability-incompatible.
- `system_warnings` includes the skip reason and, if another provider is available, a `routing_fallback` row.

---

## T3 - Telemetry timestamp format is readable

**Steps:**
1. Generate at least one chat turn or session-summary call.
2. Stop the API before CLI/DB inspection if DuckDB is locked.
3. Run:

```bash
uv run neurodb-telemetry --db /tmp/neurodb_phase6_manual.duckdb --tail 5
```

**Pass criteria:**
- Model-call timestamps render as `HH:MM:SS DD/MM/YY`.
- Warning timestamps render in the same format.
- Raw ISO 8601 timestamps are not shown in CLI output.

---

## T4 - Active provider chip is visible

**Steps:**
1. Open the React app.
2. Inspect the Chat header.

**Pass criteria:**
- A read-only provider chip is visible in the header.
- The chip shows the standard-tier provider and model from `/api/model-info`.
- The chip does not expose an editable control.

---

## T5 - Session summary preview is expandable

**Setup:**
Complete at least one chat turn and click Clear so the session is ended and summarized.

**Steps:**
1. Open Study Log.
2. Switch to Chat History.
3. Locate a session with a summary.
4. Expand the session summary.

**Pass criteria:**
- Sessions with `summary_preview` show an expand affordance.
- The summary is collapsed by default.
- Expanding shows text labeled `Session summary`.
- Sessions without summaries do not show the expand affordance.

---

## Results

| Test | Result | Date | Notes |
|---|---|---|---|
| T1 - Fallback warning rows are persisted | Passed | 2026-05-23 | User-reported manual pass |
| T2 - Capability mismatch is visible | Passed | 2026-05-23 | User-reported manual pass |
| T3 - Telemetry timestamp format is readable | Passed | 2026-05-23 | User-reported manual pass |
| T4 - Active provider chip is visible | Passed | 2026-05-23 | User-reported manual pass |
| T5 - Session summary preview is expandable | Passed | 2026-05-23 | User-reported manual pass |

## Sign-Off

| Tester | Date | Result | Notes |
|---|---|---|---|
| oldha | 2026-05-23 | Passed | Phase 6 manual test T1-T5 passed |
