import pytest
from sqlalchemy import create_engine, inspect
from sqlalchemy.pool import StaticPool

from neurodb.schema import Base, Paper


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


def test_paper_table_exists(engine):
    assert "papers" in inspect(engine).get_table_names()


def test_knowledge_sources_table_does_not_exist_in_new_schema(engine):
    assert "knowledge_sources" not in inspect(engine).get_table_names()


def test_paper_has_original_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("papers")}
    assert {
        "id", "title", "normalized_title", "doi", "url", "source_type",
        "topic_context", "status", "queued_at", "reviewed_at", "summary", "chroma_id",
    }.issubset(cols)


def test_paper_has_new_columns(engine):
    cols = {c["name"] for c in inspect(engine).get_columns("papers")}
    assert {"abstract", "authors_json", "year"}.issubset(cols)


def test_paper_class_importable():
    from neurodb.schema import Paper
    assert Paper.__tablename__ == "papers"
