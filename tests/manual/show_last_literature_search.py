"""Inspect the most recent literature_searches audit rows (manual-test support).

Usage: uv run python tests/manual/show_last_literature_search.py [N]
Prints the latest N rows (default 1): query, searched_at, provider_counts_json,
and the legacy pubmed/semantic_scholar/arxiv counts — so the manual audit step
can confirm provider_counts_json is populated and the legacy columns match it.

Only the agent's search_literature tool writes these rows (via
LiteratureSearchClient.search). The connectivity helper
(check_literature_providers.py) calls providers directly and logs nothing.

NOTE: DuckDB is single-writer. Stop the FastAPI server before running this, or
it will fail to open the locked DB file.
"""
from __future__ import annotations

import json
import os
import sys

from dotenv import load_dotenv


def main() -> int:
    load_dotenv()
    db_path = os.environ.get("NEURODB_DB_PATH", "neurodb.duckdb")
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 1

    import duckdb

    try:
        conn = duckdb.connect(db_path, read_only=True)
    except Exception as exc:
        print(f"Could not open {db_path}: {exc}")
        print("If a FastAPI server is running it holds the DuckDB lock — stop it and retry.")
        return 1

    rows = conn.execute(
        "select id, query, searched_at, provider_counts_json, "
        "pubmed_count, semantic_scholar_count, arxiv_count "
        "from literature_searches order by id desc limit ?",
        [n],
    ).fetchall()

    if not rows:
        print("No literature_searches rows. Run an agent search_literature query first "
              "(the connectivity helper does NOT log a row).")
        return 1

    ok = True
    for (id_, query, searched_at, counts_json, pm, s2, ax) in rows:
        counts = json.loads(counts_json) if counts_json else {}
        print(f"#{id_}  {searched_at}")
        print(f"  query: {query}")
        print(f"  provider_counts_json: {counts}")
        print(f"  legacy: pubmed={pm} semantic_scholar={s2} arxiv={ax}")
        if not counts:
            print("  WARN: provider_counts_json is empty/null")
            ok = False
        for name, legacy_val in (("pubmed", pm), ("semantic_scholar", s2), ("arxiv", ax)):
            if counts.get(name, 0) != legacy_val:
                print(f"  WARN: legacy {name}={legacy_val} != json {counts.get(name, 0)}")
                ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
