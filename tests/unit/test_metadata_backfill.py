"""Tests for backfill field selection and orchestration (no network)."""
from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.db import get_session
from neurodb.metadata_backfill import (
    backfill_paper_metadata,
    select_backfill_fields,
)
from neurodb.metadata_lookup import PaperMetadata
from neurodb.schema import Base, Paper

_FOUND = PaperMetadata(
    source="semantic_scholar",
    authors=["J. Hopfield"],
    abstract="Collective properties emerge.",
    year=1982,
    doi="10.1073/pnas.79.8.2554",
    url="https://doi.org/10.1073/pnas.79.8.2554",
)


def _engine():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    return engine


def _add_paper(engine, **overrides) -> int:
    values = dict(title="Hopfield 1982", normalized_title="hopfield 1982",
                  source_type="paper", topic_context="memory", status="approved",
                  queued_at="2026-01-01T00:00:00")
    values.update(overrides)
    with get_session(engine) as session:
        paper = Paper(**values)
        session.add(paper)
        session.flush()
        return paper.id


class _StubClient:
    def __init__(self, found):
        self.found = found
        self.calls: list[dict] = []

    def lookup(self, *, doi=None, title=None):
        self.calls.append({"doi": doi, "title": title})
        return self.found


def test_select_fills_only_null_fields():
    current = {"authors_json": None, "abstract": "curated abstract",
               "year": None, "doi": "10.9999/curated", "url": None}
    fields = select_backfill_fields(current, _FOUND)
    assert fields == {
        "authors_json": json.dumps(["J. Hopfield"]),
        "year": 1982,
        "url": "https://doi.org/10.1073/pnas.79.8.2554",
    }  # abstract and doi are curated → untouched


def test_select_returns_empty_when_everything_curated():
    current = {"authors_json": "[\"X\"]", "abstract": "a", "year": 2000,
               "doi": "10.1/x", "url": "https://x"}
    assert select_backfill_fields(current, _FOUND) == {}


def test_backfill_uses_doi_when_present_and_writes_via_set_fields():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1073/pnas.79.8.2554")
    client = _StubClient(_FOUND)
    written: dict = {}
    result = backfill_paper_metadata(
        engine, paper_id, metadata_client=client,
        set_fields=lambda **f: written.update(f),
    )
    assert client.calls == [{"doi": "10.1073/pnas.79.8.2554", "title": None}]
    assert written["authors_json"] == json.dumps(["J. Hopfield"])
    assert result.filled["authors_json"] == "semantic_scholar"
    assert result.warnings == []


def test_backfill_falls_back_to_title_when_no_doi():
    engine = _engine()
    paper_id = _add_paper(engine, doi=None)
    client = _StubClient(_FOUND)
    backfill_paper_metadata(engine, paper_id, metadata_client=client,
                            set_fields=lambda **f: None)
    assert client.calls == [{"doi": None, "title": "Hopfield 1982"}]


def test_backfill_lookup_empty_records_warning_and_writes_nothing():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1/x")
    written: dict = {}
    result = backfill_paper_metadata(
        engine, paper_id, metadata_client=_StubClient(None),
        set_fields=lambda **f: written.update(f),
    )
    assert written == {}
    assert result.filled == {} and len(result.warnings) == 1


def test_backfill_write_failure_becomes_warning():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1/x")

    def _boom(**fields):
        raise RuntimeError("duplicate doi")

    result = backfill_paper_metadata(engine, paper_id,
                                     metadata_client=_StubClient(_FOUND),
                                     set_fields=_boom)
    assert result.filled == {}
    assert any("failed" in w for w in result.warnings)


def test_backfill_is_idempotent():
    engine = _engine()
    paper_id = _add_paper(engine, doi="10.1073/pnas.79.8.2554")
    client = _StubClient(_FOUND)

    def _apply(**fields):
        with get_session(engine) as session:  # sqlite: direct write is fine in tests
            row = session.get(Paper, paper_id)
            for key, value in fields.items():
                setattr(row, key, value)

    first = backfill_paper_metadata(engine, paper_id, metadata_client=client,
                                    set_fields=_apply)
    second = backfill_paper_metadata(engine, paper_id, metadata_client=client,
                                     set_fields=_apply)
    assert first.filled != {}
    assert second.filled == {} and second.values == {}  # nothing left to fill
