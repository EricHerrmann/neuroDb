import pytest
from sqlalchemy import create_engine
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base
from neurodb.fulltext_staging import stage_artifact, read_staging, delete_staging


def _eng():
    e = create_engine("duckdb:///:memory:"); Base.metadata.create_all(e); return e


def _art():
    return ParsedArtifact(
        [Section(label="Intro", text="abc", char_start=0, char_end=3, page=1)],
        0.6, "pdf_pymupdf", fetched_url="http://x/p.pdf")


def test_stage_read_delete_roundtrip():
    eng = _eng()
    stage_artifact(eng, source_id=7, artifact=_art())
    got = read_staging(eng, 7)
    assert got["parse_confidence"] == pytest.approx(0.6)
    assert got["sections"][0]["page"] == 1
    assert got["text_source"] == "pdf_pymupdf"
    delete_staging(eng, 7)
    assert read_staging(eng, 7) is None


def test_stage_replaces_existing():
    eng = _eng()
    stage_artifact(eng, source_id=7, artifact=_art())
    stage_artifact(eng, source_id=7, artifact=_art())
    assert read_staging(eng, 7) is not None
    # exactly one row per source
    from neurodb.schema import PaperFulltextStaging
    from neurodb.db import get_session
    with get_session(eng) as s:
        assert s.query(PaperFulltextStaging).filter_by(source_id=7).count() == 1
