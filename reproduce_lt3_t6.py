#!/usr/bin/env python3
"""LT-3 T6/T7 reproduction script — instruments each iteration for stop_reason and token usage."""

import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import anthropic
from sqlalchemy import create_engine

from neurodb.agents.research_agent import NeuroResearchAgent

PROMPT_T6 = (
    "Draft a hypothesis linking hippocampal synaptic plasticity to learning-related "
    "dataset measures, including evidence, predictions, candidate datasets, confounds, "
    "and limitations."
)

PROMPT_T7 = "Draft a hypothesis from local datasets about hippocampal plasticity and learning."


def _make_instrumented_stream(original_stream, iteration_log: list):
    """Wrap the stream context manager to log stop_reason and token usage."""

    def patched_stream(*args, **kwargs):
        ctx = original_stream(*args, **kwargs)

        class _InstrumentedStream:
            def __enter__(self_):
                self_._inner = ctx.__enter__()
                return self_

            def __exit__(self_, *a):
                return ctx.__exit__(*a)

            def __iter__(self_):
                return iter(self_._inner)

            def get_final_message(self_):
                msg = self_._inner.get_final_message()
                usage = getattr(msg, "usage", None)
                entry = {
                    "stop_reason": msg.stop_reason,
                    "content_types": [b.type for b in msg.content],
                    "input_tokens": getattr(usage, "input_tokens", None),
                    "output_tokens": getattr(usage, "output_tokens", None),
                }
                iteration_log.append(entry)
                print(
                    f"\n  [iter {len(iteration_log)}] stop_reason={msg.stop_reason} "
                    f"content={entry['content_types']} "
                    f"out_tokens={entry['output_tokens']}"
                )
                return msg

        return _InstrumentedStream()

    return patched_stream


def run(prompt: str, label: str) -> None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("ERROR: ANTHROPIC_API_KEY not set in .env")
        sys.exit(1)

    max_iters = int(os.environ.get("NEURODB_RESEARCH_MAX_TOOL_ITERATIONS", "25"))
    print(f"\n{'='*60}")
    print(f"Reproducing: {label}")
    print(f"Max tool iterations: {max_iters}")
    print(f"Prompt: {prompt[:80]}...")
    print("=" * 60)

    # Use a fresh test DB so we can run alongside the Streamlit server
    engine = create_engine("duckdb:///repro_test.duckdb")
    client = anthropic.Anthropic(api_key=api_key)

    agent = NeuroResearchAgent(
        client=client,
        engine=engine,
        max_tool_iterations=max_iters,
    )

    iteration_log: list = []
    agent._client.messages.stream = _make_instrumented_stream(
        agent._client.messages.stream, iteration_log
    )

    messages: list = []
    print("\n--- streaming events ---")
    for event in agent.chat_stream(prompt, messages):
        t = event["type"]
        if t == "text_delta":
            print(event["text"], end="", flush=True)
        elif t == "tool_start":
            print(
                f"\n[TOOL START] Step {event.get('iteration')}/{event.get('limit')}: "
                f"{event['tool_name']} input={json.dumps(event['tool_input'])[:120]}"
            )
        elif t == "tool_result":
            preview = event["result"][:200].replace("\n", " ")
            print(f"[TOOL RESULT] {event['tool_name']}: {preview}")
        elif t == "done":
            print(f"\n[DONE] stop_reason={event['stop_reason']}")
        elif t == "error":
            print(f"\n[ERROR] {event['text'][:300]}")

    print("\n\n--- iteration summary ---")
    for i, e in enumerate(iteration_log, 1):
        print(
            f"  iter {i:02d}: stop_reason={e['stop_reason']:12s} "
            f"content_types={e['content_types']} "
            f"out_tokens={e['output_tokens']}"
        )

    draft_tools = [t for t in agent._tool_trace_debug if t == "draft_hypothesis"] if hasattr(agent, "_tool_trace_debug") else []
    max_tokens_hits = sum(1 for e in iteration_log if e["stop_reason"] == "max_tokens")
    end_turn_hits = sum(1 for e in iteration_log if e["stop_reason"] == "end_turn")
    tool_use_hits = sum(1 for e in iteration_log if e["stop_reason"] == "tool_use")
    print(f"\n  total iterations: {len(iteration_log)}")
    print(f"  tool_use stops:   {tool_use_hits}")
    print(f"  end_turn stops:   {end_turn_hits}")
    print(f"  max_tokens stops: {max_tokens_hits}")

    final_messages_count = len(messages)
    print(f"  messages in API history after turn: {final_messages_count}")
    if messages:
        last_role = messages[-1].get("role", "?")
        last_content = messages[-1].get("content", "")
        if isinstance(last_content, str):
            preview = last_content[:120]
        elif isinstance(last_content, list) and last_content:
            first = last_content[0]
            if isinstance(first, dict):
                preview = str(first)[:120]
            else:
                preview = str(getattr(first, "type", first))[:120]
        else:
            preview = str(last_content)[:120]
        print(f"  last message role={last_role}: {preview}")


if __name__ == "__main__":
    run(PROMPT_T6, "T6 — draft hypothesis")
