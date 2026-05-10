# Config Control Phase 2 — Manual Test Plan

**Epoch scope:** Config Control — validates local model-call telemetry for model-routing cost analysis.

**Feature:** `model_call_log` telemetry for agent loops and summary calls
**Status:** Passed — signed off 2026-05-08
**Plan:** `docs/superpowers/plans/2026-05-07-config-phase2-cost-telemetry.md`
**Date:** 2026-05-07

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.
Telemetry SQL checks are written as command-line checks using `uv run python -c`.

DuckDB allows only one writer process for `neurodb.duckdb`. Do not keep Streamlit running while running CLI SQL checks. Run T1 before starting Streamlit. For T2-T6, start Streamlit only to generate the telemetry event, stop Streamlit with `Ctrl+C`, then run the CLI check.

---

## Prerequisites

1. Config Control Phase 1 is signed off.
2. Phase 2 implementation is complete.
3. Automated tests pass:

```bash
uv run pytest tests/ -q --tb=no
```

Expected: 344 tests pass.

4. Do not start Streamlit yet. T1 must run with Streamlit stopped.

5. When a test step asks you to generate telemetry through the UI, start the app in a separate terminal:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

Then stop it with `Ctrl+C` before running that step's CLI check.

---

## Stop Criteria

Stop and fix before sign-off if telemetry:

- breaks chat, summary generation, or Knowledge Library approval;
- fails to write rows for successful model calls;
- records the wrong model for a Phase 1 model-routing path;
- loses all token data when the Anthropic response includes usage;
- causes DB lock errors during Knowledge Library approval.

---

## Run Summary — 2026-05-08

| Eval | Result | Notes |
|------|--------|-------|
| T1 — Schema exists | Pass | `model_call_log` exists and can be queried after schema initialization. |
| T2 — Local DB agent telemetry | Pass | Local DB model-call rows were written and queryable after stopping Streamlit. |
| T3 — Neuro-Tutor telemetry | Pass | Neuro-Tutor model-call rows were written with expected task/mode/model fields. |
| T4 — Neuro-Research telemetry | Pass | Neuro-Research telemetry rows captured task, model, iteration, stop reason, and elapsed time. |
| T5 — Session summary telemetry | Pass | Session-summary telemetry rows were written with summary task type and model. |
| T6 — Knowledge Library summary telemetry | Pass | Knowledge-source summary telemetry was written without DB lock errors. |
| T7 — Aggregated cost/token query | Pass | Aggregation query returned grouped task/model rows suitable for cost analysis. |

---

## Evals

### T1 — Schema exists

**Setup:** Run this CLI check after Phase 2 implementation. The command calls `init_db()` directly, so Streamlit must be stopped.

**CLI check:**

```bash
uv run python -c "from sqlalchemy import text; from neurodb.db import get_engine, init_db; e=get_engine('duckdb:///neurodb.duckdb'); init_db(e); print(e.connect().execute(text('SELECT COUNT(*) FROM model_call_log')).scalar())"
```

**Pass criteria:**
- Query succeeds
- Table exists in fresh DBs
- Existing DB migration creates the table without data loss

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Schema check passed. |

---

### T2 — Local DB agent telemetry

**Mode:** Local DB
**Prompt:** "How many studies are in the database? List them by source."

**Setup:** Start Streamlit, run the prompt in Local DB mode, then stop Streamlit before running the CLI check.

**CLI check:**

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, mode, model, stop_reason, input_tokens, output_tokens FROM model_call_log WHERE task_type = 'agent.loop.local_db' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- At least one row is written
- `mode = local_db`
- `model` matches `NEURODB_AGENT_MODEL`
- `stop_reason` is populated
- Token fields are populated when Anthropic usage is available

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Local DB telemetry row present after running the prompt and stopping Streamlit before CLI query. |

---

### T3 — Neuro-Tutor telemetry

**Mode:** Neuro-Tutor
**Prompt:** "Explain long-term potentiation and relate it to memory formation."

**Setup:** Start Streamlit, run the prompt in Neuro-Tutor mode, then stop Streamlit before running the CLI check.

**CLI check:**

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, mode, model, tool_name, tool_names_json, stop_reason FROM model_call_log WHERE task_type = 'agent.loop.neuro_tutor' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- At least one row is written
- `mode = neuro_tutor`
- `model` matches `NEURODB_AGENT_MODEL`
- Tool-use rows capture `tool_name` or `tool_names_json` when tools are requested

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Neuro-Tutor telemetry row present with expected task/mode/model fields. |

---

### T4 — Neuro-Research telemetry

**Mode:** Neuro-Research
**Prompt:** "Use current knowledge to draft a research question about synaptic plasticity and memory."

**Setup:** Start Streamlit, run the prompt in Neuro-Research mode, then stop Streamlit before running the CLI check.

**CLI check:**

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, mode, model, iteration, tool_name, stop_reason, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.neuro_research' ORDER BY recorded_at DESC LIMIT 20'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- Multiple iterations write multiple rows when tools are used
- `iteration` is 1-based and increases within the turn
- `model` matches `NEURODB_RESEARCH_MODEL`
- `elapsed_ms` is populated for successful calls

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Neuro-Research telemetry rows present with iteration and elapsed-time fields. |

---

### T5 — Session summary telemetry

**Setup:** Start Streamlit, complete at least 3 user turns, press Clear to trigger session summary, then stop Streamlit before running the CLI check.

**CLI check:**

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, mode, model, input_tokens, output_tokens, stop_reason FROM model_call_log WHERE task_type = 'summary.session' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- One row is written for the summary call
- `mode = summary`
- `model` matches `NEURODB_SUMMARY_MODEL`
- Summary still stores normally

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Session-summary telemetry row present. |

---

### T6 — Knowledge Library summary telemetry

**Setup:** Start Streamlit, queue and approve one Knowledge Library source with `ANTHROPIC_API_KEY` available, then stop Streamlit before running the CLI check.

**CLI check:**

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, mode, model, input_tokens, output_tokens, stop_reason FROM model_call_log WHERE task_type = 'summary.knowledge_source' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- One row is written for the source-summary model call
- `model` matches `NEURODB_KNOWLEDGE_SUMMARY_MODEL`
- Approval succeeds without DB lock errors
- The approved source still stores its summary

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Knowledge-source summary telemetry row present; no DB lock error observed during approval flow. |

---

### T7 — Aggregated cost/token query

**CLI check:**
Streamlit must be stopped for this check.

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT task_type, model, COUNT(*) AS calls, SUM(COALESCE(input_tokens, 0)) AS input_tokens, SUM(COALESCE(output_tokens, 0)) AS output_tokens, SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd FROM model_call_log GROUP BY task_type, model ORDER BY calls DESC'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**
- Query returns grouped rows by task and model
- Token totals are usable for cost analysis
- Null cost estimates do not break aggregation

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Aggregate telemetry query returned grouped task/model cost-token rows. |

---

## Sign-off

All 7 evals must pass before proceeding to Config Control Phase 3.

| Tester | Date | Result |
|--------|------|--------|
| User | 2026-05-08 | Pass |
