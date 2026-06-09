"""Unit tests for the temporal trust descriptor (spec invariant #8)."""
from neurodb.temporal import CUTOFF_YEAR, temporal_descriptor


def test_pre_cutoff_year():
    d = temporal_descriptor(1982, "current")
    assert d["cutoff_relation"] == "pre_cutoff"
    assert d["vintage"] == "1982"
    assert d["warning"] is None


def test_post_cutoff_year():
    d = temporal_descriptor(CUTOFF_YEAR, "current")
    assert d["cutoff_relation"] == "post_cutoff"


def test_unknown_year():
    d = temporal_descriptor(None, "current")
    assert d["cutoff_relation"] == "unknown"
    assert d["vintage"] == "unknown"


def test_retracted_sets_warning():
    d = temporal_descriptor(2020, "retracted")
    assert d["warning"] is not None
    assert "retracted" in d["warning"]


def test_current_has_no_warning():
    assert temporal_descriptor(2020, "current")["warning"] is None
