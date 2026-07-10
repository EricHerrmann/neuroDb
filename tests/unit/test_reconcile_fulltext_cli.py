"""Tests for the one-time full-text reconcile CLI (dry-run path only; the live
path builds real Chroma stores + embedder and is covered by the manual gate)."""
from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.pool import StaticPool

from neurodb.cli.reconcile_fulltext import select_fulltext_papers
from neurodb.db import get_session
from neurodb.schema import Base, Paper


def test_select_fulltext_papers_returns_only_full_text_tier():
    engine = create_engine("sqlite:///:memory:",
                           connect_args={"check_same_thread": False},
                           poolclass=StaticPool)
    Base.metadata.create_all(engine)
    with get_session(engine) as session:
        for title, tier in [("Full A", "full_text"), ("Abs B", "abstract"),
                            ("Full C", "full_text")]:
            session.add(Paper(title=title, normalized_title=title.lower(),
                              source_type="paper", topic_context="t",
                              status="approved", queued_at="2026-01-01T00:00:00",
                              data_tier=tier))
    rows = select_fulltext_papers(engine)
    assert [title for _pid, title in rows] == ["Full A", "Full C"]
