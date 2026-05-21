#!/usr/bin/env python
"""Provider smoke-test: escalating isolation checks for one provider.

Mirrors the evidence-gathering approach used to diagnose the OpenAI
tool-use failure (2026-05-19). Each check isolates one more layer of the
stack, so failures pinpoint exactly where the provider diverges.

Checks (in order):
  1. Raw SDK, no tools
  2. NeuroDb adapter (create_message), no tools
  3. NeuroDb adapter (stream_message), no tools
  4. Raw SDK, one minimal tool
  5. NeuroDb adapter (create_message), full Tutor tools
  6. NeuroDb adapter (stream_message), full Tutor tools
  7. Full NeuroTutorAgent via chat_stream

Usage:
    uv run scripts/probe_provider.py --provider anthropic
    uv run scripts/probe_provider.py --provider openai
    uv run scripts/probe_provider.py --provider groq
    uv run scripts/probe_provider.py --provider gemini
    uv run scripts/probe_provider.py --provider deepseek

    # Use economy or premium tier model instead of standard:
    uv run scripts/probe_provider.py --provider openai --tier economy

API keys must be set in .env or the environment before running.
"""
import argparse
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# TOML config helpers
# ---------------------------------------------------------------------------

try:
    import tomllib
except ImportError:
    import tomli as tomllib  # type: ignore[no-redef]

_TOML_PATH = Path(__file__).resolve().parent.parent / "neurodb_models.toml"


def _load_toml() -> dict:
    with open(_TOML_PATH, "rb") as fh:
        return tomllib.load(fh)


def _model_for(provider: str, tier: str) -> str:
    config = _load_toml()
    try:
        return config["tiers"][tier]["providers"][provider]["model"]
    except KeyError:
        raise SystemExit(f"No model entry for provider={provider!r} tier={tier!r} in neurodb_models.toml")


# ---------------------------------------------------------------------------
# Provider → SDK client factories
# ---------------------------------------------------------------------------

_GROQ_BASE_URL = "https://api.groq.com/openai/v1"
_GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta/openai/"
_DEEPSEEK_BASE_URL = "https://api.deepseek.com/v1"

_OPENAI_COMPAT_PROVIDERS = {
    "openai":   ("OPENAI_API_KEY",   None),
    "groq":     ("GROQ_API_KEY",     _GROQ_BASE_URL),
    "gemini":   ("GOOGLE_API_KEY",   _GEMINI_BASE_URL),
    "deepseek": ("DEEPSEEK_API_KEY", _DEEPSEEK_BASE_URL),
}


def _build_raw_sdk(provider: str):
    """Return a raw SDK client for the provider (not a NeuroDb adapter)."""
    if provider == "anthropic":
        key = os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY not set")
        import anthropic
        return anthropic.Anthropic(api_key=key)

    if provider in _OPENAI_COMPAT_PROVIDERS:
        env_var, base_url = _OPENAI_COMPAT_PROVIDERS[provider]
        key = os.environ.get(env_var)
        if not key:
            raise SystemExit(f"{env_var} not set")
        import openai
        return openai.OpenAI(api_key=key, **({} if base_url is None else {"base_url": base_url}))

    raise SystemExit(f"Unknown provider: {provider!r}")


def _build_adapter(provider: str):
    """Return a NeuroDb ModelClient adapter for the provider."""
    from neurodb.config.providers.anthropic_client import AnthropicModelClient
    from neurodb.config.providers.openai_client import OpenAIModelClient

    raw = _build_raw_sdk(provider)
    if provider == "anthropic":
        return AnthropicModelClient(raw)
    return OpenAIModelClient(raw)


# ---------------------------------------------------------------------------
# Minimal tool definition (Anthropic input_schema format — adapters translate)
# ---------------------------------------------------------------------------

_ECHO_TOOL = {
    "name": "echo",
    "description": "Return the input string unchanged. Used only for provider smoke-testing.",
    "input_schema": {
        "type": "object",
        "properties": {"text": {"type": "string", "description": "Any string."}},
        "required": ["text"],
    },
}

_ECHO_TOOL_ANTHROPIC_RAW = _ECHO_TOOL  # Anthropic uses input_schema natively.

_ECHO_TOOL_OPENAI_RAW = {
    "type": "function",
    "function": {
        "name": "echo",
        "description": "Return the input string unchanged. Used only for provider smoke-testing.",
        "parameters": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
}


def _raw_tool_for(provider: str) -> list:
    if provider == "anthropic":
        return [_ECHO_TOOL_ANTHROPIC_RAW]
    return [_ECHO_TOOL_OPENAI_RAW]


# ---------------------------------------------------------------------------
# Tutor tools (copy from agent so we don't import the whole agent for check 5)
# ---------------------------------------------------------------------------

def _tutor_tools() -> list[dict]:
    from neurodb.agents.tutor_agent import _TUTOR_TOOLS
    from neurodb.agents.db_agent import TOOLS as _DB_TOOLS
    return list(_TUTOR_TOOLS) + list(_DB_TOOLS)


# ---------------------------------------------------------------------------
# Probe checks
# ---------------------------------------------------------------------------

_PROMPT = "Say exactly: probe ok"


def _check_1_raw_no_tools(provider: str, model: str) -> None:
    """Raw SDK call, no tools — confirms the provider API is reachable."""
    raw = _build_raw_sdk(provider)
    if provider == "anthropic":
        response = raw.messages.create(
            model=model,
            max_tokens=32,
            messages=[{"role": "user", "content": _PROMPT}],
        )
        text = "".join(b.text for b in response.content if b.type == "text")
    else:
        response = raw.chat.completions.create(
            model=model,
            max_completion_tokens=32,
            messages=[{"role": "user", "content": _PROMPT}],
        )
        text = response.choices[0].message.content or ""

    assert text.strip(), "Empty response from raw SDK (no tools)"


def _check_2_adapter_no_tools(provider: str, model: str) -> None:
    """NeuroDb adapter create_message, no tools — confirms adapter basic path."""
    adapter = _build_adapter(provider)
    response = adapter.create_message(
        model=model,
        messages=[{"role": "user", "content": _PROMPT}],
        system="",
        tools=[],
        max_tokens=32,
    )
    text = "".join(b.text for b in response.content if b.type == "text")
    assert text.strip(), "Empty response from adapter (no tools)"


def _check_3_adapter_stream_no_tools(provider: str, model: str) -> None:
    """NeuroDb adapter stream_message, no tools — confirms streaming path."""
    adapter = _build_adapter(provider)
    chunks = []
    with adapter.stream_message(
        model=model,
        messages=[{"role": "user", "content": _PROMPT}],
        system="",
        tools=[],
        max_tokens=32,
    ) as stream:
        for delta in stream:
            if delta.get("type") == "text_delta":
                chunks.append(delta["text"])
        final = stream.get_final_message()

    text = "".join(chunks) or "".join(b.text for b in final.content if b.type == "text")
    assert text.strip(), "Empty streaming response from adapter (no tools)"


def _check_4_raw_one_tool(provider: str, model: str) -> None:
    """Raw SDK call with one minimal tool — confirms tool schema is accepted."""
    raw = _build_raw_sdk(provider)
    tools = _raw_tool_for(provider)

    if provider == "anthropic":
        response = raw.messages.create(
            model=model,
            max_tokens=256,
            tools=tools,
            messages=[{"role": "user", "content": "Call the echo tool with text='hello'."}],
        )
        stop = response.stop_reason
    else:
        response = raw.chat.completions.create(
            model=model,
            max_completion_tokens=256,
            tools=tools,
            messages=[{"role": "user", "content": "Call the echo tool with text='hello'."}],
        )
        stop = response.choices[0].finish_reason

    assert stop in ("tool_use", "tool_calls", "stop", "end_turn"), (
        f"Unexpected stop_reason for raw SDK one-tool: {stop!r}"
    )


def _check_5_adapter_tutor_tools(provider: str, model: str) -> None:
    """Adapter create_message with full Tutor tool list — confirms schema translation."""
    adapter = _build_adapter(provider)
    tools = _tutor_tools()
    response = adapter.create_message(
        model=model,
        messages=[{"role": "user", "content": "What is synaptic plasticity? Use your tools."}],
        system="You are a neuroscience tutor. Search your tools before answering.",
        tools=tools,
        max_tokens=256,
    )
    assert response.stop_reason in ("end_turn", "tool_use"), (
        f"Unexpected stop_reason for adapter Tutor tools: {response.stop_reason!r}"
    )
    if response.stop_reason == "tool_use":
        tool_names = [b.tool_name for b in response.content if b.type == "tool_use"]
        print(f"       tool_use emitted: {tool_names}")


def _check_6_adapter_stream_tutor_tools(provider: str, model: str) -> None:
    """Adapter stream_message with full Tutor tool list — confirms streaming + tools."""
    adapter = _build_adapter(provider)
    tools = _tutor_tools()
    with adapter.stream_message(
        model=model,
        messages=[{"role": "user", "content": "What is synaptic plasticity? Use your tools."}],
        system="You are a neuroscience tutor. Search your tools before answering.",
        tools=tools,
        max_tokens=256,
    ) as stream:
        for _ in stream:
            pass
        final = stream.get_final_message()

    assert final.stop_reason in ("end_turn", "tool_use"), (
        f"Unexpected stop_reason for streaming adapter Tutor tools: {final.stop_reason!r}"
    )


def _check_7_full_agent(provider: str, model: str) -> None:
    """Full NeuroTutorAgent via chat_stream — confirms the end-to-end agent path."""
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from neurodb.schema import Base
    from neurodb.agents.tutor_agent import NeuroTutorAgent

    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)

    adapter = _build_adapter(provider)
    agent = NeuroTutorAgent(
        model_client=adapter,
        model=model,
        model_provider=provider,
        engine=engine,
        max_tool_iterations=3,
        max_tokens=512,
        context_mode="general",
    )

    events = list(agent.chat_stream("What is LTP?", []))
    terminal = next((e for e in reversed(events) if e.get("type") in ("done", "error")), None)
    assert terminal is not None, "No terminal event (done/error) from chat_stream"
    assert terminal["type"] != "error", f"Agent returned error: {terminal.get('text')}"

    text = terminal.get("text", "")
    print(f"       terminal_type: {terminal['type']}  text_chars: {len(text)}")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

_CHECKS = [
    ("Raw SDK, no tools",                        _check_1_raw_no_tools),
    ("NeuroDb adapter create_message, no tools", _check_2_adapter_no_tools),
    ("NeuroDb adapter stream_message, no tools", _check_3_adapter_stream_no_tools),
    ("Raw SDK, one minimal tool",                _check_4_raw_one_tool),
    ("NeuroDb adapter create_message, Tutor tools", _check_5_adapter_tutor_tools),
    ("NeuroDb adapter stream_message, Tutor tools", _check_6_adapter_stream_tutor_tools),
    ("Full NeuroTutorAgent via chat_stream",     _check_7_full_agent),
]


_ALL_TIERS = ["economy", "standard", "premium"]


def run_tier(provider: str, tier: str) -> int:
    """Run all checks for one tier. Returns number of failures."""
    model = _model_for(provider, tier)
    print(f"\n  [{tier}]  {model}")

    passed = 0
    failed = 0
    for label, fn in _CHECKS:
        print(f"    {label:<52}", end=" ", flush=True)
        try:
            fn(provider, model)
            print("-> OK")
            passed += 1
        except Exception as exc:
            print(f"-> FAIL: {exc}")
            failed += 1

    status = "ALL PASSED" if failed == 0 else f"{failed} FAILED, {passed} passed"
    print(f"    {status}")
    return failed


def run(provider: str, tiers: list[str]) -> None:
    print(f"\nNeuroDb provider probe: {provider.upper()}")
    print(f"  TOML: {_TOML_PATH.name}")

    total_failures = 0
    for tier in tiers:
        total_failures += run_tier(provider, tier)

    print()
    overall = "ALL PASSED" if total_failures == 0 else f"{total_failures} TOTAL FAILURES"
    print(f"  Overall: {overall}\n")
    if total_failures:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="NeuroDb provider smoke-test — runs all 7 isolation checks against each model tier.",
    )
    parser.add_argument(
        "--provider",
        required=True,
        choices=["anthropic", "openai", "groq", "gemini", "deepseek"],
        help="Provider to test",
    )
    parser.add_argument(
        "--tier",
        choices=_ALL_TIERS,
        help="Specific tier to test (default: all three tiers)",
    )
    args = parser.parse_args()
    tiers = [args.tier] if args.tier else _ALL_TIERS
    run(args.provider, tiers)


if __name__ == "__main__":
    main()
