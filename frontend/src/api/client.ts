import type {
  ChatSession,
  ActiveContext,
  ClaimItem,
  CreateLearningSourceRequest,
  CreateQuestionRequest,
  CreateStudyNoteRequest,
  DatasetItem,
  DeleteStudyNoteResponse,
  DuplicateCheckResponse,
  EvidenceLinkItem,
  EvidenceSummary,
  Hypothesis,
  HypothesisReviewItem,
  PaperItem,
  LearningSourceItem,
  ModelInfo,
  Preferences,
  QuestionConceptLink,
  QuestionTopicLink,
  ResearchGapItem,
  ResearchMetrics,
  ResearchQuestion,
  ResearchQuestionDetail,
  SqlResult,
  StudyNote,
  SuggestionsResponse,
  TaskResponse,
} from './types'

async function get<T>(path: string): Promise<T> {
  const res = await fetch(path)
  if (!res.ok) throw new Error(`${res.status} ${res.statusText}`)
  return res.json() as Promise<T>
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

async function put<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PUT',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

async function patch<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'PATCH',
    headers: body !== undefined ? { 'Content-Type': 'application/json' } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  return res.json() as Promise<T>
}

async function del<T = void>(path: string): Promise<T> {
  const res = await fetch(path, { method: 'DELETE' })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(text || `${res.status} ${res.statusText}`)
  }
  if (res.status === 204) return undefined as T
  return res.json() as Promise<T>
}

export const api = {
  getPreferences: () => get<Preferences>('/api/preferences'),
  getModelInfo: () => get<ModelInfo>('/api/model-info'),
  setAgentMode: (mode: string) =>
    put<{ agent_mode: string }>('/api/preferences/agent-mode', { mode }),
  setContextMode: (mode: string) =>
    put<{ context_mode: string }>('/api/preferences/context-mode', { mode }),
  getSessions: () => get<ChatSession[]>('/api/sessions'),
  deleteSession: (sessionId: string) => del<void>(`/api/sessions/${sessionId}`),
  getActiveContext: () => get<ActiveContext>('/api/sessions/active-context'),
  getStudyLog: () => get<StudyNote[]>('/api/study-log'),
  createStudyNote: (body: CreateStudyNoteRequest) =>
    post<StudyNote>('/api/study-log', body),
  updateStudyNote: (id: number, body: CreateStudyNoteRequest) =>
    patch<StudyNote>(`/api/study-log/${id}`, body),
  deleteStudyNote: (id: number) =>
    del<DeleteStudyNoteResponse>(`/api/study-log/${id}`),
  getSuggestions: () => get<SuggestionsResponse>('/api/suggestions'),
  dismissImportItem: (id: number) =>
    post<void>(`/api/suggestions/import-queue/${id}/dismiss`),
  dismissSourceSuggestion: (id: number) =>
    post<void>(`/api/suggestions/source-suggestions/${id}/dismiss`),
  promoteSourceSuggestion: (id: number) =>
    post<LearningSourceItem>(`/api/suggestions/source-suggestions/${id}/promote`),
  getDatasets: (keyword?: string, modality?: string) => {
    const params = new URLSearchParams()
    if (keyword) params.set('keyword', keyword)
    if (modality && modality !== 'all') params.set('modality', modality)
    const query = params.toString()
    return get<DatasetItem[]>(query ? `/api/datasets?${query}` : '/api/datasets')
  },
  importDataset: (source: string, sourceId: string) =>
    post<TaskResponse>(`/api/datasets/${source}/${sourceId}/import`),
  getRegistry: () => get<LearningSourceItem[]>('/api/registry'),
  deleteRegistryEntry: (id: number) =>
    del(`/api/registry/${id}`),
  createRegistryEntry: (body: CreateLearningSourceRequest) =>
    post<LearningSourceItem>('/api/registry', body),
  getKnowledgeLibrary: (status = 'all') =>
    get<PaperItem[]>(`/api/knowledge-library?status=${status}`),
  approveSource: (id: number) =>
    post<PaperItem>(`/api/knowledge-library/${id}/approve`),
  approveSourceWithSummary: (id: number) =>
    post<TaskResponse>(`/api/knowledge-library/${id}/approve-with-summary`),
  getKnowledgeDuplicates: (id: number) =>
    get<DuplicateCheckResponse>(`/api/knowledge-library/${id}/duplicates`),
  rejectSource: (id: number) =>
    post<PaperItem>(`/api/knowledge-library/${id}/reject`),
  removeSource: (id: number) =>
    post<PaperItem>(`/api/knowledge-library/${id}/remove`),
  getResearchMetrics: () => get<ResearchMetrics>('/api/research/metrics'),
  getResearchQuestions: (statuses: string[] = []) => {
    const params = new URLSearchParams()
    statuses.forEach(status => params.append('status', status))
    const query = params.toString()
    return get<ResearchQuestion[]>(query ? `/api/research/questions?${query}` : '/api/research/questions')
  },
  getHypotheses: (statuses: string[] = []) => {
    const params = new URLSearchParams()
    statuses.forEach(status => params.append('status', status))
    const query = params.toString()
    return get<Hypothesis[]>(query ? `/api/research/hypotheses?${query}` : '/api/research/hypotheses')
  },
  getHypothesisReviews: (id: number) =>
    get<HypothesisReviewItem[]>(`/api/research/hypotheses/${id}/reviews`),
  snapshotMetrics: () => post<Record<string, unknown>>('/api/research/metrics/snapshot'),
  runHypothesisReview: (id: number) =>
    post<TaskResponse>(`/api/research/hypotheses/${id}/review`),
  acceptHypothesisReview: (id: number) =>
    post<HypothesisReviewItem>(`/api/research/reviews/${id}/accept`),
  dismissHypothesisReview: (id: number) =>
    post<HypothesisReviewItem>(`/api/research/reviews/${id}/dismiss`),
  endSession: (sessionId: string, body: { messages: { role: string; content: string }[]; agent_mode: string }) =>
    post<ChatSession>(`/api/sessions/${sessionId}/end`, body),
  executeSQL: (sql: string) => post<SqlResult>('/api/sql/execute', { sql }),
  getClaims: () => get<ClaimItem[]>('/api/research/claims'),
  getGaps: () => get<ResearchGapItem[]>('/api/research/gaps'),
  getEvidenceLinks: (hypothesisId: number) =>
    get<EvidenceLinkItem[]>(`/api/research/hypotheses/${hypothesisId}/evidence-links`),
  retractEvidenceLink: (id: number) =>
    post<EvidenceLinkItem>(`/api/research/evidence-links/${id}/retract`),
  archiveHypothesis: (id: number) =>
    post<Hypothesis>(`/api/research/hypotheses/${id}/archive`),
  archiveQuestion: (id: number) =>
    post<ResearchQuestion>(`/api/research/questions/${id}/archive`),
  getResearchQuestionsDetail: (statuses: string[] = [], topicId?: number) => {
    const params = new URLSearchParams()
    statuses.forEach(status => params.append('status', status))
    if (topicId !== undefined) params.set('topic_id', String(topicId))
    const query = params.toString()
    return get<ResearchQuestionDetail[]>(query ? `/api/research/questions?${query}` : '/api/research/questions')
  },
  getQuestionDetail: (id: number) =>
    get<ResearchQuestionDetail>(`/api/research/questions/${id}`),
  createQuestion: (body: CreateQuestionRequest) =>
    post<ResearchQuestionDetail>('/api/research/questions', body),
  updateQuestion: (id: number, body: { question?: string; topic_context?: string }) =>
    put<ResearchQuestionDetail>(`/api/research/questions/${id}`, body),
  deleteQuestion: (id: number) =>
    del<void>(`/api/research/questions/${id}`),
  addQuestionTopic: (questionId: number, topicId: number) =>
    post<ResearchQuestionDetail>(`/api/research/questions/${questionId}/topics`, { topic_id: topicId }),
  confirmQuestionTopic: (questionId: number, topicId: number) =>
    patch<ResearchQuestionDetail>(`/api/research/questions/${questionId}/topics/${topicId}`, { status: 'confirmed' }),
  removeQuestionTopic: (questionId: number, topicId: number) =>
    del<void>(`/api/research/questions/${questionId}/topics/${topicId}`),
  addQuestionConcept: (questionId: number, conceptId: number) =>
    post<ResearchQuestionDetail>(`/api/research/questions/${questionId}/concepts`, { concept_id: conceptId }),
  confirmQuestionConcept: (questionId: number, conceptId: number) =>
    patch<ResearchQuestionDetail>(`/api/research/questions/${questionId}/concepts/${conceptId}`, { status: 'confirmed' }),
  removeQuestionConcept: (questionId: number, conceptId: number) =>
    del<void>(`/api/research/questions/${questionId}/concepts/${conceptId}`),
  approveClaim: (id: number) =>
    post<ClaimItem>(`/api/research/claims/${id}/approve`),
  rejectClaim: (id: number) =>
    post<ClaimItem>(`/api/research/claims/${id}/reject`),
  archiveClaim: (id: number) =>
    post<ClaimItem>(`/api/research/claims/${id}/archive`),
  resolveGap: (id: number) =>
    post<ResearchGapItem>(`/api/research/gaps/${id}/resolve`),
  archiveGap: (id: number) =>
    post<ResearchGapItem>(`/api/research/gaps/${id}/archive`),
}
