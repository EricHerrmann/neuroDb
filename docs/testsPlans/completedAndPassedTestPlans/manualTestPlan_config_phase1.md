# Config Control Phase 1 — Manual Test Plan

**Epoch scope:** Config Control — tests per-agent model env var wiring against the live Streamlit app.

**Feature:** Per-task model env vars replacing single global `NEURODB_MODEL`
**Status:** Passed — signed off 2026-05-07
**Plan:** `docs/superpowers/plans/2026-05-07-model-routing-impl.md` (Phase 1, Task 1.4)
**Date:** 2026-05-07

All commands run from the repo root (`/home/oldha/projects/neuroDb`) unless noted.

---

## Prerequisites

1. `.env` has the four new model-routing vars set:
   ```
   NEURODB_AGENT_MODEL=claude-sonnet-4-6
   NEURODB_RESEARCH_MODEL=claude-sonnet-4-6
   NEURODB_SUMMARY_MODEL=claude-haiku-4-5-20251001
   NEURODB_KNOWLEDGE_SUMMARY_MODEL=claude-haiku-4-5-20251001
   ```

2. Automated tests pass:

```bash
uv run pytest tests/ -q --tb=no
```

Expected: 332 tests pass.

3. Start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

---

## Stop Criteria

Per the model routing plan: if Sonnet produces fabricated dataset IDs or incorrect SQL that Opus did not, stop and escalate the affected task type to a higher tier before proceeding to Phase 2.

---

## Run Summary — 2026-05-07

| Eval | Result | Notes |
|------|--------|-------|
| T1 — Local DB query | Pass | Query executed without fabricated dataset IDs or source names. |
| T2 — External DB discovery | Pass | Discovery flow returned grounded candidates or no-results behavior without fabricated accessions. |
| T3 — Neuro-Tutor explanation | Pass | Final response was clear and scientifically useful; local DB no-results wait behavior remains logged for monitoring in `LOG-040`. |
| T4 — Session summary on Clear | Pass | Summary generation passed; UI visibility for directly reviewing summary date/topic/key concepts remains logged as `LOG-041`. |
| T5 — Knowledge Library source summary | Pass | Source summary generated without invented source metadata. |

---

## Evals

### T1 — Local DB query (Sonnet via `NEURODB_AGENT_MODEL`)

**Mode:** Local DB (default mode)
**Prompt:** "How many studies are in the database? List them by source."

**Pass criteria:**
- Query executes without error
- Result cites correct SQL or shows accurate counts from real data
- No fabricated dataset IDs or source names
- Response is grounded in actual DB contents

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Query executed without error and stayed grounded in DB contents. |

---

### T2 — External DB discovery (Sonnet via `NEURODB_AGENT_MODEL`)

**Mode:** Local DB
**Prompt:** "Search for fMRI studies related to working memory on OpenNeuro."

**Pass criteria:**
- Agent calls search tools without error
- Returns valid, real dataset candidates (or reports no results)
- No fabricated OpenNeuro accession numbers

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Search behavior completed without fabricated OpenNeuro accession numbers. |

---

### T3 — Neuro-Tutor explanation (Sonnet via `NEURODB_AGENT_MODEL`)

**Mode:** Neuro-Tutor
**Prompt:** "Explain long-term potentiation and how it relates to memory formation."

**Pass criteria:**
- Response is clear and scientifically accurate
- References Knowledge Library if relevant prior learning exists
- No hallucinated citations

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Good final response. A local DB no-results wait/hang observation is tracked separately as `LOG-040`. |

---

### T4 — Session summary on Clear (Haiku via `NEURODB_SUMMARY_MODEL`)

**Setup:** Complete at least 3 user turns in any agent mode, then press "Clear" to trigger session summary.

**Pass criteria:**
- Summary generates without error
- Correct date, topic, and key concepts captured
- No invented datasets or session content
- Summary is structurally coherent (not truncated or malformed)

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Summary generation passed. Direct UI review of generated summaries is tracked as a feature review in `LOG-041`. |

---

### T5 — Knowledge Library source summary (Haiku via `NEURODB_KNOWLEDGE_SUMMARY_MODEL`)

**Setup:** In Neuro-Tutor mode, add a knowledge source (any URL or PDF) to the Knowledge Library.

**Pass criteria:**
- Summary generates without error
- Useful structured summary of the source content
- No invented DOI, author names, or source claims
- Summary fits expected format

| | Result |
|--|--------|
| Pass / Fail | Pass |
| Notes | Generated a useful structured source summary without invented DOI, author, or source claims. |

---

## Sign-off

All 5 evals must pass before proceeding to Phase 2.

| Tester | Date | Result |
|--------|------|--------|
| User | 2026-05-07 | Pass |
