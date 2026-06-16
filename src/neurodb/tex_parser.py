"""TeX project folder -> ParsedArtifact (Phase 2b TeX ingest).

Default path uses pylatexenc (pure-Python). A `latexml_convert` seam is accepted for a future
high-fidelity LaTeXML adapter (deferred); it defaults to None, so pylatexenc is used today.
Sections are anchored by section label (page=None); TeX has no pages.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)


def _has_doc_markers(p: Path) -> bool:
    try:
        t = p.read_text(errors="replace")
    except OSError:
        return False
    return "\\documentclass" in t and "\\begin{document}" in t


def _find_main_tex(project_dir: Path) -> Path:
    """Return the main .tex (contains \\documentclass and \\begin{document}).

    Multiple matches -> first by sorted path (logged). No match -> ValueError.
    """
    mains = [p for p in sorted(project_dir.rglob("*.tex")) if p.is_file() and _has_doc_markers(p)]
    if not mains:
        raise ValueError(f"No main .tex (\\documentclass + \\begin{{document}}) in {project_dir}")
    if len(mains) > 1:
        logger.warning("Multiple main .tex files in %s; using %s", project_dir, mains[0])
    return mains[0]


_INCLUDE_RE = re.compile(r"\\(?:input|include)\{([^}]+)\}")
_MAX_INCLUDE_DEPTH = 20


def _expand_includes(path: Path, root: Path, _seen: set | None = None, _depth: int = 0) -> str:
    """Inline \\input/\\include relative to root. Skips missing/escaping files; guards cycles."""
    if _seen is None:
        _seen = set()
    rp = path.resolve()
    if rp in _seen or _depth > _MAX_INCLUDE_DEPTH:
        return ""
    _seen.add(rp)
    try:
        text = path.read_text(errors="replace")
    except OSError:
        return ""

    def _repl(m: re.Match) -> str:
        name = m.group(1).strip()
        if not name.endswith(".tex"):
            name += ".tex"
        child = (root / name)
        try:
            inside = child.resolve().is_relative_to(root.resolve())
        except OSError:
            inside = False
        if not inside or not child.exists():
            logger.warning("Skipping missing/escaping include: %s", name)
            return ""
        return _expand_includes(child, root, _seen, _depth + 1)

    return _INCLUDE_RE.sub(_repl, text)
