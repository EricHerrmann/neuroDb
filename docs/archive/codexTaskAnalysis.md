# NeuroDb: Codex Task-Based Cost and Model Routing Analysis

**Date:** 2026-05-07
**Status:** Design analysis only — no implementation
**Related analysis:** `docs/claudeTaskAnalysis.md`

This report consolidates the earlier Codex cost and task analyses into one design note. It evaluates task-based model routing, the limits of Claude Pro/ChatGPT Pro substitution, and a future architecture for adding model providers such as Anthropic, OpenAI, and Gemini without hardcoding rapidly changing model generations into the application.

## Executive Summary

The core conclusion is that NeuroDb should route model spend by task complexity, not by agent identity.

The Research agent is not a homogeneous Opus-class workload. Most of the loop is:

- tool selection,
- SQL/query formulation,
- search-query formulation,
- JSON/tool-result interpretation,
- relevance judgment,
- structured persistence.

Those tasks should generally run on a standard-tier model. Premium models should be reserved for bounded scientific synthesis, hypothesis critique, and difficult reasoning over compact evidence bundles.

However, there is an important code-level constraint: in the current implementation, `draft_hypothesis` is a persistence tool, not a synthesis tool. The loop model has already generated the hypothesis fields before the tool is called. So "use Sonnet for the loop and Opus only inside `draft_hypothesis`" is conceptually right but not a literal implementation path. A premium synthesis/review step needs to be designed explicitly.

My recommendation:

1. MVP cost fix: keep Anthropic as the only provider, but stop using Opus as the universal default.
2. Use per-agent/per-purpose model settings first: standard model for chat loops, economy model for summaries, premium model only for explicit review.
3. Plan Path B as a provider-agnostic architecture: task routing, provider adapters, and config-driven model tables.
4. Treat dynamic "latest model" selection as a later feature. Design for it now, but do not make it an MVP dependency.

## Routing Decision Model

NeuroDb should treat each model call as a routed work unit, not as "the Research agent uses model X" or "the Tutor agent uses model Y." A single user-facing turn may contain several model calls, and each call can have a different task type, token profile, quality requirement, and model fit.

Summary principle:

```text
Use the cheapest model that reliably passes the quality bar for the task.
Escalate only when the task needs deeper reasoning, better scientific judgment,
or recovery from failure.
```

| Dimension | Meaning | Why it matters |
|-----------|---------|----------------|
| `task_type` | The kind of work the model is doing: SQL generation, search query formulation, tool orchestration, summary, hypothesis synthesis, critique, etc. | Model capability should match the task, not the broad agent mode. |
| `turns / iterations` | How many model calls are needed to complete one user-facing task. | Multi-step loops multiply cost because each iteration is a billable request. |
| `tokens` | Input tokens plus output tokens per call. | Long history, tool schemas, prior context, and tool results increase input cost; drafting increases output cost. |
| `model` | The concrete provider/model used for the call. | Models differ in cost, latency, tool reliability, reasoning depth, and output quality. |
| `model_fit` | How appropriate the selected model is for the task type. | Fit should be judged by measured quality and cost, not by assumed prestige. |
| `risk` | Consequence of a bad answer or weak reasoning. | Higher-risk scientific claims justify stronger review. |
| `context_size` | Amount of local evidence, prior context, and conversation history included. | Large context can make even cheap models expensive; compaction matters. |
| `quality_outcome` | Whether the result passed task-specific eval criteria. | Routing should improve over time from observed pass/fail behavior. |

Decision function:

```text
task_type + risk + context_size + expected_iterations
    -> capability_tier
    -> provider/model
    -> max_tokens / budget
    -> eval + telemetry feedback
```

| Task type | Cost driver | Quality requirement | Default fit | Escalation trigger |
|-----------|-------------|---------------------|-------------|--------------------|
| Session summary | One short call | Format adherence, correct date/topic, no invented datasets | Economy | Summary quality becomes research-grade or misses key context |
| Knowledge source summary | One short call | Structured summary, no invented DOI/source claims | Economy or local template | Canonical source needs higher-quality synthesis |
| SQL generation | Short calls, possible retries | Precision against fixed schema | Standard; deterministic for common patterns | Repeated invalid SQL or complex schema reasoning |
| Search query formulation | Short calls | Good term selection, API-aware query shape | Economy for narrow terms; standard for broad topics | Broad, ambiguous, or multi-concept search strategy |
| Tool orchestration | Many iterations | State tracking, tool discipline, no fabrication | Standard | Repeated loop failures or high ambiguity |
| Tool-result interpretation | Medium, repeated | Correctly read JSON and decide next step | Standard | Conflicting or sparse evidence |
| Relevance judgment | Medium | Domain vocabulary and grounding to local evidence | Standard | Sparse evidence, high-value decision, or conflicting candidates |
| Research question extraction | Short/medium | Concise question, valid context/status | Economy or standard | Long conversation extraction or ambiguous scope |
| Draft hypothesis | Medium/high output | Evidence, predictions, datasets, confounds, limitations, draft-only status | Standard first | High-value artifact or weak/conflicting evidence |
| Final critique / premium review | One bounded call | Deep reasoning, epistemic calibration, unsupported-claim detection | Premium | Always premium when explicitly requested |

Telemetry should make model routing empirical:

| Logged field | Question it answers |
|--------------|---------------------|
| `task_type` | What kind of work consumed the call? |
| `provider` / `model` | Which model handled it? |
| `mode` | Which user-facing agent mode triggered it? |
| `iteration_count` | Did one user request expand into many model calls? |
| `input_tokens` | How much context/tool/history cost was sent? |
| `output_tokens` | How much generation cost was produced? |
| `stop_reason` | Did the model finish, hit token limits, or continue tool use? |
| `estimated_cost` | What did the call likely cost? |
| `quality_outcome` | Did the model pass task-specific criteria? |

The feedback loop should be:

```text
task routing hypothesis
  -> run model
  -> measure turns, tokens, model, task_type, cost, quality
  -> promote, demote, or constrain the model for that task type
```

The strategic problem today is that "Research mode" bundles many task types into one loop and one model. The target architecture separates them so cheap tasks and premium tasks are not billed at the same model tier.

## Why Pro Accounts Are Not a Substitute

Claude Pro and ChatGPT Pro are useful for side review, brainstorming, and manual second opinions. They are not an adequate substitute for NeuroDb's integrated RAG/context workflow.

NeuroDb's value is the loop around local state:

- DuckDB structured records,
- Chroma semantic retrieval,
- prior session summaries,
- Knowledge Library summaries,
- study notes and concept tags,
- research questions,
- draft hypotheses,
- tool-mediated persistence back into the app.

Using standalone Claude or ChatGPT loses automatic retrieval, provenance, persisted artifacts, repeatability, and tool-mediated grounding. Consumer chat subscriptions are also separate from API billing. They can supplement the workflow, but the app still needs API-backed or local model infrastructure for integrated RAG.

## Current Anthropic API Usage

`ANTHROPIC_API_KEY` is used in three cost-producing runtime paths, with four direct model-call sites.

| File | Function | When called | Current model behavior | Tokens |
|------|----------|-------------|------------------------|--------|
| `src/neurodb/agents/base.py` | `_chat_inner()` | Every non-streaming agent tool iteration | `NEURODB_MODEL`, default `claude-opus-4-7` | Agent `max_tokens` per call |
| `src/neurodb/agents/base.py` | `_chat_stream_inner()` | Every streaming agent tool iteration | `NEURODB_MODEL`, default `claude-opus-4-7` | Agent `max_tokens` per call |
| `src/neurodb/session_manager.py` | `_generate_summary()` | Once when a session is summarized on Clear after enough turns | `NEURODB_MODEL`, default `claude-opus-4-7` | 512 |
| `src/neurodb/ui/pages/knowledge_library.py` | `_generate_summary()` | Once when a Knowledge Library source is approved and an API key exists | `NEURODB_MODEL`, default `claude-opus-4-7` | 700 |

Client construction occurs in `src/neurodb/ui/pages/chat.py` and `src/neurodb/ui/app.py`, but creating `anthropic.Anthropic(...)` is not billable. Cost starts when one of the model calls above runs.

## Why Research Mode Raised Cost

Research mode registers more tools and encourages multi-step grounded work:

- `search_knowledge_library`
- `search_literature`
- `cross_reference_datasets`
- `get_knowledge_growth_metrics`
- `record_research_question`
- `draft_hypothesis`
- read-only DB tools: `query_db`, `semantic_search`, `get_study_notes`

The shared loop works as:

1. Send user prompt, system prompt, current conversation, and tool schemas.
2. Model requests a tool.
3. App executes local code.
4. App sends tool result back to the model.
5. Repeat until final response, terminal tool result, max-token stop, or iteration budget.

Each loop step is a billable model request. Long chat history and prior context are resent, so later turns become more expensive. Recent LT-3 remediation reduced one wasteful pattern by ending after successful hypothesis persistence instead of always making another final-response model call.

## Task Taxonomy

The task-level view is the right lens. Agent sessions contain mixed-complexity tasks.

| Task | Description | Capability needed | Recommended tier |
|------|-------------|-------------------|------------------|
| SQL generation | Translate natural language to `SELECT` against fixed schema | Precision and format accuracy | Standard; deterministic for common patterns |
| Search query formulation | Translate topic to PubMed/Semantic Scholar query | Structured reasoning and term selection | Economy for narrow topics; standard for broad topics |
| Tool-result interpretation | Read JSON output and decide the next call | Multi-step orchestration and grounding | Standard |
| Relevance judgment | Decide if dataset/source is relevant to topic | Domain vocabulary and bounded judgment | Standard |
| Structured record writing | Populate research question, study note, summary, or status fields | Extraction and format adherence | Economy or standard |
| Scientific synthesis | Combine evidence into a testable claim with confounds and limitations | Deep reasoning and epistemic calibration | Standard draft, premium review |
| Pedagogical explanation | Explain neuroscience concepts clearly | Clarity and accuracy | Standard |
| Template-fill summarization | Fill fixed fields from existing text | Extraction and format adherence | Economy |

## Corrected Model Assignment

| Task | Default | Escalation | Notes |
|------|---------|------------|-------|
| Common local DB queries | Deterministic code | Standard model | Avoid model calls for known count/list/filter patterns where possible |
| Open-ended SQL generation | Standard | Premium only after repeated failure | Schema-grounded precision task |
| PubMed/Semantic Scholar query generation | Economy or standard | Standard for broad research topics | Search APIs perform retrieval |
| Tool orchestration | Standard | Premium only for repeated loop failures | Most loop calls should not use premium models |
| JSON/tool-result interpretation | Standard | Premium rarely | Needs discipline, not creativity |
| Relevance judgment | Standard | Premium for sparse/conflicting evidence | Bounded domain judgment |
| Research question extraction | Economy or standard | Standard for long conversation extraction | Mostly structured persistence |
| Session summary | Economy | Standard if summaries become research-grade memory artifacts | Current prompt is constrained |
| Knowledge Library summary | Economy or local template | Standard for canonical sources | Avoid premium by default |
| Tutor explanation | Standard | Premium for difficult conceptual synthesis | Teaching quality matters, but most turns are not premium |
| Draft hypothesis fields | Standard | Premium critique/revision for high-value artifacts | Standard model can draft from compact evidence |
| Final hypothesis critique | Premium | None | Best use of premium spend |

## Current Code Constraint: `draft_hypothesis`

The current `draft_hypothesis` tool is not a synthesis boundary.

Current flow:

1. The loop model receives evidence and tool schemas.
2. The loop model decides to call `draft_hypothesis`.
3. The loop model fills `title`, `mechanism`, `evidence`, `predictions`, `datasets`, `confounds`, and `limitations`.
4. The app persists those fields.

Therefore, changing the model inside `_execute_tool_block()` is too late if the goal is to have Opus create the hypothesis. A model call there could critique or rewrite the tool input, but the architecture would need to explicitly replace or review the draft before persistence.

Better Path B designs:

1. **New synthesis tool:** Standard loop retrieves evidence, then calls a premium synthesis tool over a compact evidence bundle. The premium tool returns structured fields that are validated and persisted.
2. **Two-step draft/review:** Standard model drafts and persists as `needs_review`; user triggers a premium review/revision action.
3. **Pre-persistence review:** Standard model proposes a draft; premium model critiques/revises it; revised draft is persisted.

The two-step draft/review design is the safest MVP extension because it keeps the expensive premium call explicit and bounded.

## Path A vs. Path B

### Path A: Per-agent and per-purpose model settings

MVP Anthropic-only approach:

```text
NEURODB_AGENT_MODEL=<standard model>
NEURODB_RESEARCH_MODEL=<standard model>
NEURODB_SUMMARY_MODEL=<economy model>
NEURODB_KNOWLEDGE_SUMMARY_MODEL=<economy model>
NEURODB_PREMIUM_MODEL=<premium model>
```

Pros:

- Fastest cost reduction.
- No provider abstraction required.
- Low implementation risk.
- Keeps NeuroDb's integrated RAG loop intact.
- Lets Anthropic remain the MVP provider.

Cons:

- Still couples the app to Anthropic model names.
- Does not solve rapid generation churn.
- Does not enable OpenAI/Gemini routing.
- If Research loop remains premium, cost remains high.
- If Research loop becomes standard, hypothesis quality depends on adding a premium review path.

Verdict: use this as the MVP cost-control step.

### Path B: Per-task model switching with provider-agnostic architecture

Target direction:

- Standard model handles loop orchestration.
- Economy model handles summaries/extraction.
- Premium model handles explicit scientific synthesis or critique.
- Provider abstraction supports Anthropic first, then OpenAI/Gemini later.
- Model IDs come from config, not hardcoded defaults.

Pros:

- Aligns cost with task complexity.
- Future-proofs the app against model generation churn.
- Allows provider competition on cost/quality.
- Enables OpenAI or Gemini where they are more cost-effective.
- Keeps premium spend focused on compact, high-value evidence bundles.

Cons:

- More architectural work.
- Requires provider-specific adapters for messages, streaming, tool calls, and tool results.
- Requires evals because task quality varies by provider and model generation.
- Requires telemetry to validate savings and failure rates.
- Dynamic latest-model selection can introduce instability if not pinned/evaluated.

Verdict: design for Path B now, but implement it in phases after the Anthropic MVP routing is stable.

## Multi-Provider Architecture Considerations

The architecture should not permanently assume Anthropic. The `.env` already has multiple provider keys available, and model generations change quickly. The design should separate:

- task type,
- capability tier,
- provider,
- current model ID,
- fallback policy,
- eval status.

### Provider abstraction

Introduce a provider-neutral interface later:

```text
ModelClient
  create_message(request) -> ModelResponse
  stream_message(request) -> ModelStream
  normalize_tool_schema(tool) -> provider_tool
  normalize_tool_result(result) -> provider_message
```

Provider implementations:

- `AnthropicModelClient`
- `OpenAIModelClient`
- `GeminiModelClient`

The `BaseAgent` loop should eventually depend on `ModelClient`, not directly on Anthropic's SDK message schema.

### Task router

A future `TaskRouter` should map:

```text
task_type -> capability_tier -> provider -> model_id
```

Example task types:

- `agent.loop.local_db`
- `agent.loop.research`
- `summary.session`
- `summary.knowledge_source`
- `research.hypothesis_draft`
- `research.hypothesis_review`
- `tutor.explanation`
- `search.query_formulation`

## Config-Driven Model Table

Model generations change too quickly to hardcode "Sonnet 4.6", "Opus 4.7", or "Haiku 4.5" throughout the code. The architecture should use stable task/tier names and keep provider/model IDs in a config file.

Example config shape:

```toml
[tiers.economy]
description = "Structured extraction, summaries, template-fill tasks"
default_provider = "anthropic"

[tiers.economy.providers.anthropic]
model = "claude-haiku-4-5"
eval_status = "candidate"

[tiers.economy.providers.openai]
model = "gpt-5-mini"
eval_status = "candidate"

[tiers.standard]
description = "RAG loop orchestration, relevance judgment, tutor explanations"
default_provider = "anthropic"

[tiers.standard.providers.anthropic]
model = "claude-sonnet-4-6"
eval_status = "baseline"

[tiers.standard.providers.openai]
model = "gpt-5"
eval_status = "candidate"

[tiers.premium]
description = "Scientific synthesis, final critique, difficult reasoning"
default_provider = "anthropic"

[tiers.premium.providers.anthropic]
model = "claude-opus-4-7"
eval_status = "baseline"

[tiers.premium.providers.openai]
model = "gpt-5.2"
eval_status = "candidate"

[tasks.summary.session]
tier = "economy"
max_tokens = 512

[tasks.agent.loop.research]
tier = "standard"
max_tokens = 2048

[tasks.research.hypothesis_review]
tier = "premium"
max_tokens = 4096
```

Important fields for later:

- `provider`
- `model`
- `tier`
- `task_type`
- `max_tokens`
- `temperature`
- `tool_support`
- `streaming_support`
- `structured_output_support`
- `eval_status`
- `last_verified_at`
- `fallback_provider`
- `fallback_model`

## Latest-Generation Model Selection

Automatic "latest model" selection should not be an MVP feature. It is useful, but it can create instability.

Recommended design:

1. Use pinned model IDs for production-like workflows.
2. Track capability tiers in config.
3. Add a later utility that checks provider docs or APIs for newer model generations.
4. Mark new models as `candidate`, not `baseline`.
5. Run task evals before promoting a candidate to default.

The app should make it easy to update from one generation to another, but it should not silently switch models just because a provider released a new one.

## MVP vs. Planned Features

| Feature | MVP | Later design |
|---------|-----|--------------|
| Anthropic-only model routing | Yes | Remains supported |
| Per-agent/per-purpose env vars | Yes | Replaced or backed by config |
| Sonnet/default standard loop | Yes | Config-driven standard tier |
| Haiku/economy summaries | Yes | Config-driven economy tier |
| Explicit premium Opus review | Useful MVP extension | Config-driven premium tier |
| Provider abstraction | No | Yes |
| OpenAI/Gemini providers | No | Yes |
| Config model table | Design now, implement later | Yes |
| Latest-generation discovery | No | Candidate update utility |
| Automated model promotion | No | Only after evals |

## Evaluation Requirements

Before switching defaults or adding providers, NeuroDb needs small task evals:

| Eval | Candidate tier/provider | Pass criteria |
|------|-------------------------|---------------|
| Local DB query | standard, deterministic | Correct SQL/tool call, correct result, no fabricated IDs |
| External discovery | standard | Valid source calls, grounded candidates, no fabricated sources |
| Tutor explanation | standard | Clear explanation, uses Knowledge Library where relevant |
| Session summary | economy | Correct date/topic/concepts, no invented datasets |
| Knowledge summary | economy | Useful summary, no invented DOI/source claims |
| Research question recording | economy/standard | Concise persisted question and topic context |
| Dataset cross-reference | standard | Local evidence used, limitations surfaced |
| Draft hypothesis | standard | Evidence, predictions, datasets, confounds, limitations, draft-only status |
| Premium critique | premium | Identifies unsupported claims, weak evidence, missing confounds |

Telemetry should accompany evals:

- model used,
- provider,
- task type,
- mode,
- tool name,
- iteration count,
- input tokens,
- output tokens,
- stop reason,
- elapsed time,
- estimated cost.

Without telemetry, savings estimates such as "35 of 40 iterations are standard-tier" remain plausible but unmeasured.

## Design Pros and Cons

### Anthropic MVP first

Pros:

- Lower risk.
- Preserves current working behavior.
- Fastest route to reducing Opus usage.
- Avoids multi-provider schema complexity during cost stabilization.

Cons:

- Still tied to Anthropic pricing and model lifecycle.
- Does not exploit potentially cheaper OpenAI/Gemini task fits.
- Requires later refactor for provider abstraction.

### Provider-agnostic Path B

Pros:

- Best long-term architecture.
- Lets the app route by task, not provider loyalty.
- Supports rapid model generation changes through config.
- Allows comparison and fallback across Anthropic/OpenAI/Gemini.

Cons:

- Higher design and testing cost.
- Tool-call semantics differ across providers.
- Streaming behavior differs across providers.
- Requires task evals before each provider/model promotion.
- Latest-model automation can destabilize workflows if not gated.

## Final Recommendation

Use Anthropic as the MVP provider for Path B, but do not design the architecture as Anthropic-only.

The near-term move is:

1. Keep all provider changes out of the immediate MVP.
2. Add model routing within Anthropic: economy summaries, standard loops, premium review.
3. Add telemetry and task evals.
4. Design the future config table and provider abstraction now so OpenAI/Gemini can be added later without rewriting the agent logic.

The long-term goal should be:

```text
task -> tier -> provider/model config -> provider adapter -> normalized response
```

That gives NeuroDb a stable architecture even as model names and generations change.

## References

- `docs/claudeTaskAnalysis.md`
- `src/neurodb/agents/base.py`
- `src/neurodb/agents/research_agent.py`
- `src/neurodb/session_manager.py`
- `src/neurodb/ui/pages/knowledge_library.py`
- Anthropic model overview: https://platform.claude.com/docs/en/about-claude/models/overview
- Anthropic pricing: https://platform.claude.com/docs/en/about-claude/pricing
- OpenAI model overview: https://developers.openai.com/api/docs/models
- OpenAI pricing: https://developers.openai.com/api/docs/pricing
