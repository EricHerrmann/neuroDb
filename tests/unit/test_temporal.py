"""Unit tests for the temporal trust descriptor (spec invariant #8)."""
from neurodb.temporal import (
    CUTOFF_YEAR,
    TEMPORAL_DISCLOSURE_RULES,
    attach_temporal,
    parse_year,
    temporal_descriptor,
)


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


def test_parse_year_coerces_and_tolerates_garbage():
    assert parse_year("2024") == 2024
    assert parse_year(2024) == 2024
    assert parse_year("") is None
    assert parse_year(None) is None
    assert parse_year("circa 2020") is None


def test_attach_temporal_enriches_each_result():
    results = [
        {"metadata": {"year": "2026", "currency_status": "current"}},
        {"metadata": {"year": "", "currency_status": "retracted"}},
        {"metadata": None},
    ]
    enriched = attach_temporal(results)
    assert enriched[0]["temporal"]["cutoff_relation"] == "post_cutoff"
    assert enriched[0]["temporal"]["vintage"] == "2026"
    assert enriched[1]["temporal"]["warning"] is not None
    assert enriched[2]["temporal"]["cutoff_relation"] == "unknown"


def test_disclosure_rules_mention_tier_and_cutoff():
    assert "state its tier" in TEMPORAL_DISCLOSURE_RULES.lower()
    assert "post-training-cutoff" in TEMPORAL_DISCLOSURE_RULES.lower()
