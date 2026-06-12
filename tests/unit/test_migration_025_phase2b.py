from sqlalchemy import create_engine, inspect, text
from neurodb.db import _MIGRATIONS, _migration_025_phase2b  # noqa: F401


def test_migration_025_adds_columns_and_staging():
    eng = create_engine("duckdb:///:memory:")
    with eng.connect() as conn:
        conn.execute(text("CREATE TABLE papers (id INTEGER)"))
        conn.execute(text("CREATE TABLE paper_chunks (id INTEGER)"))
        conn.commit()
        _MIGRATIONS[25](conn)
        conn.commit()
    cols_papers = {c["name"] for c in inspect(eng).get_columns("papers")}
    cols_chunks = {c["name"] for c in inspect(eng).get_columns("paper_chunks")}
    assert "parse_confidence" in cols_papers
    assert "page" in cols_chunks
    assert "paper_fulltext_staging" in inspect(eng).get_table_names()
