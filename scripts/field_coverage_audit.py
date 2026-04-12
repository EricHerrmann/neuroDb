#!/usr/bin/env python
"""Audit field coverage across sources — run after Phase 3 ingest.

Usage:
    uv run scripts/field_coverage_audit.py --db neurodb.db
"""
import argparse
from sqlalchemy import text
from neurodb.db import get_engine, init_db, create_views

COVERAGE_QUERY = """
SELECT
    source,
    COUNT(*) AS total,
    SUM(CASE WHEN doi IS NOT NULL THEN 1 ELSE 0 END) AS has_doi,
    SUM(CASE WHEN modality IS NOT NULL THEN 1 ELSE 0 END) AS has_modality,
    SUM(CASE WHEN n_subjects IS NOT NULL AND n_subjects > 0 THEN 1 ELSE 0 END) AS has_n_subjects,
    SUM(CASE WHEN description IS NOT NULL AND description != '' THEN 1 ELSE 0 END) AS has_description
FROM v_all_datasets
GROUP BY source
ORDER BY source;
"""

SUMMARY_QUERY = "SELECT * FROM v_dataset_summary ORDER BY source, modality;"

DOI_OVERLAP_QUERY = """
SELECT d1.source AS source_a, d2.source AS source_b, d1.doi
FROM v_all_datasets d1
JOIN v_all_datasets d2 ON d1.doi = d2.doi AND d1.source < d2.source
WHERE d1.doi IS NOT NULL
ORDER BY d1.doi;
"""


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", default="neurodb.db")
    args = parser.parse_args()

    engine = get_engine(f"sqlite:///{args.db}")
    init_db(engine)
    create_views(engine)

    with engine.connect() as conn:
        print("=== Field Coverage by Source ===")
        rows = conn.execute(text(COVERAGE_QUERY)).fetchall()
        headers = ["source", "total", "has_doi", "has_modality", "has_n_subjects", "has_description"]
        print("\t".join(headers))
        for row in rows:
            print("\t".join(str(v) for v in row))

        print("\n=== Dataset Summary (v_dataset_summary) ===")
        rows = conn.execute(text(SUMMARY_QUERY)).fetchall()
        print("source\tmodality\tn_datasets\ttotal_subjects")
        for row in rows:
            print("\t".join(str(v) for v in row))

        print("\n=== DOI Overlap Between Sources ===")
        rows = conn.execute(text(DOI_OVERLAP_QUERY)).fetchall()
        if rows:
            print("source_a\tsource_b\tdoi")
            for row in rows:
                print("\t".join(str(v) for v in row))
        else:
            print("(no DOI overlap found between sources)")


if __name__ == "__main__":
    main()
