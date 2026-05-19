#!/usr/bin/env python
"""Phase 3 migration: add claims, evidence_links, research_gaps; add topic_id to
research_questions; make evidence_json, datasets_json, confounds_json nullable on
research_hypotheses.

Safe to re-run. Each step checks current state before executing.

Usage:
    uv run scripts/migrate_phase3_claims_evidence.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

from neurodb.schema import Base


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    return result.scalar() > 0


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    )
    return result.scalar() > 0


def _is_nullable(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT is_nullable FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
    )
    row = result.fetchone()
    return row is not None and row[0] == "YES"


def run_migration(engine) -> None:
    # Steps 1–3 must run BEFORE create_all so that no dependent tables (e.g.
    # evidence_links, hypothesis_reviews, research_gaps) exist when we issue
    # ALTER TABLE … DROP NOT NULL on research_hypotheses.  DuckDB rejects ALTER
    # on any table that has rows in information_schema.referential_constraints
    # pointing at it.

    with engine.begin() as conn:
        # Step 1: add topic_id FK to research_questions (before create_all adds
        # any tables that reference research_questions)
        if not _column_exists(conn, "research_questions", "topic_id"):
            # DuckDB does not support ADD COLUMN with inline REFERENCES.
            # FK semantics are enforced at the ORM level.
            conn.execute(
                text("ALTER TABLE research_questions ADD COLUMN topic_id INTEGER")
            )
            print("✓ Added research_questions.topic_id")
        else:
            print("✓ research_questions.topic_id already present — skip")

        # Steps 2–4: make evidence fields nullable on research_hypotheses.
        # Must run before create_all creates evidence_links / hypothesis_reviews
        # which reference this table — DuckDB blocks ALTER on a referenced table.
        for col in ["evidence_json", "datasets_json", "confounds_json"]:
            if _table_exists(conn, "research_hypotheses") and not _is_nullable(
                conn, "research_hypotheses", col
            ):
                conn.execute(
                    text(
                        f"ALTER TABLE research_hypotheses ALTER COLUMN {col} DROP NOT NULL"
                    )
                )
                print(f"✓ research_hypotheses.{col} is now nullable")
            else:
                print(f"✓ research_hypotheses.{col} already nullable — skip")

    # Step 5: create new tables (claims, evidence_links, research_gaps) and any
    # other ORM-defined tables not yet in the DB.  Skips tables that already exist.
    Base.metadata.create_all(engine, checkfirst=True)
    print("✓ create_all complete — new tables created if missing")


if __name__ == "__main__":
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    engine = create_engine(f"duckdb:///{db_path}")
    run_migration(engine)
    print("\nMigration complete.")
