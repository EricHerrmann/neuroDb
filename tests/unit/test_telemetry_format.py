from neurodb.config.telemetry_format import format_recorded_at


def test_format_recorded_at_formats_iso_timestamp():
    assert format_recorded_at("2026-05-23T13:45:22+00:00") == "13:45:22 23/05/26"


def test_format_recorded_at_handles_z_suffix():
    assert format_recorded_at("2026-05-23T13:45:22Z") == "13:45:22 23/05/26"


def test_format_recorded_at_returns_original_for_unparseable_value():
    assert format_recorded_at("not-a-date") == "not-a-date"
