# NeuroDb — Agent Core Epoch Plan

**Status:** Stable — BaseAgent and ModelClient abstraction complete through Config Control Phase 4; provider live-tool reliability gap identified
**Last updated:** 2026-05-20
**Epoch directory:** `src/neurodb/agents/`
**Architecture reference:** `docs/superpowers/specs/2026-05-07-epoch-architecture-design.md`

---

## Epoch Goal

Provide the shared conversation loop, tool dispatch, rollback, streaming, session persistence, and configuration injection that all specialized agents inherit. Adding a new agent means implementing three methods and nothing else.

**Active work:** Phase 4 context-mode manual verification; coordinate with Config Control on provider live-tool validation and provider-specific ModelClient capability boundaries.

---

## Phases

| Phase | Focus | Status | Tests | Sign-off | Test plan |
|-------|-------|--------|-------|----------|-----------|
| LT-1 | BaseAgent abstract class, NeuroDbAgent migration, auto-session, streaming | Complete | — | 2026-05-05 | — |
| Config P4 | ModelClient abstraction — BaseAgent decoupled from Anthropic SDK; provider-neutral via `ModelClient` interface | Complete | 389 + 7 manual | 2026-05-09 | `docs/testsPlans/manualTestPlan_config_phase4.md` |

Active test plan: none

---

## Open Backlog

| Item | Issue |
|------|-------|
| Provider live-tool validation | Manual Phase 4 testing showed the live Tutor agent path depends on provider/model tool-call behavior that mocks do not validate. Agent Core should require provider adapters to declare and test tool/streaming capabilities before a provider is routed to tool-using agents. |
| Provider-specific ModelClient boundaries | `OpenAIModelClient` currently covers OpenAI, Groq, Gemini, and DeepSeek because they expose OpenAI-compatible APIs, but live behavior can differ. Agent Core should keep the shared `ModelClient` contract while allowing Config Control to split provider-specific adapters/capabilities. |
| Per-turn `source_summary` event for UI Source Lens | Finding from contextual-mode T3 testing: the Tutor response was useful for learning, but citation/queue-state hallucination was heavy. Prompt rules are the immediate fix, but UI trust requires Agent Core to emit a structured per-turn `source_summary` event during or after each agent turn instead of forcing the frontend to parse raw `tool_result` JSON. Metadata should group sources by `local`, `local_memory`, `external`, and `general_model_knowledge`; include reference fields such as paper ID, DOI/URL, dataset `source:source_id`, study-note ID, claim ID, evidence-link ID, literature result source, and external dataset source ID; and label each item as `evidence`, `context`, `discovery`, or `reasoning`. Recommended LOE: start with a small classifier from existing tool trace (0.5-1 day), then expand to parsed references from known tool result shapes (2-4 days). Avoid strict sentence-level citation policing until source metadata is proven useful, because that path is higher complexity and more brittle. |
| Design Choice 2 (deferred) — capability-flag routing gate | 2026-05-20 live probe showed `openai/gpt-oss-120b` and `gemini-2.5-flash-lite` exhaust `max_tool_iterations` without concluding. Root cause: these models emit tool calls as terminal output rather than as a step toward a final answer. Proposed fix: TOML `tool_loop_reliable = false` flag read by `TaskRouter` to exclude such models from `agent.loop.*` tasks. Design and evidence in `docs/ConfigControl_EpochPlan.md` → Design Choice 2 section. |

---

## Key Decisions

| Date | Decision | Rationale |
|------|----------|-----------|
| 2026-05-05 | BaseAgent abstract class from day one | The three-method contract is small to define early and expensive to retrofit later |
| 2026-05-05 | Auto-start and auto-summarize replace explicit session ceremony | Retains cross-session memory value while eliminating user friction |
| 2026-05-08 | ModelClient interface replaces direct Anthropic SDK calls in BaseAgent | BaseAgent calls `self._model_client.create_message()` — provider-neutral; clients injected at construction; no `os.environ` inside agent class bodies. See `docs/superpowers/plans/2026-05-07-model-routing-impl.md`. |
| 2026-05-19 | Provider-neutral contract is necessary but not sufficient | Live calls showed Anthropic completes the full Tutor tool path, while OpenAI `gpt-5.4` fails through Chat Completions when tools are supplied. Agent Core must rely on provider capability validation, not mocked adapter tests alone, before routing tool-using agents to a provider. |
| 2026-05-20 | DeepSeek, Groq economy/standard, Gemini standard pass all 7 checks | After fixing probe `context_mode` and token budget: `deepseek-chat`, `deepseek-reasoner`, `llama-3.1-8b-instant`, `llama-3.3-70b-versatile`, and `gemini-2.5-flash` complete the full agent loop cleanly. All elevated to `"baseline"`. |
| 2026-05-20 | Groq premium and Gemini economy loop tools without concluding | `openai/gpt-oss-120b` and `gemini-2.5-flash-lite` exhaust `max_tool_iterations=3` without emitting a final answer in check 7 — models treat tool-calling as default output rather than using tools to reach a conclusion. A separate class of failure from schema/API errors; requires either routing exclusion or a stronger stop-and-synthesize directive in the system prompt. |
| 2026-05-20 | Groq premium (`openai/gpt-oss-120b`) generates no content without tools | Checks 1–3 (no tools) return empty responses; checks 4–7 require tool context. Must not be routed to tool-free tasks or summary calls. |

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
