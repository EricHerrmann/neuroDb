# NeuroDb — Agent Core Epoch Plan

**Status:** Stable — BaseAgent and ModelClient abstraction complete through Config Control Phase 4
**Last updated:** 2026-05-09
**Epoch directory:** `src/neurodb/agents/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Provide the shared conversation loop, tool dispatch, rollback, streaming, session persistence, and configuration injection that all specialized agents inherit. Adding a new agent means implementing three methods and nothing else.

**Active work:** None — stable. Config Control Phase 6 may add constructor fallback chain logic here.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-1 | BaseAgent abstract class, NeuroDbAgent migration, auto-session, streaming | Complete | — | 2026-05-05 | — |
| Config P4 | ModelClient abstraction — BaseAgent decoupled from Anthropic SDK; provider-neutral via `ModelClient` interface | Complete | 389 + 7 manual | 2026-05-09 | `docs/testsPlans/manualTestPlan_config_phase4.md` |

Active test plan: none

---

## Open Backlog

No open LOG entries currently assigned to Agent Core epoch.

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | BaseAgent abstract class from day one | The three-method contract is small to define early and expensive to retrofit later |
| 2026-05-05 | Auto-start and auto-summarize replace explicit session ceremony | Retains cross-session memory value while eliminating user friction |
| 2026-05-08 | ModelClient interface replaces direct Anthropic SDK calls in BaseAgent | BaseAgent calls `self._model_client.create_message()` — provider-neutral; clients injected at construction; no `os.environ` inside agent class bodies. See `docs/superpowers/plans/2026-05-07-model-routing-impl.md`. |

---

## Agent Classes + BaseAgent Contract

### Concrete agent classes

| Module | Class | Mode |
|--------|-------|------|
| `src/neurodb/agents/base.py` | `BaseAgent` | Abstract base |
| `src/neurodb/agents/db_agent.py` | `NeuroDbAgent` | `local_db`, `external_db` |
| `src/neurodb/agents/tutor_agent.py` | `NeuroTutorAgent` | `neuro_tutor` |
| `src/neurodb/agents/research_agent.py` | `NeuroResearchAgent` | `neuro_research` |

### Three-method contract (all subclasses implement)

| Method | Purpose |
|--------|---------|
| `_get_active_tools()` | Returns the tool list for this agent |
| `_build_system_prompt()` | Returns the system prompt for this agent |
| `_execute_tool_block(block)` | Dispatches a tool call and returns a result string |

The conversation loop (`chat()`, `chat_stream()`), checkpoint/rollback logic, and streaming protocol are implemented once in `BaseAgent` — never in subclasses.

### Configuration injection rule

No agent reads env vars or config files internally. Configuration enters through the constructor only. Pre-Phase 4: env vars read at the call site, passed in. Post-Phase 4: `TaskRouter.route(task_type)` returns `(ModelClient, model_id, max_tokens)`, passed to the constructor.
