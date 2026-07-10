"""Tests for the one-time full-text reconcile CLI (dry-run path only; the live
path builds real Chroma stores + embedder and is covered by the manual gate)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.cli.reconcile_fulltext import select_fulltext_papers
from neurodb.db import get_session
from neurodb.schema import Base, Paper


def test_select_fulltext_papers_returns_only_full_text_tier_ordered_by_id():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    # Explicit ids inserted OUT of ascending-id order so that insertion order
    # (Full C, Abs B, Full A) differs from the expected ascending-id result
    # (Full A id=10, Full C id=30). This makes the assertion discriminating:
    # deleting .order_by(Paper.id.asc()) from the implementation would return
    # the rows in insertion order and fail this test.
    with get_session(engine) as session:
        for paper_id, title, tier in [(30, "Full C", "full_text"),
                                      (20, "Abs B", "abstract"),
                                      (10, "Full A", "full_text")]:
            session.add(Paper(id=paper_id, title=title,
                              normalized_title=title.lower(),
                              source_type="paper", topic_context="t",
                              status="approved", queued_at="2026-01-01T00:00:00",
                              data_tier=tier))
    rows = select_fulltext_papers(engine)
    # Excludes the "abstract" tier and returns full_text rows ordered by id asc.
    assert rows == [(10, "Full A"), (30, "Full C")]
