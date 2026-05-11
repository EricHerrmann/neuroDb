import type {
  ChatSession,
  CreateLearningSourceRequest,
  CreateStudyNoteRequest,
  DatasetItem,
  Hypothesis,
  KnowledgeSourceItem,
  LearningSourceItem,
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
  setAgentMode: (mode: string) =>
    put<{ agent_mode: string }>('/api/preferences/agent-mode', { mode }),
  getSessions: () => get<ChatSession[]>('/api/sessions'),
  getStudyLog: () => get<StudyNote[]>('/api/study-log'),
  createStudyNote: (body: CreateStudyNoteRequest) =>
    post<StudyNote>('/api/study-log', body),
  getSuggestions: () => get<SuggestionsResponse>('/api/suggestions'),
  dismissImportItem: (id: number) =>
    post<void>(`/api/suggestions/import-queue/${id}/dismiss`),
  dismissSourceSuggestion: (id: number) =>
    post<void>(`/api/suggestions/source-suggestions/${id}/dismiss`),
  promoteSourceSuggestion: (id: number) =>
    post<LearningSourceItem>(`/api/suggestions/source-suggestions/${id}/promote`),
  getDatasets: (keyword?: string) =>
    get<DatasetItem[]>(
      keyword ? `/api/datasets?keyword=${encodeURIComponent(keyword)}` : '/api/datasets',
    ),
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
  rejectSource: (id: number) =>
    post<KnowledgeSourceItem>(`/api/knowledge-library/${id}/reject`),
  getResearchMetrics: () => get<ResearchMetrics>('/api/research/metrics'),
  getResearchQuestions: (status = 'all') =>
    get<ResearchQuestion[]>(`/api/research/questions?status=${status}`),
  getHypotheses: (status = 'all') =>
    get<Hypothesis[]>(`/api/research/hypotheses?status=${status}`),
  snapshotMetrics: () => post<Record<string, unknown>>('/api/research/metrics/snapshot'),
  runHypothesisReview: (id: number) =>
    post<TaskResponse>(`/api/research/hypotheses/${id}/review`),
  executeSQL: (sql: string) => post<SqlResult>('/api/sql/execute', { sql }),
}
