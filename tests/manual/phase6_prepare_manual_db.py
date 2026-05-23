#!/usr/bin/env python
"""Prepare a loaded disposable DB copy for Config Control Phase 6 manual tests."""
from __future__ import annotations

import argparse
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Copy the primary NeuroDb DB and Chroma store to disposable Phase 6 paths."
    )
    parser.add_argument("--source-db", default="neurodb.duckdb")
    parser.add_argument("--target-db", default="/tmp/neurodb_phase6_manual.duckdb")
    parser.add_argument(
        "--force",
        action="store_true",
        help="Replace an existing target DB and target Chroma directory.",
    )
    args = parser.parse_args()

    source_db = Path(args.source_db)
    target_db = Path(args.target_db)
    source_chroma = _chroma_path_for_db(source_db)
    target_chroma = _chroma_path_for_db(target_db)

    if not source_db.exists():
        raise SystemExit(f"Source DB not found: {source_db}")
    if target_db.exists() and not args.force:
        raise SystemExit(f"Target DB already exists: {target_db}; rerun with --force to replace it")
    if target_chroma.exists() and not args.force:
        raise SystemExit(
            f"Target Chroma directory already exists: {target_chroma}; rerun with --force to replace it"
        )

    target_db.parent.mkdir(parents=True, exist_ok=True)
    if target_db.exists():
        target_db.unlink()
    if target_chroma.exists():
        shutil.rmtree(target_chroma)

    shutil.copy2(source_db, target_db)
    print(f"Copied DB: {source_db} -> {target_db}")

    if source_chroma.exists():
        shutil.copytree(source_chroma, target_chroma)
        print(f"Copied Chroma: {source_chroma} -> {target_chroma}")
    else:
        print(f"No Chroma directory found at {source_chroma}; copied DB only")

    print("PASS: Phase 6 disposable manual DB is ready.")
    return 0


def _chroma_path_for_db(db_path: Path) -> Path:
    text = str(db_path)
    if text.endswith(".duckdb"):
        return Path(text.replace(".duckdb", "_chroma"))
    return Path(f"{text}_chroma")


if __name__ == "__main__":
    raise SystemExit(main())
