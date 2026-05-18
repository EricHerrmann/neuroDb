#!/usr/bin/env python
"""Manual helper: verify dataset research packet integrity for a local DB."""
import argparse
import sys

from dotenv import load_dotenv
from sqlalchemy import func, select
from sqlalchemy.orm import Session

load_dotenv()

from neurodb.db import get_engine, init_db  # noqa: E402
from neurodb.schema import DatasetIndex, DatasetResearchPacket  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify dataset research packets")
    parser.add_argument("--db", default="neurodb.duckdb")
    args = parser.parse_args()

    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)

    with Session(engine) as session:
        dataset_count = session.scalar(select(func.count(DatasetIndex.id))) or 0
        packet_count = session.scalar(select(func.count(DatasetResearchPacket.id))) or 0
        duplicate_keys = session.execute(
            select(
                DatasetResearchPacket.source,
                DatasetResearchPacket.source_id,
                func.count(DatasetResearchPacket.id),
            )
            .group_by(DatasetResearchPacket.source, DatasetResearchPacket.source_id)
            .having(func.count(DatasetResearchPacket.id) > 1)
        ).all()
        incomplete_packets = session.execute(
            select(DatasetResearchPacket).where(
                (DatasetResearchPacket.usefulness_state == "")
                | (DatasetResearchPacket.missing_context_json == "")
                | (DatasetResearchPacket.provenance_json == "")
                | (DatasetResearchPacket.harvested_at == "")
            )
        ).scalars().all()

    errors = []
    if dataset_count == 0:
        errors.append("No datasets found; run an ingest before verification.")
    if packet_count != dataset_count:
        errors.append(f"Expected {dataset_count} packet(s), found {packet_count}.")
    if duplicate_keys:
        errors.append(f"Duplicate packet keys found: {duplicate_keys}")
    if incomplete_packets:
        keys = [f"{p.source}:{p.source_id}" for p in incomplete_packets]
        errors.append(f"Incomplete packet fields for: {keys}")

    if errors:
        for error in errors:
            print(f"FAIL: {error}", file=sys.stderr)
        return 1

    print(f"PASS: {packet_count} dataset research packet(s) for {dataset_count} dataset(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

