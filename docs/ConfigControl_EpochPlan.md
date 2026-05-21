# NeuroDb — Config Control Epoch Plan

**Status:** Phase 5B complete — 398 automated tests; Phase 4 signed off 2026-05-09
**Last updated:** 2026-05-19
**Epoch directory:** `src/neurodb/config/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Own model and provider selection, capability tier routing, provider adapters, API key management, cost and capability gating, and telemetry-informed routing. Keep the cost envelope stable as the feedback loop matures — more capable, not more expensive.

**Active work:** Phase 4 signed off. Provider-by-provider live model/tool-call validation is required before further routing expansion; Phase 6 (constructor fallback chain, SystemWarning table, CLI telemetry surface) remains planned.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| Phase 1 | Per-agent model env vars; summary model routing | Complete | 332 | 2026-05-07 | `docs/testsPlans/manualTestPlan_config_phase1.md` |
| Phase 2 | `model_call_log` telemetry for agent loops and summary calls | Complete | 344 | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase2.md` |
| Phase 3 | Research Synthesis Split — standard-tier loop + premium hypothesis review | Complete | 350 | 2026-05-08 | `docs/testsPlans/manualTestPlan_config_phase3.md` |
| Phase 4 | `ModelClient` abstraction, `AnthropicModelClient`, `OpenAIModelClient`, `TaskRouter`, config-driven provider selection, `BaseAgent` refactor | Complete | 389 + 7 manual | 2026-05-09 | `docs/testsPlans/manualTestPlan_config_phase4.md` |
| Phase 5A | TOML corrected; 4-provider × 3-tier model table; Gemini wired; tool schemas fixed for OpenAI strict validation | Complete | 397 | 2026-05-08 | — |
| Phase 5B | TOML routing refactor — single `[routing]` section replaces env-var tier overrides | Complete | 398 | 2026-05-08 | — |
| Phase 6 | Constructor fallback chain, `SystemWarning` table, CLI telemetry surface | Planned | — | — | — |

Active test plan: none

---

## Open Backlog

| Log ID | Issue |
|--------|-------|
| LOG-050 | Gemini premium model testing deferred — API account set up; further Gemini premium testing deferred |
| — | DeepSeek wired as future-feature provider — `eval_status = "unverified"` for all tiers; routing and manual eval deferred |
| — | Provider-by-provider live tool-call validation required — mocks do not catch actual model/API tool behavior |
| — | **Design Choice 2 (deferred):** Per-provider capability flags in TOML — prevent routing `degraded` models to incompatible task types at the `TaskRouter` level; see evidence section below |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-07 | Env vars for model selection (Phase 1); TOML for provider routing (Phase 4+) | Env vars sufficient for model name overrides; TOML gives tier × provider × model IDs, version tracking, and eval status in one file |
| 2026-05-08 | `ModelClient` abstract interface wraps all providers | BaseAgent becomes provider-neutral; adding a provider means implementing `ModelClient`, not modifying BaseAgent |
| 2026-05-08 | `GOOGLE_API_KEY` is the env var for Gemini | Google issues a single API key for Gemini; `GEMINI_API_KEY` was an internal naming error |
| 2026-05-09 | `stream_options={"include_usage": True}` required for OpenAI/Gemini streaming token counts | Without it the OpenAI streaming API does not emit a usage chunk; token counts are null in telemetry |
| 2026-05-11 | DeepSeek added as OpenAI-compatible provider via `DEEPSEEK_API_KEY` + `https://api.deepseek.com/v1` | DeepSeek exposes an OpenAI-compatible API; `OpenAIModelClient` handles it with a `base_url` override, same pattern as Groq and Gemini. Models: economy/standard = `deepseek-chat`, premium = `deepseek-reasoner`. |
| 2026-05-19 | OpenAI-compatible does not mean behavior-identical | Live testing found `openai/gpt-5.4` succeeds without tools, fails through Chat Completions when any function tool is supplied, and succeeds with a minimal tool through Responses API. Anthropic `claude-sonnet-4-6` completed the full Tutor tool path. Each provider must have live tool-call validation, not only mocked adapter tests. |

---

## Provider Live Validation Requirement

Manual provider validation must run real model calls because mocked SDK tests only
prove request construction and response mapping. They do not prove that a
provider/model accepts tools, streams tool calls, or returns usable tool-call
payloads.

Required provider matrix:

| Provider | Adapter path | Live checks required |
|----------|--------------|----------------------|
| OpenAI | OpenAI official API | no tools, minimal function tool, Tutor tools, Research tools, streaming tool path |
| Anthropic | Anthropic SDK | no tools, minimal tool, Tutor tools, Research tools, streaming tool path |
| Groq | OpenAI-compatible API | no tools, minimal function tool, Tutor tools, Research tools, streaming tool path |
| Gemini | OpenAI-compatible API | no tools, minimal function tool, Tutor tools, Research tools, streaming tool path |
| DeepSeek | OpenAI-compatible API | no tools, minimal function tool, Tutor tools, Research tools, streaming tool path |

Finding from Phase 4 manual investigation:

- `openai/gpt-5.4` via Chat Completions fails with HTTP 500 when function tools
  are supplied, including a raw minimal tool.
- The same `openai/gpt-5.4` model succeeds with no tools.
- The same `openai/gpt-5.4` model succeeds with a minimal tool through Responses
  API.
- Anthropic `claude-sonnet-4-6` succeeds with no tools, minimal tool, streaming,
  full Tutor tools, and a full Tutor agent loop.

Finding from 2026-05-20 provider probe (all 7 checks after probe script fix):

- **DeepSeek** (`deepseek-chat` economy/standard, `deepseek-reasoner` premium): all 7 checks pass across all three tiers. `eval_status` elevated to `"baseline"`.
- **Groq economy** (`llama-3.1-8b-instant`): all 7 checks pass.
- **Groq standard** (`llama-3.3-70b-versatile`): all 7 checks pass.
- **Groq premium** (`openai/gpt-oss-120b`): checks 1–3 (no tools) return empty content — model requires a tool-calling context to generate any output. Check 7 fails: agent exhausts 3 tool iterations without producing a final answer; model loops tool calls rather than synthesizing. `eval_status` set to `"degraded"`.
- **Gemini economy** (`gemini-2.5-flash-lite`): checks 1–6 pass. Check 7 fails: same max-iterations loop pattern as Groq premium — model calls tools repeatedly but does not exit to a final answer at 512 tokens. `eval_status` set to `"degraded"`.
- **Gemini standard** (`gemini-2.5-flash`): all 7 checks pass.
- **Gemini premium** (`gemini-2.5-pro`): all checks fail with HTTP 429. Expected: Gemini premium tier is not subscribed; `gemini-2.5-pro` remains in TOML for future use but will not be validated.

Design implication:

- Keep a shared OpenAI-compatible base for common translation only.
- Split provider-specific behavior into subclasses or capability adapters.
- OpenAI GPT-5-class tool calls likely need a Responses API adapter rather than
  the current Chat Completions path.
- Groq premium (`openai/gpt-oss-120b`) must not be routed to tool-free tasks (returns empty) or tool-using agent loops (loops without concluding).
- Gemini economy (`gemini-2.5-flash-lite`) loops tools without concluding at the probe's 512-token limit; may succeed with a higher `max_tokens` budget or a stronger system-prompt directive to stop and synthesize.
- The max-iterations loop failure is a separate class of problem from the tool-schema failures seen with OpenAI — it points to models that emit tool calls as their default behaviour rather than treating them as optional. This is a candidate for Design Choice 2 (capability flags in TOML).

---

## Design Choice 2 — Per-Provider Capability Flags (Deferred)

### Problem

Two providers reached `eval_status = "degraded"` during 2026-05-20 live validation because their models fail at the full agent loop (check 7), not at the adapter or schema level:

| Provider | Tier | Model | Failure mode |
|----------|------|-------|--------------|
| Groq | premium | openai/gpt-oss-120b | Returns empty content with no tools (checks 1–3); exhausts `max_tool_iterations` without emitting a final answer (check 7) |
| Gemini | economy | gemini-2.5-flash-lite | Passes checks 1–6; exhausts `max_tool_iterations` without emitting a final answer (check 7) |

These are distinct failure classes from the OpenAI Chat Completions HTTP 500 (schema rejection). The models accept tool schemas and call tools, but treat tool-calling as their terminal output rather than a step toward a final answer. The shared `OpenAIModelClient` cannot paper over this — it is a model behaviour difference.

### Proposed Design

Add optional capability constraint fields to each `[tiers.X.providers.Y]` TOML block:

```toml
requires_tools = true          # model returns empty without a tool list
tool_loop_reliable = false     # model loops tool calls without concluding
```

`TaskRouter.route()` reads these flags and either refuses to route the provider to an incompatible task type (raising a routing error) or falls back to the tier's next available provider. No new adapter code paths; gating is purely at the routing layer.

### Evidence (2026-05-20 probe run, `scripts/probe_provider.py`)

- `openai/gpt-oss-120b` checks 1–3 assertion: `Empty response from raw SDK (no tools)` / `Empty response from adapter (no tools)` / `Empty streaming response from adapter (no tools)`
- `openai/gpt-oss-120b` check 7 assertion: `Agent returned error: [Agent reached maximum tool iterations (3) without a final answer...]`
- `gemini-2.5-flash-lite` check 7 assertion: `Agent returned error: [Agent reached maximum tool iterations (3) without a final answer...]`
- All other tiers/providers at checks 1–7: pass

### Routing tasks incompatible with degraded models

| Task type | `requires_tools` conflict | `tool_loop_reliable=false` conflict |
|-----------|--------------------------|--------------------------------------|
| `summary.*` | yes — summary calls use no tools | no |
| `agent.loop.*` | no — agents always supply tools | yes — agent loop depends on a concluding response |

### Deferred until

Not scheduled. Address when routing a non-Anthropic provider to a production task type, or when adding provider fallback logic in Config Control Phase 6.

---

## Key Design Docs

| Document | Purpose |
|----------|---------|
| `docs/superpowers/plans/claudeTaskArch.md` | Capability tiers, per-agent env vars, provider abstraction design |
| `docs/superpowers/plans/2026-05-07-model-routing-impl.md` | Phased implementation plan — task checklists for Phases 1–4 |
| `docs/superpowers/plans/2026-05-08-config-phase5-provider-model-table.md` | Phase 5 design — 4-provider model table, Gemini wiring |
| `neurodb_models.toml` | Live config — tier/provider/task routing table and model IDs |

---

## Routing and Telemetry

### Capability Tiers

| Tier | Role | Task examples |
|------|------|---------------|
| `premium` | Deep scientific reasoning, synthesis under conflicting evidence | Hypothesis critique, final synthesis review |
| `standard` | Multi-step orchestration, domain-grounded judgment | SQL generation, tutor explanation, hypothesis drafting |
| `economy` | Extraction, format adherence, template-fill from provided input | Session summary, knowledge source summary, narrow search query |

### Telemetry Task Types

See the Telemetry task types table in `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` → Configuration Control Epoch section.
