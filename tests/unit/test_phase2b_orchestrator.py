from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base, Paper, PaperFulltextStaging
from neurodb import phase2b


def _eng_with_paper():
    e = create_engine("duckdb:///:memory:"); Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Paper(id=1, title="P", normalized_title="p", source_type="paper",
                    topic_context="x", status="approved", queued_at="t",
                    data_tier="abstract", currency_status="current"))
        s.commit()
    return e


def _spy():
    calls = []
    def fn(**kw): calls.append(kw)
    return fn, calls


def test_high_confidence_auto_commits_and_verifies():
    eng = _eng_with_paper(); commit, calls = _spy()
    art = ParsedArtifact([Section(None, "memory " * 80, 0, 600, page=1)], 0.95, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=lambda: art)
    assert len(calls) == 1
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "verified"


def test_medium_confidence_stages_for_review_no_commit():
    eng = _eng_with_paper(); commit, calls = _spy()
    art = ParsedArtifact([Section(None, "memory " * 80, 0, 600, page=1)], 0.6, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=lambda: art)
    assert calls == []
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "needs_review"
        assert s.query(PaperFulltextStaging).filter_by(source_id=1).count() == 1


def test_low_confidence_rejected():
    eng = _eng_with_paper(); commit, calls = _spy()
    art = ParsedArtifact([Section(None, "x", 0, 1)], 0.1, "pdf_pymupdf")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=lambda: art)
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "unavailable"


def test_parse_error_sets_failed():
    eng = _eng_with_paper(); commit, _ = _spy()
    def boom(): raise RuntimeError("both parsers failed")
    phase2b.run_acquisition(source_id=1, engine=eng, commit_chunks=commit, parse=boom)
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "failed"
