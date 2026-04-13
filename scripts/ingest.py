#!/usr/bin/env python
"""CLI: run ingest for a named source.

Usage:
    uv run scripts/ingest.py --source openneuro --limit 200 --db neurodb.db
"""
import argparse
from neurodb.db import get_engine, init_db, create_views
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector
from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.neurovault import NeuroVaultConnector  # noqa: F401 — registers model

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
    "allen_brain": AllenBrainConnector,
    "neurovault": NeuroVaultConnector,
}


def main():
    parser = argparse.ArgumentParser(description="Ingest a neuro data source into NeuroDb")
    parser.add_argument("--source", choices=list(CONNECTORS), required=True)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--db", default="neurodb.duckdb")
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    create_views(engine)
    connector = CONNECTORS[args.source]()
    run = run_ingest(engine, connector=connector, limit=args.limit)
    print(f"Ingest complete: run_id={run.id}, source={run.source}, at={run.run_at}")


if __name__ == "__main__":
    main()
