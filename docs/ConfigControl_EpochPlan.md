# NeuroDb — Config Control Epoch Plan

**Status:** Phase 5B complete — 398 automated tests; Phase 4 signed off 2026-05-09
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/config/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Own model and provider selection, capability tier routing, provider adapters, API key management, cost and capability gating, and telemetry-informed routing. Keep the cost envelope stable as the feedback loop matures — more capable, not more expensive.

**Active work:** Phase 4 signed off. Phase 6 (constructor fallback chain, SystemWarning table, CLI telemetry surface) is next.

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

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-07 | Env vars for model selection (Phase 1); TOML for provider routing (Phase 4+) | Env vars sufficient for model name overrides; TOML gives tier × provider × model IDs, version tracking, and eval status in one file |
| 2026-05-08 | `ModelClient` abstract interface wraps all providers | BaseAgent becomes provider-neutral; adding a provider means implementing `ModelClient`, not modifying BaseAgent |
| 2026-05-08 | `GOOGLE_API_KEY` is the env var for Gemini | Google issues a single API key for Gemini; `GEMINI_API_KEY` was an internal naming error |
| 2026-05-09 | `stream_options={"include_usage": True}` required for OpenAI/Gemini streaming token counts | Without it the OpenAI streaming API does not emit a usage chunk; token counts are null in telemetry |

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
