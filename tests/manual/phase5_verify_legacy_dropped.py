#!/usr/bin/env python
"""Verify Groupings Phase 5 final state on a real DuckDB database.

Checks, against the given DB file, that migration 021 has run and the legacy
taxonomy schema is gone while the unified groupings schema is intact:
  - the eight legacy tables are ABSENT,
  - `groupings` and `grouping_links` are PRESENT,
  - `schema_migrations` records version >= 21.

Intended for the Groupings Phase 5 manual test plan: run it against the live
backend's DuckDB after the server has started (which applies migrations) and
after a restart, to confirm the drop sticks and is not resurrected.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, inspect, text

_LEGACY = (
    "topics",
    "concepts",
    "question_topics",
    "question_concepts",
    "paper_topics",
    "paper_concepts",
    "topic_concepts",
    "dataset_packet_topics",
)
_REQUIRED = ("groupings", "grouping_links")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="neurodb.duckdb", help="Path to the DuckDB database file.")
    args = parser.parse_args()

    db_path = Path(args.db)
    if not db_path.exists():
        raise SystemExit(f"DB not found: {db_path}")

    engine = create_engine(f"duckdb:///{db_path}")
    names = set(inspect(engine).get_table_names())

    failures: list[str] = []

    present_legacy = sorted(names & set(_LEGACY))
    if present_legacy:
        failures.append(f"legacy tables still present: {present_legacy}")

    missing_required = sorted(set(_REQUIRED) - names)
    if missing_required:
        failures.append(f"required groupings tables missing: {missing_required}")

    with engine.connect() as conn:
        version_row = conn.execute(
            text("SELECT MAX(version) FROM schema_migrations")
        ).fetchone()
    max_version = version_row[0] if version_row and version_row[0] is not None else None
    if max_version is None or max_version < 21:
        failures.append(f"schema_migrations max version is {max_version}; expected >= 21")

    if failures:
        print("FAIL: Groupings Phase 5 verification failed:")
        for f in failures:
            print(f"  - {f}")
        return 1

    print(
        "PASS: legacy taxonomy tables dropped; groupings/grouping_links present; "
        f"schema version {max_version}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
