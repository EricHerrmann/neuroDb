import type {
  ChatSession,
  ActiveContext,
  CreateLearningSourceRequest,
  CreateStudyNoteRequest,
  DatasetItem,
  DeleteStudyNoteResponse,
  DuplicateCheckResponse,
  Hypothesis,
  HypothesisReviewItem,
  KnowledgeSourceItem,
  LearningSourceItem,
  ModelInfo,
  Preferences,
  ResearchMetrics,
  ResearchQuestion,
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
  getSessions: () => get<ChatSession[]>('/api/sessions'),
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
    get<KnowledgeSourceItem[]>(`/api/knowledge-library?status=${status}`),
  approveSource: (id: number) =>
    post<KnowledgeSourceItem>(`/api/knowledge-library/${id}/approve`),
  approveSourceWithSummary: (id: number) =>
    post<TaskResponse>(`/api/knowledge-library/${id}/approve-with-summary`),
  getKnowledgeDuplicates: (id: number) =>
    get<DuplicateCheckResponse>(`/api/knowledge-library/${id}/duplicates`),
  rejectSource: (id: number) =>
    post<KnowledgeSourceItem>(`/api/knowledge-library/${id}/reject`),
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
}
