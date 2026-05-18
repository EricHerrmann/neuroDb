import pytest
from datetime import datetime, timezone
from sqlalchemy import create_engine, inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Concept, Topic


def _now():
    return datetime.now(timezone.utc).isoformat()


@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(eng)
    yield eng
    eng.dispose()


def test_topic_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("topics")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_concept_table_has_required_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("concepts")}
    assert {"id", "name", "description", "status", "created_at", "updated_at"}.issubset(cols)


def test_topic_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Topic(name="stroke recovery", status="active", created_at=now, updated_at=now))
            s.commit()


def test_concept_name_is_unique(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
        s.commit()
    with pytest.raises(IntegrityError):
        with Session(engine) as s:
            s.add(Concept(name="neuroplasticity", status="active", created_at=now, updated_at=now))
            s.commit()


def test_topic_description_is_optional(engine):
    now = _now()
    with Session(engine) as s:
        s.add(Topic(name="cortical remapping", status="active", created_at=now, updated_at=now))
        s.commit()
