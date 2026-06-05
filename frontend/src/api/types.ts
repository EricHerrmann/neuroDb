export interface StudyNote {
  id: number
  source: string
  source_id: string
  concept_tag: string
  section_ref: string | null
  note_text: string | null
  tagged_at: string
  warnings?: string[]
}

export interface ChatSession {
  id: number
  session_id: string
  inferred_topic: string
  agent_mode: string
  started_at: string
  message_count: number
  summary_preview: string | null
  topic_category: string | null
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
  title: string | null
  modality: string | null
  n_subjects: number | null
  usefulness_state: string | null
  missing_context: string | null
}

export interface LearningSourceItem {
  id: number
  source_type: string
  source_key: string
  display_name: string
  added_by: string
  added_at: string
  content_json?: LearningSourceContent | null
}

export interface LearningSourceContent {
  topics?: string[]
  chapters?: Array<{ number?: number | string; title?: string; name?: string } | string>
  raw?: unknown
  [key: string]: unknown
}

export interface PaperItem {
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
  abstract: string | null
  year: number | null
  grouping_links?: PaperGroupingLink[]
  warnings?: string[]
}

export interface PaperGroupingLink {
  grouping_id: number
  grouping_type: string
  grouping_name: string
  status: string
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
  evidence_json: unknown[]
  predictions_json: unknown[]
  datasets_json: unknown[]
  confounds_json: unknown[]
  limitations: string | null
  status: string
  created_at: string | null
}

export interface HypothesisReviewItem {
  id: number
  hypothesis_id: number
  model: string
  critique_text: string
  unsupported_claims: unknown[]
  missing_confounds: unknown[]
  suggested_revisions: string
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
  context_mode: 'general' | 'contextual' | 'grounded'
  relevance_threshold: number
}

export interface ActiveContext {
  active_prior_topic: string | null
}

export interface ModelRouteInfo {
  tier: string
  provider: string
  model: string
}

export interface ModelInfo {
  agent_modes: Record<string, ModelRouteInfo>
  tiers: Record<'low' | 'mid' | 'high', ModelRouteInfo>
}

export interface TaskResponse {
  task_id: string
}

export interface DeleteStudyNoteResponse {
  deleted: boolean
  warnings?: string[]
}

export interface DuplicateCandidate {
  id: string
  title: string
  doi: string | null
  distance: number | null
}

export interface DuplicateCheckResponse {
  candidates: DuplicateCandidate[]
}

export interface CreateStudyNoteRequest {
  source: string
  source_id: string
  concept_tag: string
  section_ref?: string
  note_text?: string
}

export interface CreateLearningSourceRequest {
  source_type: string
  source_key: string
  display_name: string
  topics?: string[]
}

export interface EvidenceSummary {
  mode: string
  papers: number
  notes: number
  claims: number
  datasets: number
  gaps: number
}

export interface ClaimItem {
  id: number
  paper_id: number
  text: string
  claim_type: string
  status: string
  created_at: string
  updated_at: string
}

export interface ResearchGapItem {
  id: number
  question_id: number | null
  hypothesis_id: number | null
  description: string
  gap_type: string
  status: string
  created_at: string
  updated_at: string
}

export interface EvidenceLinkItem {
  id: number
  hypothesis_id: number
  claim_id: number | null
  paper_id: number | null
  packet_id: number | null
  note_id: number | null
  link_type: string
  status: string
  created_at: string
}

export interface QuestionTopicLink {
  topic_id: number
  topic_name: string
  status: string  // 'pending' | 'confirmed'
  proposed?: boolean
}

export interface QuestionConceptLink {
  concept_id: number
  concept_name: string
  status: string
  proposed?: boolean
}

export interface GroupingItem {
  id: number
  type: string
  name: string
  parent_id: number | null
  status: string
  description: string | null
}

export interface ResearchQuestionDetail {
  id: number
  question: string
  status: string
  topic_context: string | null
  origin_session_id: number | null
  created_at: string | null
  topics: QuestionTopicLink[]
  concepts: QuestionConceptLink[]
}

export interface CreateQuestionRequest {
  question: string
  topic_context?: string
  origin_session_id?: number
}

export interface PlanStep {
  id: number
  plan_id: number
  order_index: number
  step_type: 'read' | 'action'
  paper_id: number | null
  source_ref: string | null
  action_text: string | null
  lifecycle: 'proposed' | 'confirmed' | 'proposed_removal'
  progress: 'todo' | 'in_progress' | 'done' | 'skipped'
  note: string | null
}

export interface PlanGroupingLink {
  id: number
  type: string
  name: string
  link_status: string
}

export interface PlanSummary {
  id: number
  title: string
  status: string
  origin_agent: string
  percent_complete: number
  step_count: number
  pending_change_count: number
}

export interface PlanDetail extends PlanSummary {
  origin_prompt: string
  research_question_id: number | null
  created_at: string
  updated_at: string
  steps: PlanStep[]
  groupings: PlanGroupingLink[]
}
