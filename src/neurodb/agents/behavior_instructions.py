"""Load optional user-facing behavior instructions for NeuroDb agents."""

import os
from pathlib import Path

CITATION_PROVENANCE_RULE = (
    "When you cite a specific paper, mark its source provenance inline, right "
    "after the paper. If the paper came from a Knowledge Library result (a "
    "search_knowledge_library result, or a paper in the provided local/topic "
    "context), render the citation as a clickable Markdown link to that paper "
    "in the Knowledge Library panel, using the result's source_id: "
    "'[<Title> (Knowledge Library · <level>)](/knowledge-library?focus=<source_id>)', "
    "where <level> is that result's data_tier rendered as 'metadata', 'abstract', "
    "or 'full text' and <source_id> is the integer id from the tool result or "
    "provided local context. If the paper is not in the Knowledge Library (for "
    "example a search_literature result), instead link it with its URL using "
    "Markdown, e.g. [Title](https://example.org). If a cited paper is neither in "
    "the Knowledge Library nor has a URL, write '(not in Knowledge Library)' and "
    "apply the usual model-knowledge / needs-verification labeling. Never state a "
    "Knowledge Library status or level, or a source_id, that did not come from a "
    "tool result or the provided local context."
)

_DATA_TIER_LABELS = {
    "metadata": "metadata",
    "abstract": "abstract",
    "full_text": "full text",
}


def data_tier_label(data_tier: str | None) -> str:
    """Map a stored Paper.data_tier to a human citation level."""
    return _DATA_TIER_LABELS.get((data_tier or "").strip().lower(), "metadata")

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
