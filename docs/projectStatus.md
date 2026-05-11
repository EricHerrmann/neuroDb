# NeuroDb — Project Status

**Last updated:** 2026-05-11
**Active focus:** UI-2B signed off; next focus pending selection
**Next:** Choose next UI hardening task, UI-3 parity migration, or another epoch priority
**Goal alignment:** Two co-equal goals in a feedback loop — accumulate neuroscience understanding grounded in real data (Goal 1), and conduct structured neuroscience investigations using existing public datasets and good scientific method (Goal 2). See `NeuroDbGoals.md`.

---

## Epoch Status

| Epoch | Source | Maturity | Next |
|---|---|---|---|
| DB | `src/neurodb/db/`, `src/neurodb/connectors/` | MVP complete (phases 0–6) | Entity resolution (7), research storage schema (8) |
| Agent Core | `src/neurodb/agents/` | Stable | Config Control Phases 1–4 signed off; Phase 6 may add fallback chain logic |
| Tutor | `src/neurodb/tutor/` | MVP complete (LT-1/2/3) | Open backlog: LOG-001, LOG-006, LOG-030 |
| Research | `src/neurodb/research/` | Scaffolded (LT-3); hypothesis review with structured tool-use output | Research run management, research question actions (LOG-037) |
| UI | `src/neurodb/ui/`, `src/neurodb/api/`, `frontend/` | UI-2B signed off 2026-05-11 — activity rail, resizable panes, agent mode in chat header | UI-3 parity migration (Streamlit surfaces → React) |
| Config Control | `src/neurodb/config/` | Phase 5B complete — 398 automated tests; Phase 4 signed off 2026-05-09 | Phase 6: constructor fallback chain, SystemWarning table, CLI surface |

---

## Model Tier Table

Quality-aligned provider model assignments. Update this table and `neurodb_models.toml` together when provider models change. `last_verified_at` dates are in the TOML.

| Tier | Anthropic | OpenAI | Gemini | Groq | DeepSeek |
|---|---|---|---|---|---|
| **economy** | claude-haiku-4-5-20251001 | gpt-5.4-mini | gemini-2.5-flash-lite | llama-3.1-8b-instant | deepseek-chat |
| **standard** | claude-sonnet-4-6 | gpt-5.4 | gemini-2.5-flash | llama-3.3-70b-versatile | deepseek-chat |
| **premium** | claude-opus-4-7 | gpt-5.5 | gemini-2.5-pro | openai/gpt-oss-120b | deepseek-reasoner |

Default provider for all tiers is **anthropic**. Override per tier via `[routing]` section in `neurodb_models.toml`.
DeepSeek is wired (economy: `deepseek-chat`, standard: `deepseek-chat`, premium: `deepseek-reasoner`); `eval_status = "unverified"` — not yet validated.
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
| `docs/superpowers/specs/2026-05-11-ui2b-layout-redesign.md` | UI-2B design spec — activity rail, react-resizable-panels, collapsible right panel, agent mode in chat header |
| `docs/superpowers/plans/2026-05-11-ui2-react-workbench.md` | UI-2 implementation plan — 19 tasks complete; signed off 2026-05-11 |
| `docs/testsPlans/completedAndPassedTestPlans/manualTestPlan_ui2_react_workbench.md` | UI-2 manual test plan — 11 evals passed; signed off 2026-05-11 |
| **History** | |
| `docs/archive/completedPhases.md` | Completed phases and tech debt sprints — full history |
