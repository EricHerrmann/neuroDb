import sys

from scripts.study import parse_args


def test_study_cli_accepts_db_before_subcommand():
    args = parse_args([
        "--db",
        "custom.duckdb",
        "list",
        "--concept",
        "LTP",
    ])

    assert args.db == "custom.duckdb"
    assert args.cmd == "list"
    assert args.concept == "LTP"


def test_study_cli_accepts_db_after_subcommand():
    args = parse_args([
        "list",
        "--concept",
        "LTP",
        "--db",
        "custom.duckdb",
    ])

    assert args.db == "custom.duckdb"
    assert args.cmd == "list"
    assert args.concept == "LTP"


def test_study_cli_accepts_db_equals_form_anywhere():
    args = parse_args([
        "list",
        "--db=custom.duckdb",
        "--concept",
        "LTP",
    ])

    assert args.db == "custom.duckdb"
    assert args.cmd == "list"
    assert args.concept == "LTP"


def test_study_cli_preparses_real_sys_argv(monkeypatch):
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "scripts/study.py",
            "--db",
            "custom.duckdb",
            "list",
            "--concept",
            "LTP",
        ],
    )

    args = parse_args()

    assert args.db == "custom.duckdb"
    assert args.cmd == "list"
    assert args.concept == "LTP"
