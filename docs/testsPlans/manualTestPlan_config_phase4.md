# Manual Test Plan — Config Phase 4: Provider Abstraction + Config-Driven Model Table

**Phase:** Config Control Phase 4
**Status:** Signed off — 2026-05-09
**Last updated:** 2026-05-09

---

## Purpose

Verify that `ModelClient` abstraction correctly decouples `BaseAgent` from the Anthropic SDK, that the config-driven model table routes tasks to the correct provider and model, and that the OpenAI, Groq, and Gemini adapters produce results comparable to the Anthropic baseline.

---

## Prerequisites

- 398 automated tests passing (Phase 5B routing refactor complete)
- `.env` contains `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`, `GOOGLE_API_KEY`
- Streamlit server stopped before each CLI telemetry query
- Provider selection is controlled exclusively via `neurodb_models.toml` `[routing]` section — no env vars needed or supported

DuckDB allows only one writer process for `neurodb.duckdb`. When a test step asks you to verify telemetry from the command line, stop Streamlit with `Ctrl+C` first, then run the `uv run python -c ...` query.

Use this Streamlit command whenever a test asks you to start the app:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

### Changing providers

To route a tier to a different provider, edit `neurodb_models.toml` directly:

```toml
[routing]
economy  = "anthropic"   # change to "openai", "gemini", or "groq"
standard = "anthropic"
premium  = "anthropic"
```

After testing with a non-Anthropic provider, restore all three lines back to `"anthropic"` before starting the next test.

### Telemetry Query Pattern

Full list of `task_type` values, their tiers, `max_tokens`, and producing code: see the **Telemetry task types** table in `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` → Configuration Control Epoch section.

After producing a model call in the UI, stop Streamlit and query `model_call_log` directly. Replace the `WHERE` clause as directed in each test.

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.local_db' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

Telemetry passes only when the relevant query returns at least one recent row with the expected `task_type`, `provider`, and `model`. Token fields may be provider-dependent, but `stop_reason` and `elapsed_ms` should be populated for completed calls.

---

## Evals

### T1 — Anthropic baseline passes existing agent loop

**Goal:** Confirm that `BaseAgent` refactored to use `AnthropicModelClient` produces identical results to the pre-Phase 4 baseline.

1. Confirm `[routing]` in `neurodb_models.toml` has all three tiers set to `"anthropic"` (the default).
2. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

3. Open Chat tab → DB mode
4. Ask: "How many datasets are in the database?"
5. Stop Streamlit.
6. Verify telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.local_db' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

7. **Pass:** Agent responds with a count grounded in a `query_db` tool call. Telemetry returns at least one recent `agent.loop.local_db` row with `provider=anthropic`, `mode=local_db`, the configured standard-tier model, and a `query_db` tool entry.

---

### T2 — Config-driven model table routes tasks correctly

**Goal:** Verify `get_model_for_task` returns the right model for each task type.

1. Confirm `[routing]` has all tiers set to `"anthropic"`.
2. Run the config lookup from the command line:

```bash
uv run python -c "from neurodb.config.model_config import get_model_for_task; print(get_model_for_task('summary.session')); print(get_model_for_task('agent.loop.research')); print(get_model_for_task('research.hypothesis_review'))"
```

3. Expected output:

```text
('anthropic', 'claude-haiku-4-5-20251001', 512)
('anthropic', 'claude-sonnet-4-6', 2048)
('anthropic', 'claude-opus-4-7', 4096)
```

4. **Pass:** All three returned tuples match `neurodb_models.toml`.

---

### T3 — TaskRouter wires correct client to agents

**Goal:** Confirm that the research agent receives the standard-tier client and hypothesis review receives the premium-tier client.

1. Confirm `[routing]` has all tiers set to `"anthropic"`.
2. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

3. Open Research tab in Streamlit.
4. Submit a research question.
5. Trigger a hypothesis review after the draft hypothesis is available.
6. Stop Streamlit.
7. Verify research-loop telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.neuro_research' ORDER BY recorded_at DESC LIMIT 20'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

8. Verify hypothesis-review telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'review.hypothesis' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

9. **Pass:** Research-loop telemetry shows recent `agent.loop.neuro_research` rows with `model=claude-sonnet-4-6`. Hypothesis-review telemetry shows a recent `review.hypothesis` row with `model=claude-opus-4-7` and `tool_name=submit_critique` or `tool_names_json` containing `submit_critique`.

---

### T4 — Hypothesis review returns structured JSON (LOG-044 fix)

**Goal:** Verify the `submit_critique` tool-use approach forces structured output from the premium review call.

1. Confirm `[routing]` has all tiers set to `"anthropic"`.
2. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

3. Open Research tab.
4. Submit a research question that results in a draft hypothesis.
5. Trigger hypothesis review.
6. Stop Streamlit.
7. Verify the persisted review:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT id, hypothesis_id, model, critique_text, unsupported_claims_json, missing_confounds_json, suggested_revisions, status FROM hypothesis_reviews ORDER BY created_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

8. Verify the premium-call telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'review.hypothesis' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

9. **Pass:** Review fields (`critique_text`, `unsupported_claims`, `missing_confounds`, `suggested_revisions`) are all populated with structured values. No fallback message ("Revise manually; response was not structured JSON") appears in the review. Telemetry includes the premium model and the `submit_critique` tool-use call.

---

### T5 — OpenAI adapter agent loop (provider parity)

**Goal:** Confirm the OpenAI adapter can run the DB agent loop end-to-end.

Requires `OPENAI_API_KEY` in `.env`.

The standard-tier OpenAI model is `gpt-5.4`. Telemetry must show this ID.

1. Edit `neurodb_models.toml` `[routing]` to route the standard tier to OpenAI:

```toml
[routing]
economy  = "anthropic"
standard = "openai"
premium  = "anthropic"
```

2. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

3. Open Chat tab → DB mode.
4. Ask: "How many datasets are in the database?"
5. Stop Streamlit.
6. Verify telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.local_db' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

7. **Pass:** Agent responds with a count grounded in a `query_db` tool call. The newest relevant telemetry row has `provider=openai`, `model=gpt-5.4`, and a `query_db` tool entry.
8. **Restore:** Reset `[routing]` back to all `"anthropic"` before the next test.

---

### T6 — Phase 1 evals re-run against OpenAI provider

**Goal:** Validate provider parity across economy and standard tiers with OpenAI.

The economy-tier OpenAI model is `gpt-5.4-mini` and the standard-tier is `gpt-5.4`. Telemetry must show these IDs.

1. Edit `neurodb_models.toml` `[routing]` to route economy and standard to OpenAI:

```toml
[routing]
economy  = "openai"
standard = "openai"
premium  = "anthropic"
```

2. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

3. Run through Phase 1 evals (T1–T5 from `manualTestPlan_config_phase1.md`) with OpenAI as the provider.
4. Stop Streamlit after each model-call eval and run the matching telemetry query from Phase 2 or this plan for the task type under test.
5. **Pass:** All Phase 1 evals produce qualitatively equivalent results with OpenAI provider. The newest relevant telemetry rows use `provider=openai` with `model=gpt-5.4-mini` (economy) or `model=gpt-5.4` (standard) as appropriate.
6. **Restore:** Reset `[routing]` back to all `"anthropic"` before the next test.

---

### T7 — Gemini adapter agent loop (provider parity)

**Goal:** Confirm the Gemini adapter (OpenAI-compatible endpoint) can run the DB agent loop end-to-end.

Requires `GOOGLE_API_KEY` in `.env`.

1. Verify `GOOGLE_API_KEY` is present in `.env`.
2. Confirm `build_provider_clients()` returns a `gemini` key:

```bash
uv run python -c "from dotenv import load_dotenv; load_dotenv(); from neurodb.config.provider_factory import build_provider_clients; p = build_provider_clients(); print(list(p.keys()))"
```

Expected output includes `gemini`.

3. Edit `neurodb_models.toml` `[routing]` to route the standard tier to Gemini:

```toml
[routing]
economy  = "anthropic"
standard = "gemini"
premium  = "anthropic"
```

4. Confirm the config lookup returns the Gemini model:

```bash
uv run python -c "from neurodb.config.model_config import get_model_for_task; print(get_model_for_task('agent.loop.neuro_research'))"
```

Expected: `('gemini', 'gemini-2.5-flash', 4096)`

5. Start Streamlit:

```bash
uv run streamlit run src/neurodb/ui/app.py -- --db neurodb.duckdb
```

6. Open Chat tab → DB mode.
7. Ask: "How many datasets are in the database?"
8. Stop Streamlit.
9. Verify telemetry:

```bash
uv run python -c "import json; from sqlalchemy import text; from neurodb.db import get_engine; e=get_engine('duckdb:///neurodb.duckdb'); sql='''SELECT recorded_at, task_type, provider, mode, model, iteration, tool_name, tool_names_json, stop_reason, input_tokens, output_tokens, elapsed_ms FROM model_call_log WHERE task_type = 'agent.loop.local_db' ORDER BY recorded_at DESC LIMIT 5'''; rows=e.connect().execute(text(sql)).mappings().all(); print(json.dumps([dict(r) for r in rows], indent=2, default=str))"
```

10. **Pass:** Agent responds with a count grounded in a `query_db` tool call. The newest relevant telemetry row has `provider=gemini`, `model=gemini-2.5-flash`, and a `query_db` tool entry.
11. **Restore:** Reset `[routing]` back to all `"anthropic"`.

---

## Sign-off Criteria

All seven evals pass, no regressions in automated test suite (398+ tests), LOG-044 resolved.
