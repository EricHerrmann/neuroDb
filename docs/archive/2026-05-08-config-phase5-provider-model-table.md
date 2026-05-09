# Config Control Phase 5 — Multi-Provider Model Table

**Date:** 2026-05-08
**Status:** Design — ready for implementation review
**Epoch:** Config Control
**Scope decision:** Two sub-phases. Phase 5A fixes the TOML with correct verified model IDs and wires Gemini. Phase 5B adds a CLI model-freshness check so the table never drifts past 30 days without a flag.

---

## Problem Statement

The `neurodb_models.toml` OpenAI entries (`gpt-5-nano`, `gpt-5-mini`, `gpt-5.2`) were invented placeholders, not real model IDs. Groq and Gemini had no TOML entries at all. The design intent — a single config file where model IDs are updated without code changes — was correct, but the data was wrong and two of four planned providers were unwired.

Phase 5A makes the table accurate and complete. Phase 5B adds tooling so it stays that way.

---

## Verified Model Table (sourced 2026-05-08)

This is the reference table for the TOML update. All entries marked `eval_status = "baseline"` were confirmed against live provider docs on 2026-05-08. Groq Llama 4 entries are `candidate` — Llama 4 Scout/Maverick are newer and multimodal-capable but not yet validated for pure text agent use in this project.

| Tier | Anthropic | OpenAI | Gemini | Groq |
|---|---|---|---|---|
| **economy** | `claude-haiku-4-5-20251001` | `gpt-5.4-nano` | `gemini-2.5-flash-lite` | `llama-3.1-8b-instant` |
| **standard** | `claude-sonnet-4-6` | `gpt-5.4-mini` | `gemini-2.5-flash` | `llama-3.3-70b-versatile` |
| **premium** | `claude-opus-4-7` | `gpt-5.5` | `gemini-2.5-pro` | `openai/gpt-oss-120b` |

**Candidate entries (not yet baseline — require eval before use):**
| Tier | Provider | Model ID | Reason |
|---|---|---|---|
| standard | Groq | `meta-llama/llama-4-scout-17b-16e-instruct` | Newer MoE, multimodal — needs text-agent eval |
| premium | Groq | `meta-llama/llama-4-maverick-17b-128e-instruct` | Newer MoE, multimodal — needs text-agent eval |
| premium | Gemini | `gemini-3.1-pro-preview` | Preview status — prefer 2.5-pro (stable) until GA |

---

## Phase 5A — TOML Fix + Gemini Wiring

### Scope

- Fix all OpenAI model IDs in `neurodb_models.toml`
- Add Groq tier entries to `neurodb_models.toml`
- Add Gemini tier entries to `neurodb_models.toml`
- Add Gemini to `provider_factory.py`
- Add `GEMINI_API_KEY` to `.env.example`
- Unit tests for Gemini client construction and tier override
- No agent code changes — `OpenAIModelClient` already works for Gemini

### Gemini Wiring Design

Google exposes an OpenAI-compatible endpoint. The `OpenAIModelClient` already in the codebase works without modification — only the SDK constructor arguments differ.

**Endpoint:**
```
https://generativelanguage.googleapis.com/v1beta/openai/
```

**Auth:** Bearer token (`GEMINI_API_KEY`). The OpenAI Python SDK accepts this via `api_key=` and `base_url=`.

**Capability support (confirmed):** streaming, tool use, function calling — all use the same OpenAI wire format.

**`provider_factory.py` addition:**

```python
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"

gemini_key = os.environ.get("GEMINI_API_KEY")
if gemini_key:
    try:
        import openai
    except ModuleNotFoundError:
        pass
    else:
        providers["gemini"] = OpenAIModelClient(
            openai.OpenAI(api_key=gemini_key, base_url=_GEMINI_BASE_URL)
        )
```

This mirrors the existing Groq branch exactly. No new client class required.

**TOML addition (new sections):**

```toml
[tiers.economy.providers.gemini]
model = "gemini-2.5-flash-lite"
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.economy.providers.groq]
model = "llama-3.1-8b-instant"
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.standard.providers.gemini]
model = "gemini-2.5-flash"
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.standard.providers.groq]
model = "llama-3.3-70b-versatile"
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.premium.providers.gemini]
model = "gemini-2.5-pro"
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.premium.providers.groq]
model = "openai/gpt-oss-120b"
eval_status = "baseline"
last_verified_at = "2026-05-08"
```

**TOML fix (corrected OpenAI IDs):**

```toml
[tiers.economy.providers.openai]
model = "gpt-5.4-nano"          # was: gpt-5-nano (invalid)
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.standard.providers.openai]
model = "gpt-5.4-mini"          # was: gpt-5-mini (invalid)
eval_status = "baseline"
last_verified_at = "2026-05-08"

[tiers.premium.providers.openai]
model = "gpt-5.5"               # was: gpt-5.2 (invalid)
eval_status = "baseline"
last_verified_at = "2026-05-08"
```

### Activation via env vars

Users select providers per tier using the existing `NEURODB_{TIER}_PROVIDER` mechanism — no new env vars needed:

```bash
# .env — switch standard and premium to Gemini
NEURODB_STANDARD_PROVIDER=gemini
NEURODB_PREMIUM_PROVIDER=gemini
```

Or for Groq:
```bash
NEURODB_STANDARD_PROVIDER=groq
NEURODB_ECONOMY_PROVIDER=groq
```

### 5A File Map

The P4 T5/T6 fix already delivered `provider_factory.py` (Anthropic + OpenAI + Groq), `ModelRoute`, `NEURODB_{TIER}_PROVIDER` env vars, and the `openai` package dependency. Phase 5A is purely a data and one-branch addition — not a rebuild.

| Action | File | Change |
|---|---|---|
| Modify | `neurodb_models.toml` | **Correct** 3 wrong OpenAI IDs (unblocks T5/T6); **add** 6 Gemini entries; **add** 6 Groq entries (factory already handles the keys) |
| Modify | `src/neurodb/config/provider_factory.py` | Add Gemini branch only — Anthropic/OpenAI/Groq already wired |
| Modify | `.env.example` | Add `GEMINI_API_KEY=your_gemini_api_key_here` |
| Modify | `tests/unit/test_provider_factory.py` | Add Gemini test — file already exists for Anthropic/OpenAI/Groq |
| Modify | `tests/unit/test_model_config.py` | Add test: `NEURODB_STANDARD_PROVIDER=gemini` returns gemini model ID |
| Modify | `docs/projectStatus.md` | Update Config Control row |

### 5A Exit Criteria

- All four providers have entries in all three tiers in the TOML
- `build_provider_clients()` returns `"gemini"` key when `GEMINI_API_KEY` is set
- `NEURODB_STANDARD_PROVIDER=gemini` routes `agent.loop.neuro_research` to `gemini-2.5-flash`
- Existing tests still pass
- Manual test plan eval: set `NEURODB_STANDARD_PROVIDER=gemini`, start Streamlit, send one chat message — confirm it routes through Gemini without error

---

## Phase 5B — Model Freshness Check CLI (Future Phase)

### Problem

`last_verified_at` fields exist in the TOML but nothing reads them. Models can be deprecated by providers without any warning in the app. The design target: any `baseline` model older than 30 days is flagged.

### Design

A new CLI entry point: `uv run neurodb models check`

**What it does:**
1. Reads `neurodb_models.toml`
2. For each tier/provider entry that has `eval_status = "baseline"`:
   - If `last_verified_at` is older than 30 days → flag as STALE
   - If API key for that provider is available: call the provider's `/models` endpoint and verify the model ID is in the live list → flag as INVALID if missing
3. Prints a structured report
4. Exits non-zero if any STALE or INVALID entries exist (CI-friendly)

**Provider model list endpoints:**

| Provider | Endpoint | Auth |
|---|---|---|
| anthropic | `https://api.anthropic.com/v1/models` | `x-api-key: {key}` |
| openai | `https://api.openai.com/v1/models` | `Authorization: Bearer {key}` |
| gemini | `https://generativelanguage.googleapis.com/v1beta/openai/models` | `Authorization: Bearer {key}` |
| groq | `https://api.groq.com/openai/v1/models` | `Authorization: Bearer {key}` |

**Output format:**
```
NeuroDb model table check — 2026-05-08

anthropic
  [OK]    economy  claude-haiku-4-5-20251001   verified 2026-05-08 (0 days ago)
  [OK]    standard claude-sonnet-4-6            verified 2026-05-08 (0 days ago)
  [OK]    premium  claude-opus-4-7              verified 2026-05-08 (0 days ago)

openai
  [OK]    economy  gpt-5.4-nano                verified 2026-05-08 (0 days ago)
  [STALE] standard gpt-5.4-mini                last verified 2026-04-01 (37 days ago)
  [INVALID] premium gpt-5.5                    not found in live model list

2 issues found. Update neurodb_models.toml and re-run to clear.
```

**Module location:** `src/neurodb/config/model_check.py`

**CLI entry point:** new script in `pyproject.toml`:
```toml
[project.scripts]
neurodb-models-check = "neurodb.config.model_check:main"
```

Or invocable as:
```bash
uv run python -m neurodb.config.model_check
```

**Key implementation details:**
- Uses `httpx` (already a dependency) for provider API calls — no new packages needed
- Skips API validation for any provider whose key is not in the environment (prints a note)
- Does not modify the TOML — reports only; user updates manually
- `last_verified_at` parsing: ISO date string `YYYY-MM-DD`, compared to today

**Future extension (beyond 5B):** An interactive `--update` flag that proposes TOML edits based on the live model list and most likely tier-appropriate replacement — but this requires per-provider heuristics for what "best at each tier" means, so it is deliberately out of 5B scope.

### 5B File Map

| Action | File | Change |
|---|---|---|
| Create | `src/neurodb/config/model_check.py` | `check_model_table()` + `main()` entry point |
| Modify | `pyproject.toml` | Add `neurodb-models-check` script entry point |
| Create | `tests/unit/test_model_check.py` | Tests: stale detection, invalid detection, all-ok, missing-key skip |
| Modify | `docs/projectStatus.md` | Add Phase 5B to Config Control next |

### 5B Exit Criteria

- `uv run neurodb-models-check` prints a report for all four providers
- Exits non-zero when any STALE or INVALID entry is found
- Exits zero when all entries pass
- Correctly skips API validation when a provider key is absent
- Does not modify `neurodb_models.toml`

---

## Execution Order

Phase 5A is self-contained and can be implemented immediately.
Phase 5B depends on 5A being complete (correct TOML needed to test against).
Within 5A: TOML changes and `provider_factory.py` can be done in parallel;
tests must come before marking done.

---

## Open Questions

1. **Groq premium model**: `openai/gpt-oss-120b` is an OpenAI model running on Groq infrastructure. Should it carry a dependency note so users know it requires a Groq key to serve OpenAI weights? (Informational — no code change needed.)
2. **Gemini 3.1 Pro Preview**: Added as a `candidate` entry. When it reaches GA, upgrade to `baseline` and make it premium. Should the TOML carry explicit notes for preview-status models?
3. **30-day staleness window**: Is 30 days the right threshold? Anthropic and OpenAI release new model generations faster than that sometimes. Could tighten to 14 days.
4. **TOML auto-update in 5B**: The `--update` flag is deferred. Is it wanted in 5B or can it wait for a standalone 5C?
