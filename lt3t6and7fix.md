# LT-3 T6/T7 Fix Analysis

**Date:** 2026-05-06
**Tests blocked:** T6 (draft hypothesis), T7 (no study-note mutation)
**Reproduced with live API:** Yes — see reproduction log below

---

## Reproduction

Script: `reproduce_lt3_t6.py`
Prompt: T6 test prompt (draft hypothesis linking hippocampal synaptic plasticity to
learning-related dataset measures)
Config: `NEURODB_RESEARCH_MAX_TOOL_ITERATIONS=40`, `max_tokens=2048` (current hardcoded
value in `base.py`)

### Output

```
iter 01: stop_reason=tool_use   content=['text', 'tool_use', 'tool_use', 'tool_use']  out_tokens=337
iter 02: stop_reason=tool_use   content=['text', 'tool_use', 'tool_use', 'tool_use']  out_tokens=298
iter 03: stop_reason=tool_use   content=['tool_use', 'tool_use']                      out_tokens=127
iter 04: stop_reason=tool_use   content=['tool_use', 'tool_use', 'tool_use']          out_tokens=231
iter 05: stop_reason=tool_use   content=['text', 'tool_use', 'tool_use', 'tool_use']  out_tokens=305
iter 06: stop_reason=tool_use   content=['text', 'tool_use']                          out_tokens=403
iter 07: stop_reason=max_tokens content=['tool_use']                                  out_tokens=2048

total iterations: 7
max_tokens stops: 1
messages in API history after turn: 2
```

---

## Root Cause

### Bug 1 (primary, confirmed): `max_tokens=2048` truncates `draft_hypothesis` mid-generation

The research agent's API calls use `max_tokens=2048` (hardcoded in `base.py:65` and
`base.py:142`). At iteration 7, the model begins generating the `draft_hypothesis` tool
call. That call requires a large JSON body: mechanism, evidence (list of dicts),
predictions (list), datasets (list of dicts), confounds (list), and limitations. With
the reasoning text that precedes the JSON in the same response, the output exceeds 2048
tokens. The response is cut off mid-generation at exactly 2048 tokens.

`stop_reason` is `max_tokens`, not `tool_use`. The loop's `if/if/break` structure in
`_chat_stream_inner` (`base.py:160–220`) treats any stop_reason other than `end_turn`
or `tool_use` as a silent `break`. That break falls through to
`_handle_iteration_budget_exhausted`, which emits:

```
[Agent reached maximum tool iterations (40) without a final answer. ...]
```

The message is wrong on two counts:
1. Only 7 iterations ran, not 40.
2. The cause was a token limit, not an iteration limit.

The truncated tool_use block is appended to messages and then deleted by
`_handle_iteration_budget_exhausted(del messages[checkpoint:])`, so the API history
ends up clean. But the hypothesis is never written.

### Bug 2 (secondary, masking): misleading error message on `max_tokens` break

The `break` path yields "max tool iterations (40)" regardless of actual stop reason. A
`max_tokens` stop is architecturally distinct from exhausting the iteration budget. The
user (and any diagnostic tooling) cannot distinguish the two from the error text alone.

### Codex's terminal-tool hook does not address either bug

`_build_terminal_tool_response` in `research_agent.py:237` fires after a successful
`draft_hypothesis` execution. The tool is never executed when `max_tokens` truncates the
response at iter 7. The hook never has a chance to fire. The fix is logically correct
for the case where `draft_hypothesis` runs but the model then asks for another LLM turn;
it does not address the token-budget truncation that prevents the tool from running at
all.

---

## What the User Observes

In Streamlit the activity log shows "Step N/40" only for tool_start events, which are
emitted only when `stop_reason == "tool_use"`. When `max_tokens` fires, the tools in the
truncated response are never executed, so no tool_start event is emitted. The user sees
activity through step 6/40, then a pause (the streaming model call at iter 7 produces
only text fragments — no tool events), then the error message. This matches "no action
visible at step 7/40" and "hands off to LLM then returns with max turns exceeded."

---

## Solutions

### Solution A — Increase `max_tokens` to 4096 (recommended first)

**Files:** `base.py:65` and `base.py:142` (the two `messages.create` / `messages.stream`
call sites, both have `max_tokens=2048`).

**Change:** Set `max_tokens=4096`. The research agent's prompt responses include
multi-paragraph reasoning text plus tool-call JSON. For `draft_hypothesis` specifically,
the JSON body (mechanism, evidence list, predictions list, datasets list, confounds list,
limitations) plus preceding analysis easily reaches 2000–3000 tokens. 4096 gives
sufficient headroom. Going to 8192 is safe but increases per-call cost.

**Risk:** Modestly higher API cost per call (billed on output tokens used, not max).
No logic changes. No new failure modes introduced.

**Why this is the direct fix:** The reproduction confirms `out_tokens=2048` at the
failing iteration — the model is literally at the ceiling. Raising the ceiling removes
the constraint that causes the truncation.

**Note on the base class approach:** Both `chat` (non-streaming) and `chat_stream`
(streaming) have their own `max_tokens=2048`. Both need to be updated. Alternatively,
expose `max_tokens` as a constructor parameter so subclasses like `NeuroResearchAgent`
can set higher values without changing the base default.

---

### Solution B — Handle `max_tokens` explicitly instead of silently breaking (recommended second)

**Files:** `base.py:_chat_stream_inner` (around line 220) and `base.py:_chat_inner`
(around line 111).

**Change:** Add a branch for `stop_reason == "max_tokens"` before the `break`:

```python
if final_message.stop_reason == "max_tokens":
    # Clean up exactly like the iteration-budget handler
    # but emit a response-specific error
    yield {
        "type": "error",
        "text": (
            "[Response truncated: the model's output reached the token limit "
            "before completing the tool call. The partial turn was not saved. "
            "Try a narrower request or ask the agent to draft from currently "
            "gathered evidence.]"
        ),
    }
    del messages[checkpoint:]
    return
```

**Why:** The current `break → _handle_iteration_budget_exhausted` path produces a
misleading error and unnecessarily saves partial progress (partial progress is useful
when the agent ran out of *iterations*; when the response was *truncated mid-call*, the
partial tool state is unusable). A distinct error message lets the user know the token
budget was the issue, not the iteration budget.

**Interaction with Solution A:** If Solution A is implemented correctly, Solution B
becomes a safety net for unusually large inputs. Both should be implemented: A prevents
the failure, B correctly reports it if it happens anyway.

---

### Solution C — Expose `max_tokens` as a per-agent constructor parameter

**Files:** `base.py:__init__`, `research_agent.py:__init__`, `chat.py:_init_agent`.

**Change:** Add `max_tokens: int = 2048` to `BaseAgent.__init__` and pass it through to
the API call sites. `NeuroResearchAgent.__init__` would default to `4096`. `chat.py`
does not need changes since it doesn't pass `max_tokens`.

**Why:** Keeps the base class conservative (2048 for simpler agents like `NeuroDbAgent`
and `NeuroTutorAgent` that don't generate large tool bodies) while allowing
`NeuroResearchAgent` to use a higher value without changing the default for all agents.
Cleaner than a hardcoded bump in the base class.

**Risk:** Slightly more constructor surface area. No functional risk.

---

### Solution D — Add a budget-proximity prompt injection (optional enhancement)

**Files:** `research_agent.py:_build_system_prompt` or a new method in `base.py`.

**Change:** When fewer than N iterations remain (e.g., 5), inject a system-level
reminder into the prompt: "You have N tool iterations remaining. If you have enough
evidence, call `draft_hypothesis` now rather than gathering more data."

**Why:** Addresses the genuine iteration-exhaustion scenario (distinct from the
token-truncation root cause). On a production DB with more data, the agent could
legitimately exhaust 40 iterations in discovery. This prompt injection gives the model
a signal to pivot from gathering to drafting before the budget is gone.

**Risk:** LLM behavior under prompt injection is not guaranteed. The agent might call
`draft_hypothesis` with insufficient evidence, producing lower-quality output. Not a
substitute for Solutions A and B.

---

## Recommended Sequence

1. **Implement Solution A + B together.** A directly removes the root cause. B makes the
   fallback error honest and distinct. Neither requires architectural changes.
2. **Optionally refactor into Solution C** in the same change if you want the base class
   to stay conservative by default.
3. **Evaluate Solution D** only after A+B are in and tested — it addresses a genuinely
   separate failure mode (iteration exhaustion with large data) that is not the current
   blocker.

Do not implement fixes without:
1. Re-running `uv run python reproduce_lt3_t6.py` to confirm the error no longer fires.
2. Running the full test suite (`uv run pytest`).
3. Manual re-test of T6 and T7 per the test plan.

---

## Files to Change (Solutions A + B)

| File | Location | Change |
|------|----------|--------|
| `src/neurodb/agents/base.py` | line 65 (`chat` path) and line 142 (`chat_stream` path) | `max_tokens=2048` → `max_tokens=4096` (or add constructor param per Solution C) |
| `src/neurodb/agents/base.py` | `_chat_stream_inner` after the `break` guard | Add `max_tokens` stop_reason branch before the `break` |
| `src/neurodb/agents/base.py` | `_chat_inner` after the `break` guard | Same for non-streaming path |

Optional (Solution C):
| `src/neurodb/agents/base.py` | `__init__` | Add `max_tokens: int = 2048` param |
| `src/neurodb/agents/research_agent.py` | `__init__` | Pass `max_tokens=4096` to `super().__init__` |
