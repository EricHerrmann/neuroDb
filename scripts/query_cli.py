#!/usr/bin/env python
"""CLI: query ingested datasets.

Usage:
    uv run scripts/query_cli.py --search "plasticity"
    uv run scripts/query_cli.py --modality EEG
    uv run scripts/query_cli.py --search "brain" --modality MRI --db neurodb.db
"""
import argparse
from neurodb.db import get_engine, init_db
from neurodb.query import search_datasets
from neurodb.db import get_session


def main():
    parser = argparse.ArgumentParser(description="Query NeuroDb datasets")
    parser.add_argument("--search", default=None, help="Keyword to search in title/description")
    parser.add_argument("--modality", default=None, help="Filter by modality (e.g. MRI, EEG)")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--db", default="neurodb.db")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    init_db(engine)

    with get_session(engine) as session:
        results = search_datasets(session, keyword=args.search, modality=args.modality, limit=args.limit)

    if not results:
        print("No datasets found.")
        return

    print(f"{'ID':<12} {'Modality':<10} {'Subjects':<10} Title")
    print("-" * 70)
    for ds in results:
        print(f"{ds.source_id:<12} {(ds.modality or ''):<10} {(str(ds.n_subjects) if ds.n_subjects else ''):<10} {ds.title}")
    print(f"\n{len(results)} result(s)")


if __name__ == "__main__":
    main()
