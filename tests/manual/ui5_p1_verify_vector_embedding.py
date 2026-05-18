#!/usr/bin/env python
"""Manual UI5 P1 vector embedding verification helper."""

import argparse
import os
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_CONCEPT = "UI5-P1-manual-LTP"


def chroma_path_for_db(db_path: str) -> str:
    if db_path.endswith(".duckdb"):
        return db_path.removesuffix(".duckdb") + "_chroma"
    return db_path + "_chroma"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Search the NeuroDb Chroma collection for a manual-test note embedding.",
    )
    parser.add_argument(
        "--db",
        default="",
        help="DuckDB path used to derive the default Chroma path.",
    )
    parser.add_argument(
        "--concept",
        default=DEFAULT_CONCEPT,
        help="Concept tag to include in the default vector search query.",
    )
    parser.add_argument(
        "--chroma-path",
        default="",
        help="Path to the Chroma store. Defaults to <NEURODB_DB_PATH or neurodb.duckdb>_chroma.",
    )
    parser.add_argument(
        "--query",
        default="",
        help="Search query used to verify the note embedding.",
    )
    parser.add_argument("--n-results", type=int, default=5)
    return parser


def main() -> None:
    load_dotenv(".env")
    args = build_parser().parse_args()

    db_path = args.db or os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    chroma_path = args.chroma_path or chroma_path_for_db(db_path)
    query = args.query or f"{args.concept} vector embedding verification"

    from neurodb.embedder import Embedder
    from neurodb.vector_store import VectorStore

    store = VectorStore(path=chroma_path, embedder=Embedder())
    results = store.search(query, n_results=args.n_results)

    if not results:
        print(f"No vector results found in {Path(chroma_path)} for query: {query}")
        return

    for result in results:
        print(result["id"], result["metadata"], result["document"])


if __name__ == "__main__":
    main()
