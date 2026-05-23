# Phase 6 — Provider Fallback Chain, SystemWarning, and Telemetry Surface

**Date:** 2026-05-23
**Epoch:** Config Control
**Status:** Complete - implemented and signed off 2026-05-23
**Resolves:** LOG-006 (model visibility), LOG-041 (session summary visibility), LOG-047 (telemetry timestamp format)
**Promotes to first-class:** Design Choice 2 (per-provider capability flags)

---

## Goals

1. Make routing resilient: when the configured provider for a tier is unavailable or incompatible with a task type, automatically walk a fallback chain to a viable provider rather than raising a hard error.
2. Make routing observable: record every skip and fallback decision in a `system_warnings` table so operators can see why a non-primary provider was used.
3. Surface telemetry to operators: a `neurodb telemetry` CLI command with human-readable output covering both model call costs and routing warnings.
4. Surface routing state in the UI: a small active-provider chip in the React header and session summary text visible in the chat history sidebar.

---

## Section 1 — TOML Capability Flags and Fallback Order

### Fallback lists

Added to the `[routing]` section of `neurodb_models.toml`. One list per tier, containing all five providers in preference order. The primary provider is included — the router deduplicates at runtime so the primary is never tried twice.

```toml
[routing]
economy           = "anthropic"
standard          = "anthropic"
premium           = "anthropic"
economy_fallback  = ["anthropic", "openai", "gemini", "deepseek", "groq"]
standard_fallback = ["anthropic", "openai", "gemini", "deepseek", "groq"]
premium_fallback  = ["anthropic", "openai", "gemini", "deepseek", "groq"]
```

**Deduplication rule:** the router builds the candidate list as:
```
[primary] + [p for p in fallback_list if p != primary]
```
This means every provider appears exactly once. If the primary changes (e.g. `standard = "gemini"`), the effective walk becomes `gemini → anthropic → openai → deepseek → groq` with no changes to the fallback lists.

### Capability flags

Two optional boolean fields added to `[tiers.X.providers.Y]` blocks. Absent means no constraint.

| Flag | Meaning |
|------|---------|
| `requires_tools = true` | Model returns empty content when no tool list is supplied. Must not be routed to `summary.*` tasks. |
| `tool_loop_reliable = false` | Model calls tools repeatedly without emitting a final answer. Must not be routed to `agent.loop.*` tasks. |

Applied to the two providers with documented live-validation failures:

```toml
[tiers.economy.providers.gemini]
model = "gemini-2.5-flash-lite"
eval_status = "degraded"
last_verified_at = "2026-05-20"
tool_loop_reliable = false

[tiers.premium.providers.groq]
model = "openai/gpt-oss-120b"
eval_status = "degraded"
last_verified_at = "2026-05-20"
requires_tools = true
tool_loop_reliable = false
```

Any provider added in future phases gets `eval_status = "unverified"` by default. Capability flags are added only after live validation establishes a failure mode.

---

## Section 2 — TaskRouter Fallback Chain

### Task capability inference

`TaskRouter` infers capability requirements from the task type prefix. No new TOML section or metadata required.

| Task type prefix | `uses_tools` | `is_agent_loop` |
|------------------|-------------|-----------------|
| `summary.*` | `False` | `False` |
| `agent.loop.*` | `True` | `True` |
| `research.*` | `True` | `False` |
| anything else | unconstrained | unconstrained |

### Route resolution algorithm

`TaskRouter.route(task_type, engine=None)` — `engine` is optional; if supplied, routing decisions are persisted to `system_warnings`.

1. Look up tier, max_tokens from TOML `[tasks.*]`.
2. Infer `uses_tools` and `is_agent_loop` from task type prefix.
3. Build deduplicated candidate list: `[primary] + [p for p in fallback_list if p != primary]`.
4. Walk candidates. For each provider, check in order:
   - **Registered?** Provider name present in the `providers` dict (API key configured). If not → skip, `warning_type = "provider_missing"`, `severity = "warning"`.
   - **Not degraded?** `eval_status != "degraded"`. If degraded → skip, `warning_type = "provider_degraded"`, `severity = "warning"`.
   - **Capability compatible?** If provider has `requires_tools = true` and `uses_tools` is `False` → skip, `warning_type = "capability_mismatch"`, `severity = "warning"`. If provider has `tool_loop_reliable = false` and `is_agent_loop` is `True` → skip, same.
5. First provider passing all checks:
   - If it is not the primary → persist one `routing_fallback` row, `severity = "info"`, message names the selected provider and summarises why each skipped provider was rejected.
   - Each skipped provider already produced its own row in step 4. The `routing_fallback` row is the summary outcome row; skip rows are the per-provider detail rows.
   - Return `ModelRoute`.
6. If no provider passes → persist `routing_failed` row, `severity = "error"`, raise `RoutingError` with a message listing all providers and their rejection reasons.

### Interface changes

`TaskRouter.__init__` signature is unchanged. `route()` gains one optional keyword argument:

```python
def route(self, task_type: str, *, engine: Engine | None = None) -> ModelRoute: ...
```

Callers that don't supply `engine` get the same routing behaviour with no DB writes. All existing call sites continue to work without modification; only callers that want warning persistence pass `engine`.

### RoutingError

A new exception class in `neurodb.config.task_router`:

```python
class RoutingError(Exception):
    """Raised when no provider in the fallback chain can serve a task type."""
```

Replaces the bare `KeyError` that the current `route()` raises.

---

## Section 3 — SystemWarning Table

### Schema

```python
class SystemWarning(Base):
    __tablename__ = "system_warnings"

    id: int (PK, sequence)
    recorded_at: varchar(32)   # ISO 8601
    warning_type: varchar(32)  # provider_missing | provider_degraded |
                               # capability_mismatch | routing_fallback | routing_failed
    severity: varchar(8)       # info | warning | error
    task_type: varchar(128)
    requested_provider: varchar(64) | null   # provider that was skipped or attempted
    selected_provider: varchar(64) | null    # provider actually used; null if routing failed
    message: text
```

### Migration

Migration 013 in `src/neurodb/db.py` creates `system_warnings` with `CREATE TABLE IF NOT EXISTS` and indexes on `recorded_at`, `warning_type`, and `severity`.

### Example rows

For a standard-tier agent loop where anthropic key is missing and openai is selected:

| warning_type | severity | task_type | requested_provider | selected_provider | message |
|---|---|---|---|---|---|
| provider_missing | warning | agent.loop.neuro_tutor | anthropic | null | anthropic not registered (missing API key) |
| routing_fallback | info | agent.loop.neuro_tutor | anthropic | openai | selected fallback: openai (anthropic: missing API key) |

For a case where all providers are exhausted:

| warning_type | severity | task_type | requested_provider | selected_provider | message |
|---|---|---|---|---|---|
| routing_failed | error | agent.loop.neuro_tutor | null | null | no viable provider found: anthropic (degraded), openai (missing), gemini (capability_mismatch), deepseek (missing), groq (capability_mismatch) |

---

## Section 4 — CLI Telemetry Surface

### Command

```
uv run neurodb telemetry [--tail N] [--provider PROVIDER] [--task-type PREFIX] [--warnings-only]
```

Defaults: `--tail 20`, no provider or task-type filter. `--warnings-only` suppresses the call log section and shows only system warnings.

### Output format

```
Model Call Log (last 20)
────────────────────────────────────────────────────────────────────
13:45:22 23/05/26  agent.loop.neuro_tutor      anthropic / claude-sonnet-4-6    1,234 in / 456 out   ~$0.0023
13:44:01 23/05/26  summary.session             anthropic / claude-haiku-4-5       312 in / 128 out   ~$0.0002

System Warnings (last 10)
────────────────────────────────────────────────────────────────────
13:45:20 23/05/26  [warning]  provider_missing    agent.loop.neuro_tutor    anthropic → (none)
13:45:21 23/05/26  [info]     routing_fallback    agent.loop.neuro_tutor    anthropic → openai
```

### Timestamp formatting

All timestamps from the DB are stored as ISO 8601. A shared `format_recorded_at(iso: str) -> str` utility in `src/neurodb/config/telemetry_format.py` converts to `HH:MM:SS DD/MM/YY`. Resolves LOG-047. The formatter is importable by any future surface (API endpoint, UI) that needs the same format.

### Entry point

Added to `pyproject.toml` scripts as `neurodb-telemetry`. Follows the same pattern as existing CLI entry points: `load_dotenv()` first, then `get_engine()`, then query and print.

---

## Section 5 — React UI Additions

### Active provider chip (LOG-006)

A small read-only badge added to the existing app header bar. Reads from `/api/model-info` (already implemented) via `useQuery` with `staleTime: Infinity` — fetched once on page load, not polled. Displays the standard-tier provider and model ID:

```
anthropic · claude-sonnet-4-6
```

Rendered as a muted chip with no interaction. Hidden if the endpoint fails or returns no data — no error state shown to the user. Placement: right side of the header, left of any existing controls.

### Session summary viewer (LOG-041)

`chat_sessions.summary_preview` is already populated (truncated to 200 chars) for all completed sessions. No new endpoint or migration required.

In the chat history sidebar, each session entry gains an expandable detail: clicking a session row reveals the `summary_preview` text beneath the session title, labeled "Session summary". Collapsed by default. If `summary_preview` is null or empty, the expand affordance is hidden.

---

## Testing

### Automated

- Unit tests for `TaskRouter.route()` covering: preferred provider selected, fallback triggered by missing key, fallback triggered by degraded status, fallback triggered by capability mismatch, all providers exhausted raises `RoutingError`, deduplication of primary in fallback list, mixed primary routing.
- Unit tests for `format_recorded_at()` covering ISO 8601 → `HH:MM:SS DD/MM/YY` conversion and edge cases.
- Integration test for migration 013 (`system_warnings` table created, idempotent on re-run).
- Unit tests for `SystemWarning` write path using in-memory SQLite engine.

### Manual

A manual test plan (`docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md`) was written before implementation began and signed off 2026-05-23, covering:
- Provider fallback visible in `system_warnings` table when a key is removed
- `neurodb telemetry` output with correct timestamp format
- Active provider chip in UI header matches TOML routing config
- Session summary preview visible in chat history sidebar

---

## Open Issues Resolved

| Log ID | Resolution |
|--------|-----------|
| LOG-006 | Active provider chip in React header reads `/api/model-info` |
| LOG-041 | Session summary preview surfaced in chat history sidebar |
| LOG-047 | `format_recorded_at()` utility; all CLI output in `HH:MM:SS DD/MM/YY` |

## Files Affected

| File | Change |
|------|--------|
| `neurodb_models.toml` | Add fallback lists and capability flags |
| `src/neurodb/config/task_router.py` | Fallback chain, capability inference, `RoutingError` |
| `src/neurodb/config/model_config.py` | Read fallback lists and capability flags from TOML |
| `src/neurodb/config/telemetry_format.py` | New — `format_recorded_at()` utility |
| `src/neurodb/schema.py` | Add `SystemWarning` ORM class |
| `src/neurodb/db.py` | Migration 013 — create `system_warnings` table |
| `src/neurodb/cli/telemetry.py` | New — `neurodb telemetry` CLI entry point |
| `pyproject.toml` | Register `neurodb-telemetry` script |
| `frontend/src/components/` | New — `ProviderChip` component |
| `frontend/src/pages/` | Update header layout, session history sidebar |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_phase6_fallback_telemetry.md` | Manual test plan — T1-T5 passed and signed off 2026-05-23 |
