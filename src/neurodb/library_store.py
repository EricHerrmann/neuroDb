"""Local document library (a drop folder) for user-supplied files such as paywalled PDFs.

The user downloads files into the library dir; the Knowledge Library reads them in place. All
reads are constrained to the library root (path-traversal guard).
"""
from __future__ import annotations

import os
from pathlib import Path

SUPPORTED_EXTS = {".pdf", ".txt", ".md", ".html", ".htm"}


def library_root() -> Path:
    root = Path(os.environ.get("NEURODB_LIBRARY_DIR", "knowledge_library_files"))
    root.mkdir(parents=True, exist_ok=True)
    return root.resolve()


def list_library_files() -> list[dict]:
    root = library_root()
    files: list[dict] = []
    for p in sorted(root.iterdir()):
        if not p.is_file() or p.suffix.lower() not in SUPPORTED_EXTS:
            continue
        if not p.resolve().is_relative_to(root):
            continue
        st = p.stat()
        files.append({"name": p.name, "size": st.st_size, "modified": st.st_mtime})
    return files


def resolve_library_path(name: str) -> Path | None:
    """Return the resolved path iff `name` is a supported regular file inside the library root."""
    if not name:
        return None
    root = library_root()
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_file():
        return None
    if candidate.suffix.lower() not in SUPPORTED_EXTS:
        return None
    return candidate


def _has_tex(folder: Path) -> bool:
    return any(c.is_file() and c.suffix.lower() == ".tex" for c in folder.rglob("*.tex"))


def list_library_projects() -> list[dict]:
    """Surface top-level subdirectories containing at least one .tex as selectable projects."""
    root = library_root()
    projects: list[dict] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir():
            continue
        if not p.resolve().is_relative_to(root):
            continue
        if not _has_tex(p):
            continue
        projects.append({"name": p.name, "kind": "tex_project", "modified": p.stat().st_mtime})
    return projects


def resolve_library_project(name: str) -> Path | None:
    """Return the resolved folder iff `name` is a directory inside the root containing a .tex."""
    if not name:
        return None
    root = library_root()
    candidate = (root / name).resolve()
    if not candidate.is_relative_to(root):
        return None
    if not candidate.is_dir():
        return None
    if not _has_tex(candidate):
        return None
    return candidate
