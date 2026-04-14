#!/usr/bin/env python
"""CLI: enrich source records with file-level metadata.

Usage:
    uv run scripts/enrich.py --source dandi --limit 10 --db neurodb.duckdb
"""
import argparse
from neurodb.db import get_engine, init_db, create_views
from neurodb.connectors.dandi import DandiDataset  # noqa: F401 — registers model
from neurodb.enrichment import run_enrichment

SOURCES = ["dandi"]


def main():
    parser = argparse.ArgumentParser(description="Enrich neuro records with file-level metadata")
    parser.add_argument("--source", choices=SOURCES, required=True)
    parser.add_argument("--limit", type=int, default=None, help="Max records to enrich (default: all)")
    parser.add_argument("--db", default="neurodb.duckdb")
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    create_views(engine)
    count = run_enrichment(engine, limit=args.limit)
    print(f"Enrichment complete: {count} records enriched.")


if __name__ == "__main__":
    main()
