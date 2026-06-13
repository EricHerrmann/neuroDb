import pytest
from sqlalchemy import create_engine
from neurodb.schema import Base, Paper, PaperChunk, PaperFulltextStaging


def test_phase2b_models_create_and_roundtrip():
    eng = create_engine("duckdb:///:memory:")
    Base.metadata.create_all(eng)
    from sqlalchemy.orm import Session
    with Session(eng) as s:
        s.add(PaperFulltextStaging(
            source_id=1, text_source="pdf_docling", parse_confidence=0.7,
            fetched_url="http://x/p.pdf", artifact_json="{}", created_at="t",
        ))
        s.commit()
        row = s.query(PaperFulltextStaging).one()
        # DuckDB FLOAT is 32-bit; use approx for the float comparison.
        assert row.source_id == 1
        assert row.parse_confidence == pytest.approx(0.7, rel=1e-5)
    assert Paper.__table__.c.parse_confidence is not None
    assert PaperChunk.__table__.c.page is not None
