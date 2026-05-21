"""POST /api/atlas/launch — start the NeuroAtlas viewer as a background process."""
from __future__ import annotations

import subprocess
from pathlib import Path

from fastapi import APIRouter

router = APIRouter()

_atlas_proc: subprocess.Popen | None = None
_ATLAS_SCRIPT = Path(__file__).resolve().parents[4] / "scripts" / "atlas.py"
_ATLAS_URL = "http://localhost:8080/tools/neuro-atlas/"


@router.post("/atlas/launch")
def launch_atlas() -> dict:
    global _atlas_proc
    running = _atlas_proc is not None and _atlas_proc.poll() is None
    if not running:
        _atlas_proc = subprocess.Popen(
            ["uv", "run", str(_ATLAS_SCRIPT)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
    return {"url": _ATLAS_URL}


@router.get("/atlas/status")
def atlas_status() -> dict:
    running = _atlas_proc is not None and _atlas_proc.poll() is None
    return {"running": running, "url": _ATLAS_URL if running else None}
