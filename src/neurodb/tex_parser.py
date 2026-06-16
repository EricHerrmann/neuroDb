"""TeX project folder -> ParsedArtifact (Phase 2b TeX ingest).

Default path uses pylatexenc (pure-Python). A `latexml_convert` seam is accepted for a future
high-fidelity LaTeXML adapter (deferred); it defaults to None, so pylatexenc is used today.
Sections are anchored by section label (page=None); TeX has no pages.
"""
from __future__ import annotations

import logging
import re
from collections.abc import Callable
from pathlib import Path

from neurodb.chunking import Section
from neurodb.full_text_client import sections_from_labeled_blocks
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import score

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


_SECTION_RE = re.compile(r"\\(?:sub)*section\*?\s*\{([^}]*)\}")
_DOC_RE = re.compile(r"\\begin\{document\}(.*)\\end\{document\}", re.DOTALL)


def _document_body(src: str) -> str:
    """Return the text between \\begin{document} and \\end{document}, else the whole source."""
    m = _DOC_RE.search(src)
    return m.group(1) if m else src


def _split_sections(body: str) -> list[tuple[str | None, str]]:
    """Split body into (heading-title, raw-latex) blocks on section macros.

    Text before the first heading gets label None. Nested-brace titles are not supported
    (a known limitation; such titles are truncated at the first closing brace).
    """
    matches = list(_SECTION_RE.finditer(body))
    if not matches:
        return [(None, body)]
    blocks: list[tuple[str | None, str]] = []
    if matches[0].start() > 0:
        blocks.append((None, body[: matches[0].start()]))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        blocks.append((title, body[start:end]))
    return blocks


def _references_block(project_dir: Path, l2t) -> tuple[str, str] | None:
    bbls = sorted(p for p in project_dir.rglob("*.bbl") if p.is_file())
    if not bbls:
        return None
    text = l2t.latex_to_text(bbls[0].read_text(errors="replace")).strip()
    return ("References", text) if text else None


def parse_tex(
    project_dir: Path,
    *,
    latexml_convert: Callable[[Path], list[Section]] | None = None,
    text_source: str = "tex_latexml",
) -> ParsedArtifact:
    """Parse a TeX project folder into a ParsedArtifact.

    Uses latexml_convert if provided and it yields sections; otherwise (default today) uses
    pylatexenc. Raises ValueError if no text is extractable.
    """
    from pylatexenc.latex2text import LatexNodes2Text

    if latexml_convert is not None:
        try:
            sections = latexml_convert(project_dir)
            if sections:
                art = ParsedArtifact(sections, 0.0, text_source)
                art.parse_confidence = score(art)
                return art
        except Exception:
            logger.exception("latexml_convert failed; falling back to pylatexenc")

    main = _find_main_tex(project_dir)
    src = _expand_includes(main, project_dir)
    body = _document_body(src)
    l2t = LatexNodes2Text(math_mode="verbatim")

    blocks: list[tuple[str | None, str]] = []
    for label, raw in _split_sections(body):
        clean_label = l2t.latex_to_text(label).strip() if label else None
        blocks.append((clean_label or None, l2t.latex_to_text(raw)))
    refs = _references_block(project_dir, l2t)
    if refs:
        blocks.append(refs)

    sections, _full = sections_from_labeled_blocks(blocks)
    if not sections:
        raise ValueError("TeX project produced no extractable text")
    art = ParsedArtifact(sections, 0.0, "tex_pylatexenc")
    art.parse_confidence = score(art)
    return art
