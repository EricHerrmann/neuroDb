"""Phase 2b acquisition orchestrator: parse -> gate -> terminal state.

`run_acquisition` is the body of the async job. `parse`, `commit_chunks`, and `set_fields` are
injected so unit tests need no network/ML/Chroma and so the route can supply the FK-safe field
setter. `set_fields` defaults to a bare UPDATE (fine for tests with no FK-referenced children).
"""
from __future__ import annotations

from collections.abc import Callable

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.fulltext_staging import stage_artifact
from neurodb.fulltext_types import ParsedArtifact
from neurodb.parse_quality import gate
from neurodb.schema import Paper


def _default_set(engine: Engine, source_id: int, **fields) -> None:
    with get_session(engine) as session:
        paper = session.get(Paper, source_id)
        for k, v in fields.items():
            setattr(paper, k, v)


def run_acquisition(*, source_id: int, engine: Engine,
                    parse: Callable[[], ParsedArtifact | None],
                    commit_chunks: Callable[..., None],
                    set_fields: Callable[..., None] | None = None) -> None:
    """Run one acquisition attempt and write the terminal full_text_status."""
    set_fields = set_fields or (lambda **f: _default_set(engine, source_id, **f))
    try:
        artifact = parse()
    except Exception:
        set_fields(full_text_status="failed", text_source=None)
        return
    if artifact is None:
        set_fields(full_text_status="unavailable")
        return
    decision = gate(artifact.parse_confidence)
    if decision == "accept":
        with get_session(engine) as s:
            paper = s.get(Paper, source_id)
            title, year, currency = paper.title, paper.year, paper.currency_status
        commit_chunks(source_id=source_id, sections=artifact.sections,
                      text_source=artifact.text_source, title=title, year=year, currency=currency)
        set_fields(full_text_status="verified", text_source=artifact.text_source,
                   data_tier="full_text", parse_confidence=artifact.parse_confidence)
    elif decision == "review":
        stage_artifact(engine, source_id=source_id, artifact=artifact)
        set_fields(full_text_status="needs_review", parse_confidence=artifact.parse_confidence)
    else:
        set_fields(full_text_status="unavailable", parse_confidence=artifact.parse_confidence)
