"""Unit tests for the suggestions page import logic."""
from unittest.mock import MagicMock, patch
import pytest
from sqlalchemy import create_engine

from neurodb.db import init_db
from neurodb.ui.pages.suggestions import _ingest_dataset


def _engine():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    return engine


def test_ingest_dataset_calls_run_ingest_in_process():
    """_ingest_dataset must call run_ingest directly — no subprocess."""
    engine = _engine()
    with patch("neurodb.ui.pages.suggestions.run_ingest") as mock_ingest:
        mock_ingest.return_value = MagicMock()
        _ingest_dataset("openneuro", "ds003787", engine)

    assert mock_ingest.called
    _, kwargs = mock_ingest.call_args
    assert kwargs["dataset_ids"] == ["ds003787"]
    assert kwargs["engine"] is engine


def test_ingest_dataset_unknown_source_raises():
    """_ingest_dataset must raise ValueError for an unregistered source."""
    engine = _engine()
    with pytest.raises(ValueError, match="No connector registered"):
        _ingest_dataset("unknown_source", "ds003787", engine)


def test_ingest_dataset_does_not_use_subprocess():
    """Confirm subprocess is not involved — the whole point of the T6 fix."""
    engine = _engine()
    with patch("neurodb.ui.pages.suggestions.run_ingest", return_value=MagicMock()), \
         patch("subprocess.run") as mock_subprocess:
        _ingest_dataset("openneuro", "ds003787", engine)

    mock_subprocess.assert_not_called()
