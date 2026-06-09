import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_streamlit_is_legacy_optional_dependency() -> None:
    pyproject = tomllib.loads((ROOT / "pyproject.toml").read_text())

    assert "streamlit>=1.56.0,<2.0" not in pyproject["project"]["dependencies"]
    assert pyproject["project"]["optional-dependencies"]["legacy-ui"] == [
        "streamlit>=1.56.0,<2.0"
    ]
    assert "streamlit>=1.56.0,<2.0" in pyproject["dependency-groups"]["dev"]


def test_streamlit_app_declares_deprecation_and_primary_ui() -> None:
    source = (ROOT / "src" / "neurodb" / "ui" / "app.py").read_text()

    assert "Deprecated Streamlit UI" in source
    assert "Deprecated legacy UI" in source
    assert "FastAPI + React" in source
    assert "uv sync --extra legacy-ui" in source
