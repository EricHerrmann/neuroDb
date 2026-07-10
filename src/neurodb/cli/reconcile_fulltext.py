"""One-time backfill + reconciliation for papers that already have full text.

Runs the same shared post-acquisition hook the acquisition paths use, so the
existing corpus catches up with the FullTextAcquired pipeline. Idempotent:
re-running converges to the same state (audit rows append by design).

Usage: uv run python -m neurodb.cli.reconcile_fulltext [--db PATH] [--dry-run]
Note: the live run loads the embedding model to construct the shared stores
(no inference happens — reconciliation is metadata-only), which can take a
minute on CPU-only machines.
"""
from __future__ import annotations

import argparse
import os

from dotenv import load_dotenv


def select_fulltext_papers(engine) -> list[tuple[int, str]]:
    from neurodb.db import get_session
    from neurodb.schema import Paper

    with get_session(engine) as session:
        rows = (
            session.query(Paper.id, Paper.title)
            .filter(Paper.data_tier == "full_text")
            .order_by(Paper.id.asc())
            .all()
        )
    return [(row[0], row[1]) for row in rows]


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb"))
    parser.add_argument("--dry-run", action="store_true",
                        help="List target papers without changing anything.")
    args = parser.parse_args()

    import neurodb.connectors  # noqa: F401 — registers connector ORM models
    from neurodb.db import get_engine, init_db

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)
    targets = select_fulltext_papers(engine)
    print(f"{len(targets)} full-text papers in {args.db}")
    if args.dry_run:
        for paper_id, title in targets:
            print(f"would reconcile {paper_id}: {title}")
        return

    from neurodb.api.app import _build_runtime_stores
    from neurodb.api.routes.knowledge_library import run_post_acquisition
    from neurodb.reconciliation import register_reconciliation

    stores = _build_runtime_stores(args.db, engine)
    register_reconciliation(engine, stores["knowledge_store"], stores["chunk_store"])
    for paper_id, title in targets:
        warnings = run_post_acquisition(paper_id, engine)
        outcome = "ok" if not warnings else f"warnings: {warnings}"
        print(f"reconciled {paper_id}: {title} — {outcome}")


if __name__ == "__main__":
    main()
