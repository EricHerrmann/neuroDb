#!/usr/bin/env python
"""One-shot migration: copy an existing neurodb.db (SQLite) into neurodb.duckdb (DuckDB).

Usage:
    uv run scripts/migrate_to_duckdb.py
    uv run scripts/migrate_to_duckdb.py --sqlite neurodb.db --duckdb neurodb.duckdb

Safe to run against an already-migrated target: tables are populated only if empty.
"""
import argparse
import duckdb
from dotenv import load_dotenv
load_dotenv()
from neurodb.db import get_engine, init_db, create_views
from neurodb.connectors.openneuro import OpenNeuroDataset  # registers model with Base.metadata  # noqa: F401
from neurodb.connectors.allen_brain import AllenDataset  # registers model with Base.metadata  # noqa: F401

# Tables ordered by foreign-key dependency (parents first).
TABLES = [
    "ingest_runs",
    "datasets_index",
    "subjects",
    "cross_refs",
    "quality_events",
    "openneuro_datasets",
    "allen_datasets",
]


def migrate(sqlite_path: str, duckdb_path: str) -> None:
    print(f"Migrating {sqlite_path} → {duckdb_path}")

    # Step 1: Create DuckDB schema via SQLAlchemy (constraints, indexes, sequences).
    duckdb_engine = get_engine(f"duckdb:///{duckdb_path}")
    init_db(duckdb_engine)
    duckdb_engine.dispose()

    # Step 2: Copy data table by table using DuckDB's SQLite attachment.
    conn = duckdb.connect(duckdb_path)
    conn.execute(f"ATTACH '{sqlite_path}' AS src (TYPE SQLITE)")

    for table in TABLES:
        try:
            count = conn.execute(f"SELECT COUNT(*) FROM src.{table}").fetchone()[0]  # noqa: S608
        except Exception:
            print(f"  {table}: not in source, skipping")
            continue
        if count == 0:
            print(f"  {table}: 0 rows in source, skipping")
            continue
        existing = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        if existing > 0:
            print(f"  {table}: already has {existing} rows, skipping")
            continue
        conn.execute(f"INSERT INTO {table} SELECT * FROM src.{table}")  # noqa: S608
        copied = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]  # noqa: S608
        print(f"  {table}: copied {copied} rows")

    conn.execute("DETACH src")
    conn.close()

    # Step 3: Create views in DuckDB.
    duckdb_engine = get_engine(f"duckdb:///{duckdb_path}")
    create_views(duckdb_engine)
    duckdb_engine.dispose()
    print("Migration complete.")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", default="neurodb.db")
    parser.add_argument("--duckdb", default="neurodb.duckdb")
    args = parser.parse_args()
    migrate(args.sqlite, args.duckdb)


if __name__ == "__main__":
    main()
