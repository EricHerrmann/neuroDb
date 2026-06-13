"""Integration test: Phase 2b acquisition pipeline — real pdf_parser, real gate, in-memory DuckDB.

No network, no ML, no Chroma. Covers three terminal outcomes:
  1. High-confidence PDF  -> verified + commit_chunks called once.
  2. Medium-confidence    -> needs_review + staged + commit_chunks NOT called (trustworthiness invariant).
  3. None parse result    -> unavailable.
"""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from neurodb.chunking import Section
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import Base, Paper, PaperFulltextStaging
from neurodb import phase2b
from neurodb.pdf_parser import parse_pdf


def _eng_with_paper():
    e = create_engine("duckdb:///:memory:")
    Base.metadata.create_all(e)
    with Session(e) as s:
        s.add(Paper(id=1, title="P", normalized_title="p", source_type="paper",
                    topic_context="x", status="approved", queued_at="t",
                    data_tier="abstract", currency_status="current"))
        s.commit()
    return e


def _spy():
    calls = []
    def fn(**kw):
        calls.append(kw)
    return fn, calls


def test_real_pdf_parse_auto_verifies_and_commits():
    eng = _eng_with_paper()
    commit, calls = _spy()
    with open("tests/fixtures/sample.pdf", "rb") as f:
        data = f.read()

    artifact = parse_pdf(data)
    print(f"\n[fixture parse_confidence={artifact.parse_confidence:.4f}]")

    phase2b.run_acquisition(
        source_id=1,
        engine=eng,
        commit_chunks=commit,
        parse=lambda: parse_pdf(data),
    )
    # clean fixture prose -> high confidence -> accept -> verified, chunks committed once
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "verified"
    assert len(calls) == 1
    committed = calls[0]
    assert committed["text_source"] == "pdf_pymupdf"
    assert committed["sections"][0].page == 1  # page anchor flowed through


def test_medium_confidence_stages_and_never_commits():
    eng = _eng_with_paper()
    commit, calls = _spy()
    art = ParsedArtifact([Section(None, "memory " * 80, 0, 600, page=2)], 0.6, "pdf_pymupdf")
    phase2b.run_acquisition(
        source_id=1,
        engine=eng,
        commit_chunks=commit,
        parse=lambda: art,
    )
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "needs_review"
        assert s.query(PaperFulltextStaging).filter_by(source_id=1).count() == 1
    assert calls == []  # invariant: staged text is never committed/embedded


def test_no_source_is_unavailable():
    eng = _eng_with_paper()
    commit, calls = _spy()
    phase2b.run_acquisition(
        source_id=1,
        engine=eng,
        commit_chunks=commit,
        parse=lambda: None,
    )
    with Session(eng) as s:
        assert s.get(Paper, 1).full_text_status == "unavailable"
    assert calls == []
