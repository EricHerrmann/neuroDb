import json

from neurodb.prefs import load_prefs, save_prefs


def test_load_prefs_returns_default_when_no_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7


def test_save_and_reload_preserves_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    save_prefs({"relevance_threshold": 0.4})
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.4


def test_load_prefs_with_corrupt_file_returns_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "neurodb_prefs.json").write_text("not valid json{{")
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7


def test_load_prefs_merges_unknown_keys(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "neurodb_prefs.json").write_text(json.dumps({"other": 42}))
    prefs = load_prefs()
    assert prefs["relevance_threshold"] == 0.7
    assert prefs["other"] == 42
