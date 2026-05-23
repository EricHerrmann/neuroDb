"""DB epoch — study tag operations and study note persistence.

Migration target: src/neurodb/db/study.py
"""
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from neurodb.schema import DatasetIndex, StudyNote


def tag_dataset(
    session: Session,
    source: str,
    source_id: str,
    concept_tag: str,
    section_ref: str | None = None,
    note_text: str | None = None,
) -> StudyNote | None:
    """Create a study note linking a dataset to a concept tag.

    Returns the new StudyNote, or None if (source, source_id) is not in datasets_index.
    Caller is responsible for session.commit().
    """
    idx = session.execute(
        select(DatasetIndex).where(
            DatasetIndex.source == source,
            DatasetIndex.source_id == source_id,
        )
    ).scalar_one_or_none()
    if idx is None:
        return None
    note = StudyNote(
        index_id=idx.id,
        concept_tag=concept_tag,
        section_ref=section_ref,
        note_text=note_text,
        tagged_at=datetime.now(timezone.utc).isoformat(),
    )
    session.add(note)
    session.flush()
    return note


def list_tags(
    session: Session,
    concept: str | None = None,
    source: str | None = None,
) -> list[dict]:
    """Return study notes with dataset info, optionally filtered.

    concept: substring match against concept_tag (case-insensitive)
    source: exact match against datasets_index.source
    """
    rows = session.execute(
        select(StudyNote, DatasetIndex)
        # Phase 2: only returns dataset-anchored notes; topic/concept/paper-anchored notes are excluded (Phase 5)
        .join(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note, idx = row.StudyNote, row.DatasetIndex
        if concept and concept.lower() not in note.concept_tag.lower():
            continue
        if source and source != idx.source:
            continue
        results.append({
            "id": note.id,
            "source": idx.source,
            "source_id": idx.source_id,
            "concept_tag": note.concept_tag,
            "section_ref": note.section_ref,
            "note_text": note.note_text,
            "tagged_at": note.tagged_at,
        })
    return results


_STUDY_NOTE_INDEX_COLS = {
    "ix_study_notes_concept_id": "concept_id",
    "ix_study_notes_concept_tag": "concept_tag",
    "ix_study_notes_index_id": "index_id",
    "ix_study_notes_paper_id": "paper_id",
    "ix_study_notes_topic_id": "topic_id",
}


def delete_tag(session: Session, tag_id: int) -> bool:
    """Delete a study note by id. Returns True if deleted, False if not found."""
    note = session.get(StudyNote, tag_id)
    if note is None:
        return False
    # DuckDB ART index bug: index entries become inconsistent for rows that
    # predate column additions via ALTER TABLE. The FatalException on commit
    # invalidates the whole connection, so there is no safe catch-and-retry.
    # Drop all secondary indexes before DELETE so DuckDB has nothing to update,
    # then recreate them. Cost is negligible for a small local table.
    session.expunge(note)
    for idx_name in _STUDY_NOTE_INDEX_COLS:
        session.execute(text(f'DROP INDEX IF EXISTS "{idx_name}"'))
    session.execute(text("DELETE FROM study_notes WHERE id = :id"), {"id": tag_id})
    for idx_name, col in _STUDY_NOTE_INDEX_COLS.items():
        session.execute(text(f'CREATE INDEX IF NOT EXISTS "{idx_name}" ON study_notes ({col})'))
    return True


def search_tags(session: Session, keyword: str) -> list[dict]:
    """Return notes where keyword appears in concept_tag, note_text, or section_ref."""
    kw = keyword.lower()
    rows = session.execute(
        select(StudyNote, DatasetIndex)
        # Phase 2: only returns dataset-anchored notes; topic/concept/paper-anchored notes are excluded (Phase 5)
        .join(DatasetIndex, DatasetIndex.id == StudyNote.index_id)
        .order_by(StudyNote.tagged_at.desc())
    ).all()
    results = []
    for row in rows:
        note, idx = row.StudyNote, row.DatasetIndex
        in_concept = kw in note.concept_tag.lower()
        in_note = note.note_text and kw in note.note_text.lower()
        in_section = note.section_ref and kw in note.section_ref.lower()
        if in_concept or in_note or in_section:
            results.append({
                "source": idx.source,
                "source_id": idx.source_id,
                "concept_tag": note.concept_tag,
                "section_ref": note.section_ref,
                "note_text": note.note_text,
                "tagged_at": note.tagged_at,
            })
    return results
