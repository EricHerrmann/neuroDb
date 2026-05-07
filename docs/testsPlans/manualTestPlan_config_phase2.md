# Config Control Phase 2 — Manual Test Plan

**Epoch scope:** Config Control — validates local model-call telemetry for model-routing cost analysis.

**Feature:** `model_call_log` telemetry for agent loops and summary calls
**Status:** Ready for manual verification — implementation complete; automated tests passed
**Plan:** `docs/superpowers/plans/2026-05-07-config-phase2-cost-telemetry.md`
**Date:** 2026-05-07

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. Config Control Phase 1 is signed off.
2. Phase 2 implementation is complete.
3. Automated tests pass:

```bash
uv run pytest tests/ -q --tb=no
```

Expected: 344 tests pass.

4. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

---

## Stop Criteria

Stop and fix before sign-off if telemetry:

- breaks chat, summary generation, or Knowledge Library approval;
- fails to write rows for successful model calls;
- records the wrong model for a Phase 1 model-routing path;
- loses all token data when the Anthropic response includes usage;
- causes DB lock errors during Knowledge Library approval.

---

## Evals

### T1 — Schema exists

**Setup:** Run the app or call `init_db()` after Phase 2 implementation.

**Check:**

```sql
SELECT COUNT(*) FROM model_call_log;
```

**Pass criteria:**
- Query succeeds
- Table exists in fresh DBs
- Existing DB migration creates the table without data loss

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T2 — Local DB agent telemetry

**Mode:** Local DB
**Prompt:** "How many studies are in the database? List them by source."

**Check:**

```sql
SELECT task_type, mode, model, stop_reason, input_tokens, output_tokens
FROM model_call_log
WHERE task_type = 'agent.loop.local_db'
ORDER BY recorded_at DESC
LIMIT 5;
```

**Pass criteria:**
- At least one row is written
- `mode = local_db`
- `model` matches `NEURODB_AGENT_MODEL`
- `stop_reason` is populated
- Token fields are populated when Anthropic usage is available

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T3 — Neuro-Tutor telemetry

**Mode:** Neuro-Tutor
**Prompt:** "Explain long-term potentiation and relate it to memory formation."

**Check:**

```sql
SELECT task_type, mode, model, tool_name, tool_names_json, stop_reason
FROM model_call_log
WHERE task_type = 'agent.loop.neuro_tutor'
ORDER BY recorded_at DESC
LIMIT 5;
```

**Pass criteria:**
- At least one row is written
- `mode = neuro_tutor`
- `model` matches `NEURODB_AGENT_MODEL`
- Tool-use rows capture `tool_name` or `tool_names_json` when tools are requested

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T4 — Neuro-Research telemetry

**Mode:** Neuro-Research
**Prompt:** "Use current knowledge to draft a research question about synaptic plasticity and memory."

**Check:**

```sql
SELECT task_type, mode, model, iteration, tool_name, stop_reason, elapsed_ms
FROM model_call_log
WHERE task_type = 'agent.loop.neuro_research'
ORDER BY recorded_at DESC
LIMIT 20;
```

**Pass criteria:**
- Multiple iterations write multiple rows when tools are used
- `iteration` is 1-based and increases within the turn
- `model` matches `NEURODB_RESEARCH_MODEL`
- `elapsed_ms` is populated for successful calls

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T5 — Session summary telemetry

**Setup:** Complete at least 3 user turns, then press Clear to trigger session summary.

**Check:**

```sql
SELECT task_type, mode, model, input_tokens, output_tokens, stop_reason
FROM model_call_log
WHERE task_type = 'summary.session'
ORDER BY recorded_at DESC
LIMIT 5;
```

**Pass criteria:**
- One row is written for the summary call
- `mode = summary`
- `model` matches `NEURODB_SUMMARY_MODEL`
- Summary still stores normally

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T6 — Knowledge Library summary telemetry

**Setup:** Queue and approve one Knowledge Library source with `ANTHROPIC_API_KEY` available.

**Check:**

```sql
SELECT task_type, mode, model, input_tokens, output_tokens, stop_reason
FROM model_call_log
WHERE task_type = 'summary.knowledge_source'
ORDER BY recorded_at DESC
LIMIT 5;
```

**Pass criteria:**
- One row is written for the source-summary model call
- `model` matches `NEURODB_KNOWLEDGE_SUMMARY_MODEL`
- Approval succeeds without DB lock errors
- The approved source still stores its summary

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

### T7 — Aggregated cost/token query

**Check:**

```sql
SELECT task_type, model,
       COUNT(*) AS calls,
       SUM(COALESCE(input_tokens, 0)) AS input_tokens,
       SUM(COALESCE(output_tokens, 0)) AS output_tokens,
       SUM(COALESCE(estimated_cost_usd, 0)) AS estimated_cost_usd
FROM model_call_log
GROUP BY task_type, model
ORDER BY calls DESC;
```

**Pass criteria:**
- Query returns grouped rows by task and model
- Token totals are usable for cost analysis
- Null cost estimates do not break aggregation

| | Result |
|--|--------|
| Pass / Fail | |
| Notes | |

---

## Sign-off

All 7 evals must pass before proceeding to Config Control Phase 3.

| Tester | Date | Result |
|--------|------|--------|
| | | Pass / Fail |
