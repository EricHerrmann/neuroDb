#!/usr/bin/env python
"""Phase 2 migration: rename knowledge_sources → papers, add topics/concepts tables.

Safe to re-run. Each step checks current state before executing.

Usage:
    uv run scripts/migrate_phase2_papers_topics.py
"""
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, text

from neurodb.schema import Base


def _table_exists(conn, table: str) -> bool:
    result = conn.execute(
        text("SELECT count(*) FROM information_schema.tables WHERE table_name = :t"),
        {"t": table},
    )
    return result.scalar() > 0


def _column_exists(conn, table: str, column: str) -> bool:
    result = conn.execute(
        text(
            "SELECT count(*) FROM information_schema.columns "
            "WHERE table_name = :t AND column_name = :c"
        ),
        {"t": table, "c": column},
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
    with engine.begin() as conn:
        # Step 1: rename knowledge_sources → papers
        if _table_exists(conn, "knowledge_sources") and not _table_exists(conn, "papers"):
            conn.execute(text("ALTER TABLE knowledge_sources RENAME TO papers"))
            print("✓ Renamed knowledge_sources → papers")
        elif _table_exists(conn, "papers"):
            print("✓ papers already exists — skip rename")
        else:
            print("⚠ knowledge_sources not found and papers not found — nothing to rename")

        # Steps 2–4: add new columns to papers
        for col, ddl in [
            ("abstract", "TEXT"),
            ("authors_json", "TEXT"),
            ("year", "INTEGER"),
        ]:
            if _table_exists(conn, "papers") and not _column_exists(conn, "papers", col):
                conn.execute(text(f"ALTER TABLE papers ADD COLUMN {col} {ddl}"))
                print(f"✓ Added papers.{col}")
            else:
                print(f"✓ papers.{col} already present — skip")

    # Step 5: create new tables via create_all (topics, concepts, linking tables)
    Base.metadata.create_all(engine, checkfirst=True)
    print("✓ create_all complete — new tables created if missing")

    with engine.begin() as conn:
        # Step 6: make study_notes.index_id nullable
        if _table_exists(conn, "study_notes") and not _is_nullable(conn, "study_notes", "index_id"):
            conn.execute(text("ALTER TABLE study_notes ALTER COLUMN index_id DROP NOT NULL"))
            print("✓ study_notes.index_id is now nullable")
        else:
            print("✓ study_notes.index_id already nullable — skip")

        # Steps 7–9: add new FK columns to study_notes
        # Note: DuckDB does not support ADD COLUMN with inline REFERENCES constraint.
        # Columns are added as plain INTEGER; FK semantics are enforced at the ORM level.
        for col in ["topic_id", "concept_id", "paper_id"]:
            if _table_exists(conn, "study_notes") and not _column_exists(conn, "study_notes", col):
                conn.execute(
                    text(f"ALTER TABLE study_notes ADD COLUMN {col} INTEGER")
                )
                print(f"✓ Added study_notes.{col}")
            else:
                print(f"✓ study_notes.{col} already present — skip")

        # Step 10: drop old unique constraint (best-effort)
        try:
            conn.execute(
                text("ALTER TABLE study_notes DROP CONSTRAINT uq_study_note_index_concept")
            )
            print("✓ Dropped uq_study_note_index_concept")
        except Exception:
            print("✓ uq_study_note_index_concept already gone — skip")


if __name__ == "__main__":
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.db")
    engine = create_engine(f"duckdb:///{db_path}")
    run_migration(engine)
    print("\nMigration complete.")
