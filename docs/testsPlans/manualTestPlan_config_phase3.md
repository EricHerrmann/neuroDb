# Config Control Phase 3 — Manual Test Plan

**Epoch scope:** Config Control — validates the Research Synthesis Split: standard-tier research drafting, premium-tier hypothesis critique, no duplicate hypothesis persistence, and telemetry for both paid model paths.

**Status:** Signed off
**Created:** 2026-05-08
**Signed off:** 2026-05-08
**Manual eval count:** 4
**Automated gate:** `uv run pytest tests/ -q --tb=no`

---

## Preconditions

1. Config Control Phase 2 is signed off.
2. `.env` contains:
   - `ANTHROPIC_API_KEY`
   - `NEURODB_RESEARCH_MODEL=claude-sonnet-4-6` or another standard-tier model
   - `NEURODB_PREMIUM_MODEL=claude-opus-4-7` or another premium-tier model
3. The local database has been initialized with Phase 3 schema migrations.
4. Streamlit is not running when CLI SQL checks are executed against `neurodb.duckdb`; DuckDB allows only one writer process.

---

## Automated Gate — Regression Suite Passes

**Purpose:** Confirm Phase 3 did not regress existing DB, agent, UI, telemetry, or research workflows before paid manual evals are run.

**Steps:**

1. From the repository root, run:

```bash
uv run pytest tests/ -q --tb=no
```

**Pass criteria:**

- The full test suite passes.
- Expected count for this implementation checkpoint is `350 passed`.
- Warnings are acceptable only if they match the existing deprecation/SQLAlchemy warnings and no tests fail.

---

## T1 — Research Loop Drafts Hypothesis With Standard Model

**Purpose:** Confirm the research loop still drafts hypotheses through the normal agent loop model.

**Steps:**

1. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

2. In Chat, select Neuro-Research mode.
3. Ask for a plasticity-focused research hypothesis grounded in local datasets.
4. Wait for the agent to produce a draft hypothesis.
5. Stop Streamlit before running the SQL check.
6. Run:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine, init_db; e=get_engine('duckdb:///neurodb.duckdb'); init_db(e); sql='''SELECT id, title, status, evidence_json, predictions_json, datasets_json, confounds_json, limitations FROM research_hypotheses ORDER BY created_at DESC LIMIT 1'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**

- One recent `research_hypotheses` row exists.
- `status` is `draft`.
- Evidence, predictions, datasets, confounds, and limitations are populated.

---

## T2 — Review Hypothesis Uses Premium Model

**Purpose:** Confirm the explicit review action uses the premium model and renders a critique, not a second draft.

**Steps:**

1. Start Streamlit.
2. Open the Research tab.
3. Locate the most recent draft hypothesis.
4. Click `Review Hypothesis`.
5. Wait for the critique to render.
6. Stop Streamlit before running the SQL check.
7. Run:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine, init_db; e=get_engine('duckdb:///neurodb.duckdb'); init_db(e); sql='''SELECT hypothesis_id, model, status, critique_text, unsupported_claims_json, missing_confounds_json, suggested_revisions FROM hypothesis_reviews ORDER BY created_at DESC LIMIT 1'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**

- One recent `hypothesis_reviews` row exists.
- `model` matches `NEURODB_PREMIUM_MODEL`.
- Critique text is populated.
- At least one of `unsupported_claims_json`, `missing_confounds_json`, or `suggested_revisions` contains substantive review content.
- The UI labels the output as a critique/review of a draft hypothesis.

---

## T3 — Review Does Not Double Persist Hypothesis

**Purpose:** Confirm the premium review creates only a linked review row and does not create a second `ResearchHypothesis`.

**Steps:**

1. Stop Streamlit.
2. Before running a review, capture current counts:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine, init_db; e=get_engine('duckdb:///neurodb.duckdb'); init_db(e); sql='''SELECT (SELECT COUNT(*) FROM research_hypotheses) AS hypotheses, (SELECT COUNT(*) FROM hypothesis_reviews) AS reviews'''; print(json.dumps(dict(e.connect().execute(text(sql)).mappings().one()), indent=2))"
```

3. Start Streamlit and click `Review Hypothesis` for one existing draft.
4. Stop Streamlit.
5. Re-run the count query.

**Pass criteria:**

- `research_hypotheses` count is unchanged.
- `hypothesis_reviews` count increases by exactly one.

---

## T4 — Telemetry Captures Standard And Premium Calls

**Purpose:** Confirm Phase 2 telemetry can distinguish the normal research loop model from the premium review model.

**Steps:**

1. Stop Streamlit.
2. Run:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine, init_db; e=get_engine('duckdb:///neurodb.duckdb'); init_db(e); sql='''SELECT task_type, mode, model, stop_reason, input_tokens, output_tokens FROM model_call_log WHERE task_type IN ('agent.loop.neuro_research', 'review.hypothesis') ORDER BY recorded_at DESC LIMIT 10'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

**Pass criteria:**

- At least one `agent.loop.neuro_research` row exists using the standard research model.
- At least one `review.hypothesis` row exists using `NEURODB_PREMIUM_MODEL`.
- Token fields are populated when the provider response includes usage.
- No telemetry write failure interrupts the UI workflow.

---

## Sign-Off Criteria

The automated gate and all 4 manual evals must pass before proceeding to Config Control Phase 4.

---

## Results

| Check | Result | Notes |
|-------|--------|-------|
| Automated gate | Pass | `350 passed` |
| T1 — Research loop drafts hypothesis with standard model | Pass | Draft hypothesis saved for later review |
| T2 — Review Hypothesis uses premium model | Pass with follow-up | Review persisted and rendered; response was not structured JSON and required manual revision |
| T3 — Review does not double persist hypothesis | Pass with follow-up | Hypothesis count stayed stable; same structured-JSON issue observed as T2 |
| T4 — Telemetry captures standard and premium calls | Pass | Standard research-loop and premium review telemetry rows verified |

**Follow-up:** LOG-044 tracks hardening the premium review response format so the review output is structured JSON without manual revision.
