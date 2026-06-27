from sqlalchemy import create_engine, text

from neurodb import db as dbpkg


def test_migration_026_adds_provider_counts_json_column():
    engine = create_engine("duckdb:///:memory:")
    dbpkg.init_db(engine)  # runs create_all + all migrations
    with engine.connect() as conn:
        cols = conn.execute(text("PRAGMA table_info('literature_searches')")).fetchall()
    names = {row[1] for row in cols}
    assert "provider_counts_json" in names


def test_migration_026_registered():
    assert 26 in dbpkg._MIGRATIONS
