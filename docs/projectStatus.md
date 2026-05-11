# NeuroDb — Project Status

**Last updated:** 2026-05-11
**Active focus:** UI-2 — React workbench migration; Tasks 1–2 of 19 complete (study-log + sessions routes)
**Next:** UI-2 Tasks 3–19 (backend routes 3–8, then full React frontend)
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | `src/neurodb/agents/` | Stable | Config Control Phases 1–4 signed off; Phase 6 may add fallback chain logic |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-030 |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); hypothesis review with structured tool-use output | Research run management, research question actions (LOG-037) |
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-2 in progress — Tasks 1–2 complete (study-log, sessions routes); Tasks 3–19 remaining | Tasks 3–8: backend routes; Tasks 9–19: React frontend |
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

See `docs/testLog.md`. Current open items: LOG-001 (textbook dropdown ambiguity), LOG-006 (model visibility), LOG-013 (UI shell rearchitecture), LOG-030 (header/title sizing), LOG-037 (research-question actions), LOG-041 (session summary visibility), LOG-045 (research-to-knowledge-library bridge), LOG-047 (telemetry timestamp format), LOG-048 (dismiss draft hypothesis), LOG-050 (Gemini premium testing deferred).

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
| `docs/superpowers/specs/2026-05-11-ui2-react-workbench-design.md` | UI-2 design spec — Vite + React + React Router v7 + TanStack Query v5; two-column layout; 7 panels; data flow; testing strategy |
| `docs/superpowers/plans/2026-05-11-ui2-react-workbench.md` | UI-2 implementation plan — 19 tasks; Progress table and Patterns Established section at top; Tasks 1–2 complete |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
