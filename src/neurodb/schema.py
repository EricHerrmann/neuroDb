from sqlalchemy import Float, ForeignKey, Integer, Sequence, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class IngestRun(Base):
    __tablename__ = "ingest_runs"

    id: Mapped[int] = mapped_column(Integer, Sequence("ingest_runs_id_seq"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    run_at: Mapped[str] = mapped_column(String(32), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class DatasetIndex(Base):
    """Thin shared registry. One row per ingested dataset regardless of source.

    Source-specific tables (openneuro_datasets, allen_datasets) reference
    this table via index_id and are defined alongside their connectors.
    """
    __tablename__ = "datasets_index"
    __table_args__ = (UniqueConstraint("source", "source_id", name="uq_dataset_source_id"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("datasets_index_id_seq"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)

    subjects: Mapped[list["Subject"]] = relationship(back_populates="dataset_index")


class Subject(Base):
    __tablename__ = "subjects"
    __table_args__ = (
        UniqueConstraint("index_id", "source_subject_id", name="uq_subject_index_source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("subjects_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False)
    source_subject_id: Mapped[str] = mapped_column(String(128), nullable=False)
    age: Mapped[float | None] = mapped_column(Float, nullable=True)
    sex: Mapped[str | None] = mapped_column(String(8), nullable=True)
    diagnosis: Mapped[str | None] = mapped_column(String(128), nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)

    dataset_index: Mapped["DatasetIndex"] = relationship(back_populates="subjects")


class CrossRef(Base):
    """Records known cross-source links between entities.
    Populated only when a deterministic match exists (e.g. DOI exact match).
    Left empty until Phase 3 field-coverage review confirms overlap.
    """
    __tablename__ = "cross_refs"

    id: Mapped[int] = mapped_column(Integer, Sequence("cross_refs_id_seq"), primary_key=True)
    source_a: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id_a: Mapped[str] = mapped_column(String(128), nullable=False)
    source_b: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    id_b: Mapped[str] = mapped_column(String(128), nullable=False)
    confidence: Mapped[str] = mapped_column(String(16), nullable=False)
    method: Mapped[str] = mapped_column(String(64), nullable=False)


class QualityEvent(Base):
    """Structured quality flag log. Attached to any entity by (entity_source, entity_id)."""
    __tablename__ = "quality_events"

    id: Mapped[int] = mapped_column(Integer, Sequence("quality_events_id_seq"), primary_key=True)
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    entity_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    flag: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    flagged_at: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


class StudyNote(Base):
    __tablename__ = "study_notes"

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_at: Mapped[str] = mapped_column(String(32), nullable=False)


class LearningSource(Base):
    """Registry of textbooks, papers, and datasets used as learning sources.

    One row per source. Books carry full chapter structure in content_json.
    source_type and added_by are open strings — new values require no migration.
    """
    __tablename__ = "learning_sources"

    id: Mapped[int] = mapped_column(Integer, Sequence("learning_sources_id_seq"), primary_key=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_key: Mapped[str] = mapped_column(String(256), nullable=False, unique=True)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    content_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    added_by: Mapped[str] = mapped_column(String(32), nullable=False)
    added_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ImportQueue(Base):
    """Datasets suggested by the discovery agent, pending user confirmation.

    status is an open string: 'pending', 'imported', 'dismissed'.
    Nothing is ingested until the user confirms via the Suggestions UI tab.
    """
    __tablename__ = "import_queue"

    id: Mapped[int] = mapped_column(Integer, Sequence("import_queue_id_seq"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    chapter_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_at: Mapped[str] = mapped_column(String(32), nullable=False)
    resolved_at: Mapped[str | None] = mapped_column(String(32), nullable=True)


class SourceSuggestion(Base):
    """New connectors or learning sources suggested by the discovery agent.

    suggestion_type and status are open strings.
    Accepted entries for new connectors require a separate engineering step.
    """
    __tablename__ = "source_suggestions"

    id: Mapped[int] = mapped_column(Integer, Sequence("source_suggestions_id_seq"), primary_key=True)
    suggestion_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    display_name: Mapped[str | None] = mapped_column(Text, nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    metadata_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    suggested_at: Mapped[str] = mapped_column(String(32), nullable=False)
