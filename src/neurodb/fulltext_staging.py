"""Staging-table CRUD for medium-confidence parses awaiting review (Phase 2b)."""
from __future__ import annotations

import json
from datetime import UTC, datetime

from sqlalchemy import Engine

from neurodb.db import get_session
from neurodb.fulltext_types import ParsedArtifact
from neurodb.schema import PaperFulltextStaging


def _artifact_to_json(artifact: ParsedArtifact) -> str:
    return json.dumps({
        "sections": [
            {"label": s.label, "text": s.text, "char_start": s.char_start,
             "char_end": s.char_end, "page": s.page}
            for s in artifact.sections
        ],
    })


def stage_artifact(engine: Engine, *, source_id: int, artifact: ParsedArtifact) -> None:
    with get_session(engine) as session:
        session.query(PaperFulltextStaging).filter_by(source_id=source_id).delete()
        session.add(PaperFulltextStaging(
            source_id=source_id,
            text_source=artifact.text_source,
            parse_confidence=artifact.parse_confidence,
            fetched_url=artifact.fetched_url,
            artifact_json=_artifact_to_json(artifact),
            created_at=datetime.now(UTC).isoformat(),
        ))


def read_staging(engine: Engine, source_id: int) -> dict | None:
    with get_session(engine) as session:
        row = session.query(PaperFulltextStaging).filter_by(source_id=source_id).first()
        if row is None:
            return None
        return {
            "source_id": row.source_id,
            "text_source": row.text_source,
            "parse_confidence": row.parse_confidence,
            "fetched_url": row.fetched_url,
            "sections": json.loads(row.artifact_json)["sections"],
        }


def delete_staging(engine: Engine, source_id: int) -> None:
    with get_session(engine) as session:
        session.query(PaperFulltextStaging).filter_by(source_id=source_id).delete()
