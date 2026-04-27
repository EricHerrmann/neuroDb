#!/usr/bin/env python
"""CLI: search and query the local NeuroDb.

Usage:
    uv run scripts/query_cli.py --search "plasticity"
    uv run scripts/query_cli.py --modality fMRI
    uv run scripts/query_cli.py --sql "SELECT * FROM v_dataset_summary"
"""
import argparse
from dotenv import load_dotenv
load_dotenv()
from neurodb.db import get_engine, init_db, get_session
from neurodb.query import search_datasets
from sqlalchemy import text


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--search", help="Keyword search on title/description")
    parser.add_argument("--modality", help="Filter by modality")
    parser.add_argument("--source", help="Filter by source")
    parser.add_argument("--sql", help="Raw SQL query")
    parser.add_argument("--db", default="neurodb.duckdb")
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)

    if args.sql:
        with engine.connect() as conn:
            rows = conn.execute(text(args.sql)).fetchall()
        for row in rows:
            print("\t".join(str(v) for v in row))
    else:
        with get_session(engine) as session:
            results = search_datasets(
                session,
                keyword=args.search,
                modality=args.modality,
                source=args.source,
            )
        for ds in results:
            print(f"[{ds.source}] {ds.source_id} — {ds.title} ({ds.modality}, n={ds.n_subjects})")
        print(f"\n{len(results)} result(s)")


if __name__ == "__main__":
    main()
