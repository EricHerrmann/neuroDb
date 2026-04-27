#!/usr/bin/env python
"""CLI: run ingest for a named source.

Usage:
    uv run scripts/ingest.py --source openneuro --limit 200 --db neurodb.db
"""
import argparse
from dotenv import load_dotenv
load_dotenv()
from neurodb.db import get_engine, init_db, create_views
from neurodb.provenance import run_ingest
from neurodb.connectors.openneuro import OpenNeuroConnector
from neurodb.connectors.allen_brain import AllenBrainConnector
from neurodb.connectors.neurovault import NeuroVaultConnector  # noqa: F401 — registers model
from neurodb.connectors.dandi import DandiConnector  # noqa: F401 — registers model
from neurodb.embedder import Embedder
from neurodb.vector_store import VectorStore
from neurodb.embed_hooks import embed_source_datasets

CONNECTORS = {
    "openneuro": OpenNeuroConnector,
    "allen_brain": AllenBrainConnector,
    "neurovault": NeuroVaultConnector,
    "dandi": DandiConnector,
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
    print("Embedding datasets into vector store…")
    chroma_path = args.db.replace(".duckdb", "_chroma")
    vs = VectorStore(path=chroma_path, embedder=Embedder())
    n = embed_source_datasets(engine, vs, source=connector.SOURCE_NAME)
    print(f"Embedded {n} dataset(s).")


if __name__ == "__main__":
    main()
