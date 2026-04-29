"""User preferences persisted in a local JSON file."""

import json
from pathlib import Path

_PREFS_FILE = Path("neurodb_prefs.json")
_DEFAULTS: dict = {"relevance_threshold": 0.7}


def load_prefs() -> dict:
    """Load saved preferences, falling back to defaults on missing/corrupt files."""
    if _PREFS_FILE.exists():
        try:
            data = json.loads(_PREFS_FILE.read_text())
            return {**_DEFAULTS, **data}
        except Exception:
            return _DEFAULTS.copy()
    return _DEFAULTS.copy()


def save_prefs(prefs: dict) -> None:
    """Persist preferences to disk."""
    _PREFS_FILE.write_text(json.dumps(prefs, indent=2))
