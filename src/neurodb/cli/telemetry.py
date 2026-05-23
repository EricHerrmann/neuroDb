"""CLI surface for model-call telemetry and system warnings."""
from __future__ import annotations

import argparse
import os
from collections.abc import Sequence

from dotenv import load_dotenv
from sqlalchemy import Engine, text

from neurodb.config.telemetry_format import format_recorded_at
from neurodb.db import get_engine


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Inspect NeuroDb model telemetry")
    parser.add_argument("--tail", type=int, default=20, help="Number of rows per section")
    parser.add_argument("--provider", help="Filter by provider")
    parser.add_argument("--task-type", help="Filter by task type prefix")
    parser.add_argument("--warnings-only", action="store_true", help="Only show system warnings")
    parser.add_argument(
        "--db",
        default=None,
        help="Database path or SQLAlchemy URL. Defaults to NEURODB_DB_PATH or neurodb.duckdb.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    load_dotenv()
    args = build_parser().parse_args(argv)
    engine = get_engine(_db_url(args.db))
    output = render_telemetry(
        engine,
        tail=args.tail,
        provider=args.provider,
        task_type=args.task_type,
        warnings_only=args.warnings_only,
    )
    print(output)
    return 0


def render_telemetry(
    engine: Engine,
    *,
    tail: int = 20,
    provider: str | None = None,
    task_type: str | None = None,
    warnings_only: bool = False,
) -> str:
    sections: list[str] = []
    if not warnings_only:
        sections.append(
            _render_model_calls(engine, tail=tail, provider=provider, task_type=task_type)
        )
        context_section = _render_context_usage(engine, tail=tail)
        if context_section:
            sections.append(context_section)
    sections.append(
        _render_system_warnings(engine, tail=tail, provider=provider, task_type=task_type)
    )
    return "\n\n".join(sections)


def _render_context_usage(engine: Engine, *, tail: int) -> str | None:
    rows = _query_context_usage(engine, tail=tail)
    if not rows:
        return None
    lines = [f"Context Usage (last {tail} agent turns)", "-" * 72]
    for row in rows:
        p = row.context_papers_count or 0
        n = row.context_notes_count or 0
        c = row.context_claims_count or 0
        d = row.context_datasets_count or 0
        g = row.context_gap_count or 0
        counts = f"{p}p / {n}n / {c}c / {d}d"
        gap_str = f"  {g} gaps" if g else ""
        mode_str = row.mode or "unknown"
        lines.append(
            f"{format_recorded_at(row.recorded_at):17}  "
            f"{row.task_type:28}  "
            f"{mode_str:12}  "
            f"{counts}{gap_str}"
        )
    return "\n".join(lines)


def _query_context_usage(engine: Engine, *, tail: int) -> list:
    sql = text("""
        SELECT recorded_at, task_type, mode,
               context_papers_count, context_notes_count,
               context_claims_count, context_datasets_count, context_gap_count
        FROM model_call_log
        WHERE context_papers_count IS NOT NULL
           OR context_notes_count IS NOT NULL
           OR context_claims_count IS NOT NULL
           OR context_datasets_count IS NOT NULL
           OR context_gap_count IS NOT NULL
        ORDER BY recorded_at DESC
        LIMIT :limit
    """)
    try:
        with engine.connect() as conn:
            return list(conn.execute(sql, {"limit": tail}).fetchall())
    except Exception:
        return []


def _render_model_calls(
    engine: Engine,
    *,
    tail: int,
    provider: str | None,
    task_type: str | None,
) -> str:
    rows = _query_model_calls(engine, tail=tail, provider=provider, task_type=task_type)
    lines = [f"Model Call Log (last {tail})", "-" * 72]
    if not rows:
        lines.append("No model calls found.")
        return "\n".join(lines)
    for row in rows:
        tokens = _format_tokens(row.input_tokens, row.output_tokens)
        cost = _format_cost(row.estimated_cost_usd)
        lines.append(
            f"{format_recorded_at(row.recorded_at):17}  "
            f"{row.task_type:28}  "
            f"{row.provider} / {row.model:24}  "
            f"{tokens:18}  {cost}"
        )
    return "\n".join(lines)


def _render_system_warnings(
    engine: Engine,
    *,
    tail: int,
    provider: str | None,
    task_type: str | None,
) -> str:
    rows = _query_system_warnings(engine, tail=tail, provider=provider, task_type=task_type)
    lines = [f"System Warnings (last {tail})", "-" * 72]
    if not rows:
        lines.append("No system warnings found.")
        return "\n".join(lines)
    for row in rows:
        requested = row.requested_provider or "(none)"
        selected = row.selected_provider or "(none)"
        lines.append(
            f"{format_recorded_at(row.recorded_at):17}  "
            f"[{row.severity:<7}]  "
            f"{row.warning_type:20}  "
            f"{row.task_type:28}  "
            f"{requested} -> {selected}  "
            f"{row.message}"
        )
    return "\n".join(lines)


def _query_model_calls(
    engine: Engine,
    *,
    tail: int,
    provider: str | None,
    task_type: str | None,
) -> list:
    clauses = []
    params: dict[str, object] = {"limit": tail}
    if provider:
        clauses.append("provider = :provider")
        params["provider"] = provider
    if task_type:
        clauses.append("task_type LIKE :task_type")
        params["task_type"] = f"{task_type}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = text(f"""
        SELECT recorded_at, task_type, provider, model, input_tokens, output_tokens,
               estimated_cost_usd
        FROM model_call_log
        {where}
        ORDER BY recorded_at DESC
        LIMIT :limit
    """)
    try:
        with engine.connect() as conn:
            return list(conn.execute(sql, params).fetchall())
    except Exception:
        return []


def _query_system_warnings(
    engine: Engine,
    *,
    tail: int,
    provider: str | None,
    task_type: str | None,
) -> list:
    clauses = []
    params: dict[str, object] = {"limit": tail}
    if provider:
        clauses.append("(requested_provider = :provider OR selected_provider = :provider)")
        params["provider"] = provider
    if task_type:
        clauses.append("task_type LIKE :task_type")
        params["task_type"] = f"{task_type}%"
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    sql = text(f"""
        SELECT recorded_at, warning_type, severity, task_type, requested_provider,
               selected_provider, message
        FROM system_warnings
        {where}
        ORDER BY recorded_at DESC
        LIMIT :limit
    """)
    try:
        with engine.connect() as conn:
            return list(conn.execute(sql, params).fetchall())
    except Exception:
        return []


def _format_tokens(input_tokens: int | None, output_tokens: int | None) -> str:
    in_text = f"{input_tokens:,}" if input_tokens is not None else "?"
    out_text = f"{output_tokens:,}" if output_tokens is not None else "?"
    return f"{in_text} in / {out_text} out"


def _format_cost(value: float | None) -> str:
    if value is None:
        return "~$?"
    return f"~${value:.4f}"


def _db_url(value: str | None) -> str:
    db_value = value or os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    if "://" in db_value:
        return db_value
    return f"duckdb:///{db_value}"


if __name__ == "__main__":
    raise SystemExit(main())
