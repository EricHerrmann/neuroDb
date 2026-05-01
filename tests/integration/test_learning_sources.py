import json
from sqlalchemy import create_engine, select
from neurodb.db import init_db, seed_learning_sources
from neurodb.schema import LearningSource


def test_seed_creates_augustine_row():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            row = s.execute(
                select(LearningSource).where(LearningSource.source_key == "augustine_7e")
            ).scalar_one_or_none()
    assert row is not None
    assert row.source_type == "book"
    assert row.added_by == "seed"
    content = json.loads(row.content_json)
    assert "chapters" in content
    assert content["chapters"]["12"]["title"] == "Central Visual Pathways"


def test_seed_is_idempotent():
    engine = create_engine("sqlite:///:memory:")
    init_db(engine)
    seed_learning_sources(engine)
    with engine.connect() as conn:
        from sqlalchemy.orm import Session
        with Session(conn) as s:
            count = s.query(LearningSource).filter_by(source_key="augustine_7e").count()
    assert count == 1
