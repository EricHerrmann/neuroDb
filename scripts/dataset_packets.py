#!/usr/bin/env python
"""CLI: inspect dataset research packets and coverage."""
import argparse
import json

from dotenv import load_dotenv

load_dotenv()

from neurodb.dataset_packets import (  # noqa: E402
    backfill_dataset_research_packets,
    get_dataset_packet_coverage,
    get_dataset_packet_summary,
)
from neurodb.db import get_engine, init_db  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect dataset research packets")
    parser.add_argument("--db", default="neurodb.duckdb")
    subparsers = parser.add_subparsers(dest="command", required=True)

    coverage = subparsers.add_parser("coverage", help="Show source-level packet coverage")
    coverage.add_argument("--json", action="store_true", help="Emit JSON instead of table text")

    show = subparsers.add_parser("show", help="Show packet summaries")
    show.add_argument("--source", default=None)
    show.add_argument("--limit", type=int, default=20)
    show.add_argument("--json", action="store_true", help="Emit JSON instead of table text")

    backfill = subparsers.add_parser(
        "backfill",
        help="Create sparse packets for indexed datasets missing packets",
    )

    args = parser.parse_args()
    engine = get_engine(f"duckdb:///{args.db}")
    init_db(engine)

    if args.command == "coverage":
        rows = get_dataset_packet_coverage(engine)
        _print_json_or_table(rows, args.json, _format_coverage)
    elif args.command == "show":
        rows = get_dataset_packet_summary(engine, source=args.source, limit=args.limit)
        _print_json_or_table(rows, args.json, _format_summary)
    elif args.command == "backfill":
        count = backfill_dataset_research_packets(engine)
        print(f"Backfilled {count} dataset research packet(s).")


def _print_json_or_table(rows: list[dict], as_json: bool, formatter) -> None:
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
        return
    print(formatter(rows))


def _format_coverage(rows: list[dict]) -> str:
    if not rows:
        return "No dataset research packets found."
    lines = [
        "source | total | states | doi/paper | summary | topics | assets | avg missing",
        "---|---:|---|---:|---:|---:|---:|---:",
    ]
    for row in rows:
        states = ", ".join(f"{k}:{v}" for k, v in row["states"].items()) or "-"
        lines.append(
            " | ".join(
                [
                    row["source"],
                    str(row["total_packets"]),
                    states,
                    str(row["doi_or_paper_url"]),
                    str(row["source_summary"]),
                    str(row["topics"]),
                    str(row["asset_manifest"]),
                    str(row["avg_missing_context_count"]),
                ]
            )
        )
    return "\n".join(lines)


def _format_summary(rows: list[dict]) -> str:
    if not rows:
        return "No dataset research packets found."
    blocks = []
    for row in rows:
        missing = ", ".join(row["missing_context"]) or "-"
        supported = ", ".join(row["supported_workflows"]) or "-"
        unsupported = ", ".join(row["unsupported_workflows"]) or "-"
        blocks.append(
            "\n".join(
                [
                    f"{row['source']}:{row['source_id']} - {row['usefulness_state']}",
                    f"  title: {row['title'] or '-'}",
                    f"  doi: {row['doi'] or '-'}",
                    f"  missing: {missing}",
                    f"  supported: {supported}",
                    f"  unsupported: {unsupported}",
                ]
            )
        )
    return "\n\n".join(blocks)


if __name__ == "__main__":
    main()

