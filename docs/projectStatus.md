# NeuroDb — Project Status

**Last updated:** 2026-05-09
**Active focus:** UI-1 FastAPI backend shell — 408 automated tests; app factory + 8 routes implemented, manual evals T1–T8 pending
**Next:** UI-1 manual evals (T1–T8 curl-based), then UI-2 or Config Control Phase 6
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | `src/neurodb/agents/` | Stable | Config Control Phases 1–4 signed off; Phase 6 may add fallback chain logic |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-030 |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); hypothesis review with structured tool-use output | Research run management, research question actions (LOG-037) |
| UI | `src/neurodb/ui/`, `src/neurodb/api/` | Streamlit MVP + UI-1 in progress — 408 automated tests; app factory + 8 routes done | UI-1 manual evals T1–T8 pending |
| Config Control | `src/neurodb/config/` | Phase 5B complete — 398 automated tests; Phase 4 signed off 2026-05-09 | Phase 6: constructor fallback chain, SystemWarning table, CLI surface |

---

## Model Tier Table

Quality-aligned provider model assignments. Update this table and `neurodb_models.toml` together when provider models change. `last_verified_at` dates are in the TOML.

| Tier | Anthropic | OpenAI | Gemini | Groq |
|---|---|---|---|---|
| **economy** | claude-haiku-4-5-20251001 | gpt-5.4-mini | gemini-2.5-flash-lite | llama-3.1-8b-instant |
| **standard** | claude-sonnet-4-6 | gpt-5.4 | gemini-2.5-flash | llama-3.3-70b-versatile |
| **premium** | claude-opus-4-7 | gpt-5.5 | gemini-2.5-pro | openai/gpt-oss-120b |

Default provider for all tiers is **anthropic**. Override per tier via `NEURODB_{ECONOMY|STANDARD|PREMIUM}_PROVIDER` env var.
Source of truth for model IDs: `neurodb_models.toml`.

---

## Open Issues

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity — deferred post-LT-3), LOG-006 (model visibility — deferred post-LT-3), LOG-013 (UI shell rearchitecture — deferred post-LT-3), LOG-030 (LT-3 header/title sizing), LOG-037 (research-question actions), LOG-040 (Config Phase 1 local DB no-results wait behavior), LOG-041 (session summary visibility). LOG-044 resolved in Phase 4 via submit_critique tool-use.

---

## Key References

| Document | Purpose |
|----------|---------|
| **Goals / Process** | |
| `NeuroDbGoals.md` | Top-level project goals and feedback loop |
| `CLAUDE.md` | Engineering rules, process, environment |
| **Active Issues** | |
| `docs/testLog.md` | Running issue log — open and resolved items across all phases |
| **Epoch Architecture + Status** | |
| `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md` | Epoch architecture spec — six epochs, interface contracts, coupling rules, goal-to-epoch mapping |
| `docs/AgentCore_EpochPlan.md` | Agent Core epoch plan — BaseAgent architecture, three-method contract, configuration injection |
| `docs/Tutor_EpochPlan.md` | Tutor epoch plan — NeuroTutorAgent, Knowledge Library, session management, open backlog |
| `docs/Research_EpochPlan.md` | Research epoch plan — NeuroResearchAgent, hypothesis tools, hypothesis review, open backlog |
| `docs/ConfigControl_EpochPlan.md` | Config Control epoch plan — routing phases, provider adapters, telemetry, Phase 6 next |
| `docs/DB_EpochPlan.md` | DB epoch plan — connectors, schema ownership, phases 0–8 |
| `docs/UI_EpochPlan.md` | UI epoch plan — Streamlit MVP, FastAPI/React migration path, phases UI-0–4 |
| **Active Plans / Specs** | |
| `docs/superpowers/plans/2026-05-08-ui1-backend-api-shell.md` | UI-1 implementation plan — FastAPI app factory, 8 routes, SSE chat PoC |
| `docs/testsPlans/manualTestPlan_ui1_api_shell.md` | UI-1 manual test plan — 8 curl-based evals T1–T8 (ready to run) |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
