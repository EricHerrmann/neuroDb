"""TeX project folder -> ParsedArtifact (Phase 2b TeX ingest).

Default path uses pylatexenc (pure-Python). A `latexml_convert` seam is accepted for a future
high-fidelity LaTeXML adapter (deferred); it defaults to None, so pylatexenc is used today.
Sections are anchored by section label (page=None); TeX has no pages.
"""
from __future__ import annotations

import logging
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
