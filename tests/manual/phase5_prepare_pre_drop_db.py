#!/usr/bin/env python
"""Prepare a pre-Phase-5 DuckDB to exercise migration 021 (legacy table drop).

Builds a normal database with init_db (groupings present, all migrations
applied), then injects the eight legacy taxonomy tables with a couple of sample
rows and rewinds `schema_migrations` to version 20. Starting the backend against
the resulting DB therefore re-applies migration 021 and drops the legacy tables
— reproducing the production upgrade path without needing a historical DB.

Usage (then start the backend against the DB and run phase5_verify_legacy_dropped.py):
    uv run python tests/manual/phase5_prepare_pre_drop_db.py --force
"""
from __future__ import annotations

import argparse
from pathlib import Path

from sqlalchemy import create_engine, text

from neurodb.db import init_db

# Legacy join tables migration 021 drops: name -> the two non-id integer columns.
# Empty tables are enough to prove the drop; topics/concepts also get a sample row
# (below) so the operator can see real data was present before the drop.
_LEGACY_LINK_TABLES = {
    "question_topics": ("question_id", "topic_id"),
    "question_concepts": ("question_id", "concept_id"),
    "paper_topics": ("paper_id", "topic_id"),
    "paper_concepts": ("paper_id", "concept_id"),
    "topic_concepts": ("topic_id", "concept_id"),
    "dataset_packet_topics": ("packet_id", "topic_id"),
}

_PARENT_DDL = (
    "CREATE TABLE {name} (id INTEGER PRIMARY KEY, name VARCHAR(256), "
    "status VARCHAR(16), created_at VARCHAR(32), updated_at VARCHAR(32))"
)


def _inject_legacy_tables(conn) -> None:
    conn.execute(text(_PARENT_DDL.format(name="topics")))
    conn.execute(text(_PARENT_DDL.format(name="concepts")))
    for name, (col_a, col_b) in _LEGACY_LINK_TABLES.items():
        conn.execute(text(
            f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, {col_a} INTEGER, {col_b} INTEGER)"
        ))
    conn.execute(text(
        "INSERT INTO topics VALUES (1, 'plasticity', 'active', '2026-01-01', '2026-01-01')"
    ))
    conn.execute(text(
        "INSERT INTO concepts VALUES (1, 'LTP', 'active', '2026-01-01', '2026-01-01')"
    ))
    # Rewind so migration 021 has not yet been applied for this DB.
    conn.execute(text("DELETE FROM schema_migrations WHERE version = 21"))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-db", default="/tmp/neurodb_phase5_pre_drop.duckdb")
    parser.add_argument("--force", action="store_true", help="Replace an existing target DB.")
    args = parser.parse_args()

    target = Path(args.target_db)
    if target.exists():
        if not args.force:
            raise SystemExit(
                f"Target DB already exists: {target}; rerun with --force to replace it"
            )
        target.unlink()

    target.parent.mkdir(parents=True, exist_ok=True)
    engine = create_engine(f"duckdb:///{target}")
    init_db(engine)  # full build: groupings present, version 21, no legacy tables
    with engine.begin() as conn:
        _inject_legacy_tables(conn)

    print(f"PASS: pre-drop DB ready at {target} (legacy tables present, schema version 20).")
    print(f"Next: start the backend against this DB, then run "
          f"phase5_verify_legacy_dropped.py --db {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
