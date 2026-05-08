# Manual Test Plan — Config Phase 4: Provider Abstraction + Config-Driven Model Table

**Phase:** Config Control Phase 4
**Status:** In progress
**Last updated:** 2026-05-08

---

## Purpose

Verify that `ModelClient` abstraction correctly decouples `BaseAgent` from the Anthropic SDK, that the config-driven model table routes tasks to the correct provider and model, and that the OpenAI/Groq adapter produces results comparable to the Anthropic baseline.

---

## Prerequisites

- 350 automated tests passing (Phase 3 baseline)
- `.env` contains `ANTHROPIC_API_KEY`, `OPENAI_API_KEY`, `GROQ_API_KEY`
- Streamlit server stopped before each eval run
- `NEURODB_AGENT_MODEL`, `NEURODB_TUTOR_MODEL`, `NEURODB_RESEARCH_MODEL`, `NEURODB_PREMIUM_MODEL` env vars unset (use config-file defaults)

---

## Evals

### T1 — Anthropic baseline passes existing agent loop

**Goal:** Confirm that `BaseAgent` refactored to use `AnthropicModelClient` produces identical results to the pre-Phase 4 baseline.

1. Start Streamlit: `uv run streamlit run app.py`
2. Open Chat tab → DB mode
3. Ask: "How many datasets are in the database?"
4. **Pass:** Agent responds with a count grounded in a `query_db` tool call. Telemetry row written with `provider=anthropic`.

---

### T2 — Config-driven model table routes tasks correctly

**Goal:** Verify `get_model_for_task` returns the right model for each task type.

1. In a Python shell: `from neurodb.model_config import get_model_for_task`
2. Run: `get_model_for_task("summary.session")` → should return `("anthropic", "claude-haiku-4-5-20251001", 512)`
3. Run: `get_model_for_task("agent.loop.research")` → should return `("anthropic", "claude-sonnet-4-6", 2048)`
4. Run: `get_model_for_task("research.hypothesis_review")` → should return `("anthropic", "claude-opus-4-7", 4096)`
5. **Pass:** All three return the correct (provider, model_id, max_tokens) tuples matching `neurodb_models.toml`.

---

### T3 — TaskRouter wires correct client to agents

**Goal:** Confirm that the research agent receives the standard-tier client and hypothesis review receives the premium-tier client.

1. Open Research tab in Streamlit
2. Submit a research question
3. **Pass:** Telemetry rows show `model=claude-sonnet-4-6` for agent loop iterations and `model=claude-opus-4-7` for the hypothesis review call.

---

### T4 — Hypothesis review returns structured JSON (LOG-044 fix)

**Goal:** Verify the `submit_critique` tool-use approach forces structured output from the premium review call.

1. Open Research tab
2. Submit a research question that results in a draft hypothesis
3. Trigger hypothesis review
4. **Pass:** Review fields (`critique_text`, `unsupported_claims`, `missing_confounds`, `suggested_revisions`) are all populated with structured values. No fallback message ("Revise manually; response was not structured JSON") appears in the review.

---

### T5 — OpenAI adapter agent loop (provider parity)

**Goal:** Confirm the OpenAI adapter can run the DB agent loop end-to-end.

1. Set `NEURODB_AGENT_MODEL_PROVIDER=openai` (or configure via `neurodb_models.toml` override)
2. Start Streamlit
3. Ask: "How many datasets are in the database?"
4. **Pass:** Agent responds with a count grounded in a `query_db` tool call. Telemetry row written with `provider=openai`.

---

### T6 — Phase 1 evals re-run against OpenAI provider

**Goal:** Validate provider parity for per-agent model env var routing.

1. Run through Phase 1 evals (T1–T5 from `manualTestPlan_config_phase1.md`) with OpenAI as the provider
2. **Pass:** All Phase 1 evals produce qualitatively equivalent results with OpenAI provider.

---

## Sign-off Criteria

All six evals pass, no regressions in automated test suite (350+ tests), LOG-044 resolved.
