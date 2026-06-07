"""Load optional user-facing behavior instructions for NeuroDb agents."""

import os
from pathlib import Path

_ENV_VAR = "NEURODB_AGENT_BEHAVIOR_PATH"
_DEFAULT_MAX_CHARS = 6000
_START_MARKER = "<!-- neurodb-agent-behavior:start -->"
_END_MARKER = "<!-- neurodb-agent-behavior:end -->"
_REPO_ROOT = Path(__file__).resolve().parents[3]
_DEFAULT_RELATIVE_PATHS = (
    "docs/agent_behavior.md",
    "AGENTS.md",
    "CLAUDE.md",
)


def load_agent_behavior_instructions(
    path: str | Path | None = None,
    max_chars: int = _DEFAULT_MAX_CHARS,
) -> str:
    """Return configured behavior instructions for inclusion in agent prompts."""
    behavior_path = _resolve_behavior_path(path)
    if behavior_path is None:
        return ""

    try:
        raw_content = behavior_path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""

    content = _extract_marked_section(raw_content).strip()
    if not content:
        return ""

    if len(content) > max_chars:
        content = (
            content[:max_chars].rstrip()
            + "\n\n[Behavior instructions truncated to configured limit.]"
        )

    return f"Additional agent behavior instructions:\n{content}"


def _resolve_behavior_path(path: str | Path | None) -> Path | None:
    configured = path or os.environ.get(_ENV_VAR)
    if configured:
        candidate = _resolve_path(configured)
        return candidate if candidate.is_file() else None

    for relative_path in _DEFAULT_RELATIVE_PATHS:
        candidate = _REPO_ROOT / relative_path
        if candidate.is_file():
            return candidate
    return None


def _resolve_path(path: str | Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return _REPO_ROOT / candidate


def _extract_marked_section(content: str) -> str:
    start = content.find(_START_MARKER)
    if start == -1:
        return content

    section_start = start + len(_START_MARKER)
    end = content.find(_END_MARKER, section_start)
    if end == -1:
        return content
    return content[section_start:end]
