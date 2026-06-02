"""DB epoch — ORM schema definitions for all NeuroDb structured storage.

Owns: all SQLAlchemy ORM models including source tables, DatasetIndex,
StudyNote, ChatSession, Paper, ResearchHypothesis, HypothesisReview,
ModelCallLog, and any future research artifact tables.

Migration target: src/neurodb/db/schema.py
"""
from sqlalchemy import CheckConstraint, Float, ForeignKey, Index, Integer, Sequence, String, Text, UniqueConstraint
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
    """User note tied to a dataset, topic, concept, or paper for study tracking."""
    __tablename__ = "study_notes"
    __table_args__ = (
        CheckConstraint(
            "index_id IS NOT NULL OR topic_id IS NOT NULL OR "
            "concept_id IS NOT NULL OR paper_id IS NOT NULL",
            name="ck_study_notes_one_anchor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("study_notes_id_seq"), primary_key=True)
    index_id: Mapped[int | None] = mapped_column(
        ForeignKey("datasets_index.id"), nullable=True, index=True
    )
    topic_id: Mapped[int | None] = mapped_column(
        ForeignKey("topics.id"), nullable=True, index=True
    )
    concept_id: Mapped[int | None] = mapped_column(
        ForeignKey("concepts.id"), nullable=True, index=True
    )
    paper_id: Mapped[int | None] = mapped_column(
        ForeignKey("papers.id"), nullable=True, index=True
    )
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


class DatasetResearchPacket(Base):
    """Source-aware research context packet for an ingested dataset.

    One row per dataset. The packet records what source-native context was
    harvested, how useful the record is for research/learning, and which
    important fields are still missing.
    """
    __tablename__ = "dataset_research_packets"
    __table_args__ = (
        UniqueConstraint("index_id", name="uq_dataset_research_packets_index_id"),
        UniqueConstraint("source", "source_id", name="uq_dataset_research_packets_source_id"),
        Index("ix_dataset_research_packets_source_state", "source", "usefulness_state"),
    )

    id: Mapped[int] = mapped_column(
        Integer, Sequence("dataset_research_packets_id_seq"), primary_key=True
    )
    index_id: Mapped[int] = mapped_column(ForeignKey("datasets_index.id"), nullable=False)
    source: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    source_id: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    landing_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    api_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    doi: Mapped[str | None] = mapped_column(String(256), nullable=True, index=True)
    paper_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    publication_title: Mapped[str | None] = mapped_column(Text, nullable=True)
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    topics_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    brain_regions_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    diseases_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    modalities_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    participant_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    methods_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    assets_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    usefulness_state: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    supported_workflows_json: Mapped[str] = mapped_column(Text, nullable=False)
    unsupported_workflows_json: Mapped[str] = mapped_column(Text, nullable=False)
    missing_context_json: Mapped[str] = mapped_column(Text, nullable=False)
    provenance_json: Mapped[str] = mapped_column(Text, nullable=False)
    confidence_json: Mapped[str] = mapped_column(Text, nullable=False)
    harvested_at: Mapped[str] = mapped_column(String(32), nullable=False)
    run_id: Mapped[int] = mapped_column(ForeignKey("ingest_runs.id"), nullable=False)


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


class Paper(Base):
    """Candidate and approved learning sources surfaced by NeuroTutorAgent."""
    __tablename__ = "papers"
    __table_args__ = (
        UniqueConstraint("doi", name="uq_papers_doi"),
        UniqueConstraint("normalized_title", name="uq_papers_normalized_title"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("papers_id_seq"), primary_key=True)
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
    abstract: Mapped[str | None] = mapped_column(Text, nullable=True)
    authors_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    year: Mapped[int | None] = mapped_column(Integer, nullable=True)


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
    topic_category: Mapped[str | None] = mapped_column(String(64), nullable=True)


class LiteratureSearch(Base):
    """Observability log for literature searches run by Neuro-Tutor."""
    __tablename__ = "literature_searches"

    id: Mapped[int] = mapped_column(Integer, Sequence("literature_searches_id_seq"), primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    pubmed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    semantic_scholar_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    arxiv_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
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
    topic_id: Mapped[int | None] = mapped_column(ForeignKey("topics.id"), nullable=True)
    origin_session_id: Mapped[int | None] = mapped_column(Integer, nullable=True)


class ResearchHypothesis(Base):
    """Draft, untested research hypotheses generated by Neuro-Research."""
    __tablename__ = "research_hypotheses"

    id: Mapped[int] = mapped_column(Integer, Sequence("research_hypotheses_id_seq"), primary_key=True)
    question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    mechanism: Mapped[str] = mapped_column(Text, nullable=False)
    evidence_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    predictions_json: Mapped[str] = mapped_column(Text, nullable=False)
    datasets_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    confounds_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    limitations: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class HypothesisReview(Base):
    """Premium-model critique linked to a draft research hypothesis."""
    __tablename__ = "hypothesis_reviews"
    __table_args__ = (
        Index("ix_hypothesis_reviews_hypothesis_status", "hypothesis_id", "status"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("hypothesis_reviews_id_seq"), primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    model: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    critique_text: Mapped[str] = mapped_column(Text, nullable=False)
    unsupported_claims_json: Mapped[str] = mapped_column(Text, nullable=False)
    missing_confounds_json: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_revisions: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="pending", index=True)


class QuestionTopic(Base):
    """Many-to-many: research_questions ↔ topics, with pending/confirmed lifecycle."""
    __tablename__ = "question_topics"
    __table_args__ = (
        UniqueConstraint("question_id", "topic_id", name="uq_question_topic"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("question_topics_id_seq"), primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class QuestionConcept(Base):
    """Many-to-many: research_questions ↔ concepts, with pending/confirmed lifecycle."""
    __tablename__ = "question_concepts"
    __table_args__ = (
        UniqueConstraint("question_id", "concept_id", name="uq_question_concept"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("question_concepts_id_seq"), primary_key=True)
    question_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


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
    context_papers_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_notes_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_claims_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_datasets_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    context_gap_count: Mapped[int | None] = mapped_column(Integer, nullable=True)


class SystemWarning(Base):
    """Structured operational warnings for routing and model-provider anomalies."""
    __tablename__ = "system_warnings"
    __table_args__ = (
        Index("ix_system_warnings_recorded_type", "recorded_at", "warning_type"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("system_warnings_id_seq"), primary_key=True)
    recorded_at: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    warning_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    severity: Mapped[str] = mapped_column(String(8), nullable=False, index=True)
    task_type: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    requested_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    selected_provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    message: Mapped[str] = mapped_column(Text, nullable=False)


class AppPreference(Base):
    """Narrow persisted app preferences."""
    __tablename__ = "app_preferences"

    key: Mapped[str] = mapped_column(String(128), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Topic(Base):
    """Researchable subject area used to group Papers, Concepts, notes, and dataset packets."""
    __tablename__ = "topics"

    id: Mapped[int] = mapped_column(Integer, Sequence("topics_id_seq"), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Concept(Base):
    """Learnable idea, mechanism, anatomy term, or clinical concept within a topic."""
    __tablename__ = "concepts"

    id: Mapped[int] = mapped_column(Integer, Sequence("concepts_id_seq"), primary_key=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class PaperTopic(Base):
    """Join table linking a Paper to a Topic."""
    __tablename__ = "paper_topics"
    __table_args__ = (UniqueConstraint("paper_id", "topic_id", name="uq_paper_topics"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("paper_topics_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)


class PaperConcept(Base):
    """Join table linking a Paper to a Concept."""
    __tablename__ = "paper_concepts"
    __table_args__ = (UniqueConstraint("paper_id", "concept_id", name="uq_paper_concepts"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("paper_concepts_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False, index=True)


class TopicConcept(Base):
    """Join table linking a Topic to a Concept."""
    __tablename__ = "topic_concepts"
    __table_args__ = (UniqueConstraint("topic_id", "concept_id", name="uq_topic_concepts"),)

    id: Mapped[int] = mapped_column(Integer, Sequence("topic_concepts_id_seq"), primary_key=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)
    concept_id: Mapped[int] = mapped_column(ForeignKey("concepts.id"), nullable=False, index=True)


class DatasetPacketTopic(Base):
    """Join table linking a DatasetResearchPacket to a Topic."""
    __tablename__ = "dataset_packet_topics"
    __table_args__ = (UniqueConstraint("packet_id", "topic_id", name="uq_dataset_packet_topics"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("dataset_packet_topics_id_seq"), primary_key=True
    )
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=False, index=True
    )
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id"), nullable=False, index=True)


class DatasetPacketPaper(Base):
    """Join table linking a DatasetResearchPacket to a Paper."""
    __tablename__ = "dataset_packet_papers"
    __table_args__ = (UniqueConstraint("packet_id", "paper_id", name="uq_dataset_packet_papers"),)

    id: Mapped[int] = mapped_column(
        Integer, Sequence("dataset_packet_papers_id_seq"), primary_key=True
    )
    packet_id: Mapped[int] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=False, index=True
    )
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)


class Claim(Base):
    """Paper-sourced claim awaiting review — candidate, approved, or rejected."""
    __tablename__ = "claims"

    id: Mapped[int] = mapped_column(Integer, Sequence("claims_id_seq"), primary_key=True)
    paper_id: Mapped[int] = mapped_column(ForeignKey("papers.id"), nullable=False, index=True)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    claim_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="candidate")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class EvidenceLink(Base):
    """Structured evidence link from a hypothesis to a claim, paper, dataset packet, or study note.

    CheckConstraint enforces exactly one of (claim_id, paper_id, packet_id, note_id) non-null.
    """
    __tablename__ = "evidence_links"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN claim_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN paper_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN packet_id IS NOT NULL THEN 1 ELSE 0 END + "
            "CASE WHEN note_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_evidence_links_one_source",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("evidence_links_id_seq"), primary_key=True)
    hypothesis_id: Mapped[int] = mapped_column(
        ForeignKey("research_hypotheses.id"), nullable=False, index=True
    )
    claim_id: Mapped[int | None] = mapped_column(ForeignKey("claims.id"), nullable=True, index=True)
    paper_id: Mapped[int | None] = mapped_column(ForeignKey("papers.id"), nullable=True, index=True)
    packet_id: Mapped[int | None] = mapped_column(
        ForeignKey("dataset_research_packets.id"), nullable=True, index=True
    )
    note_id: Mapped[int | None] = mapped_column(ForeignKey("study_notes.id"), nullable=True, index=True)
    link_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)


class ResearchGap(Base):
    """Named evidence gap anchored to a research question or hypothesis (or both)."""
    __tablename__ = "research_gaps"
    __table_args__ = (
        CheckConstraint(
            "question_id IS NOT NULL OR hypothesis_id IS NOT NULL",
            name="ck_research_gaps_one_anchor",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("research_gaps_id_seq"), primary_key=True)
    question_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    hypothesis_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    gap_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="open")
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class Grouping(Base):
    """Unified categorization entity. One row per topic/concept/future type.

    `type` selects the grouping kind ('topic', 'concept', ...). `parent_id`
    is a plain self-reference without an FK constraint because DuckDB rejects
    updates on FK-referenced rows; re-parenting needs UPDATE support.
    """
    __tablename__ = "groupings"
    __table_args__ = (
        UniqueConstraint("type", "name", name="uq_groupings_type_name"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("groupings_id_seq"), primary_key=True)
    type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(256), nullable=False)
    parent_id: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active", index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
    updated_at: Mapped[str] = mapped_column(String(32), nullable=False)


class GroupingLink(Base):
    """Link from a grouping to an anchor with pending/confirmed lifecycle."""
    __tablename__ = "grouping_links"
    __table_args__ = (
        UniqueConstraint(
            "grouping_id", "anchor_type", "anchor_id", name="uq_grouping_links_anchor"
        ),
        Index("ix_grouping_links_anchor", "anchor_type", "anchor_id"),
    )

    id: Mapped[int] = mapped_column(Integer, Sequence("grouping_links_id_seq"), primary_key=True)
    grouping_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    anchor_type: Mapped[str] = mapped_column(String(32), nullable=False)
    anchor_id: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="confirmed", index=True)
    created_at: Mapped[str] = mapped_column(String(32), nullable=False)
