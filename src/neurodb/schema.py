"""DB epoch — ORM schema definitions for all NeuroDb structured storage.

Owns: all SQLAlchemy ORM models including source tables, DatasetIndex,
StudyNote, ChatSession, KnowledgeSource, ResearchHypothesis, HypothesisReview,
ModelCallLog, and any future research artifact tables.

Migration target: src/neurodb/db/schema.py
"""
from sqlalchemy import Float, ForeignKey, Index, Integer, Sequence, String, Text, UniqueConstraint
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
    __table_args__ = (
        Index("ix_quality_events_source_id_flag", "entity_source", "entity_id", "flag"),
    )

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
    __table_args__ = (
        UniqueConstraint("index_id", "concept_tag", name="uq_study_note_index_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False, index=True)
    concept_tag: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    section_ref: Mapped[str | None] = mapped_column(String(64), nullable=True)
    note_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    tagged_at: Mapped[str] = mapped_column(String(32), nullable=False)


class DatasetEmbeddingState(Base):
    """Tracks the last embedded content hash for each dataset."""
    __tablename__ = "dataset_embedding_state"
    __table_args__ = (
        UniqueConstraint("source", "source_id", name="uq_dataset_embedding_state_source_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("dataset_embedding_state_id_seq"), primary_key=True)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    embedder_model: Mapped[str] = mapped_column(String(128), nullable=False)
    embedded_at: Mapped[str] = mapped_column(String(32), nullable=False)


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


class KnowledgeSource(Base):
    """Candidate and approved learning sources surfaced by NeuroTutorAgent."""
    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint("doi", name="uq_knowledge_sources_doi"),
        UniqueConstraint("normalized_title", name="uq_knowledge_sources_normalized_title"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("knowledge_sources_id_seq"), primary_key=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    normalized_title: Mapped[str] = mapped_column(String(512), nullable=False, index=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True)
    url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    topic_context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    queued_at: Mapped[str] = mapped_column(String(32), nullable=False)
    reviewed_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    chroma_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class ChatSession(Base):
    """Completed chat-session index for previous-topic retrieval UI."""
    __tablename__ = "chat_sessions"
    __table_args__ = (
        UniqueConstraint("session_id", name="uq_chat_sessions_session_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("chat_sessions_id_seq"), primary_key=True)
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    inferred_topic: Mapped[str] = mapped_column(Text, nullable=False)
    agent_mode: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    started_at: Mapped[str] = mapped_column(String(32), nullable=False)
    ended_at: Mapped[str | None] = mapped_column(String(32), nullable=True)
    summary_preview: Mapped[str | None] = mapped_column(String(200), nullable=True)
    message_count: Mapped[int] = mapped_column(Integer, nullable=False)


class LiteratureSearch(Base):
    """Observability log for literature searches run by Neuro-Tutor."""
    __tablename__ = "literature_searches"

    id: Mapped[int] = mapped_column(Integer, Sequence("literature_searches_id_seq"), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    pubmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    semantic_scholar_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    results_json: Mapped[str] = mapped_column(Text, nullable=False)
    searched_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ResearchQuestion(Base):
    """Candidate research questions raised during Neuro-Research sessions."""
    __tablename__ = "research_questions"

    id: Mapped[int] = mapped_column(Integer, Sequence("research_questions_id_seq"), primary_key=True)
    question: Mapped[str] = mapped_column(Text, nullable=False)
    topic_context: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="open", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ResearchHypothesis(Base):
    """Draft, untested research hypotheses generated by Neuro-Research."""
    __tablename__ = "research_hypotheses"

    id: Mapped[int] = mapped_column(Integer, Sequence("research_hypotheses_id_seq"), primary_key=True)
    question_id: Mapped[int | None] = mapped_column(
        ForeignKey("research_questions.id"),
        nullable=True,
    )
    title: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    predictions_json: Mapped[str] = mapped_column(Text, nullable=False)
    datasets_json: Mapped[str] = mapped_column(Text, nullable=False)
    confounds_json: Mapped[str] = mapped_column(Text, nullable=False)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class KnowledgeGrowthSnapshot(Base):
    """Append-only snapshot of learning and research-growth metrics."""
    __tablename__ = "knowledge_growth_snapshots"

    id: Mapped[int] = mapped_column(Integer, Sequence("knowledge_growth_snapshots_id_seq"), primary_key=True)
    snapshot_at: Mapped[str] = mapped_column(String(32), nullable=False)
    approved_sources_count: Mapped[int] = mapped_column(Integer, nullable=False)
    pending_sources_count: Mapped[int] = mapped_column(Integer, nullable=False)
    chat_sessions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    literature_searches_count: Mapped[int] = mapped_column(Integer, nullable=False)
    study_notes_count: Mapped[int] = mapped_column(Integer, nullable=False)
    research_questions_count: Mapped[int] = mapped_column(Integer, nullable=False)
    research_hypotheses_count: Mapped[int] = mapped_column(Integer, nullable=False)
    metrics_json: Mapped[str] = mapped_column(Text, nullable=False)


class ModelCallLog(Base):
    """Structured telemetry for paid model calls."""
    __tablename__ = "model_call_log"
    __table_args__ = (
        Index("ix_model_call_log_task_type_model", "task_type", "model"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("model_call_log_id_seq"), primary_key=True)
    recorded_at: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    mode: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    tool_names_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    iteration: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    output_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    stop_reason: Mapped[str | None] = mapped_column(String(64), nullable=True)
    elapsed_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    estimated_cost_usd: Mapped[float | None] = mapped_column(Float, nullable=True)


class AppPreference(Base):
    """Narrow persisted app preferences."""
    __tablename__ = "app_preferences"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)
