export interface StudyNote {
  id: number
  source: string
  source_id: string
  concept_tag: string
  section_ref: string | null
  note_text: string | null
  tagged_at: string
}

export interface ChatSession {
  id: number
  session_id: string
  inferred_topic: string
  agent_mode: string
  started_at: string
  message_count: number
  summary_preview: string | null
}

export interface ImportQueueItem {
  id: number
  source: string
  source_id: string
  title: string | null
  reason: string | null
  chapter_ref: string | null
  status: string
  suggested_at: string
}

export interface SourceSuggestionItem {
  id: number
  suggestion_type: string
  reference: string | null
  display_name: string | null
  reason: string | null
  status: string
  suggested_at: string
}

export interface SuggestionsResponse {
  import_queue: ImportQueueItem[]
  source_suggestions: SourceSuggestionItem[]
}

export interface DatasetItem {
  id: number
  source: string
  source_id: string
}

export interface LearningSourceItem {
  id: number
  source_type: string
  source_key: string
  display_name: string
  added_by: string
  added_at: string
}

export interface KnowledgeSourceItem {
  id: number
  title: string
  doi: string | null
  url: string | null
  source_type: string
  topic_context: string
  status: string
  queued_at: string
  reviewed_at: string | null
  summary: string | null
}

export interface ResearchMetrics {
  approved_sources_count: number
  chat_sessions_count: number
  literature_searches_count: number
  research_hypotheses_count: number
  caveats: string[]
  [key: string]: unknown
}

export interface ResearchQuestion {
  id: number
  question: string
  status: string
  topic_context: string | null
  created_at: string | null
}

export interface Hypothesis {
  id: number
  title: string
  mechanism: string | null
  status: string
  created_at: string | null
}

export interface SqlResult {
  columns: string[]
  rows: unknown[][]
  row_count: number
}

export interface Preferences {
  agent_mode: 'local_db' | 'external_db' | 'neuro_tutor' | 'neuro_research'
  relevance_threshold: number
}
