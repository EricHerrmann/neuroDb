"""Print DuckDB + Chroma state for one paper: papers row, event_log rows,
summary-index metadata, chunk metadata/count.

Usage: uv run python tests/manual/check_library_reconciliation.py SOURCE_ID [--db PATH]
Read-only; used by docs/testsPlans/manualTestPlan_knowledge_library_augmentation.md.
NOTE: imports EventLog, which exists once the implementation tasks land.
"""
from __future__ import annotations

import argparse
import json
import os

from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser()
    parser.add_argument("source_id", type=int)
    parser.add_argument("--db", default=os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb"))
    args = parser.parse_args()

    import chromadb

    import neurodb.connectors  # noqa: F401 — registers connector ORM models
    from neurodb.api.app import _chroma_path_for_db
    from neurodb.db import get_engine, get_session
    from neurodb.schema import EventLog, Paper

    engine = get_engine(f"duckdb:///{args.db}")
    with get_session(engine) as session:
        paper = session.get(Paper, args.source_id)
        if paper is None:
            raise SystemExit(f"paper {args.source_id} not found")
        print("papers row:", json.dumps({
            "id": paper.id, "title": paper.title, "doi": paper.doi, "url": paper.url,
            "authors_json": paper.authors_json,
            "abstract": (paper.abstract or "")[:120],
            "year": paper.year, "data_tier": paper.data_tier,
            "currency_status": paper.currency_status,
        }, indent=2))
        rows = (
            session.query(EventLog)
            .filter(EventLog.entity_id == str(args.source_id))
            .order_by(EventLog.id.asc())
            .all()
        )
        for row in rows:
            print(f"event_log: {row.event_name} handler={row.handler} "
                  f"status={row.status} at={row.created_at} detail={row.detail_json}")

    client = chromadb.PersistentClient(path=_chroma_path_for_db(args.db))
    summary = client.get_collection("knowledge_library").get(
        ids=[f"knowledge_source:{args.source_id}"]
    )
    print("summary metadata:", json.dumps(summary.get("metadatas") or [], indent=2))
    chunks = client.get_collection("knowledge_chunks").get(
        where={"paper_id": str(args.source_id)}
    )
    metadatas = chunks.get("metadatas") or []
    print(f"chunk count: {len(chunks.get('ids') or [])}")
    if metadatas:
        print("first chunk metadata:", json.dumps(metadatas[0], indent=2))


if __name__ == "__main__":
    main()
