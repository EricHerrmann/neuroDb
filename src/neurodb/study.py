from datetime import datetime, timezone

from sqlalchemy import select
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
