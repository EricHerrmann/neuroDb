import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { ChatSession, CreateStudyNoteRequest, StudyNote } from '../api/types'
import PlanCard from '../components/PlanCard'
import PlanDetailView from '../components/PlanDetail'

type View = 'study-tags' | 'chat-history' | 'plans'
const SOURCE_OPTIONS = ['openneuro', 'allen_brain', 'neurovault', 'dandi', 'pubmed', 'arxiv']

const EMPTY_FORM = {
  source: 'openneuro',
  source_id: '',
  concept_tag: '',
  section_ref: '',
  note_text: '',
}

function CollapseHeader({
  label,
  collapsed,
  onToggle,
}: {
  label: string
  collapsed: boolean
  onToggle: () => void
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      style={{
        display: 'flex',
        alignItems: 'center',
        gap: 4,
        background: 'none',
        border: 'none',
        padding: '2px 0',
        cursor: 'pointer',
        fontSize: 11,
        fontWeight: 600,
        color: '#64748b',
        letterSpacing: '0.04em',
        marginBottom: collapsed ? 0 : 8,
        width: '100%',
        textAlign: 'left',
      }}
    >
      <span style={{ fontSize: 10 }}>{collapsed ? '▸' : '▾'}</span>
      {label}
    </button>
  )
}

function StudyTagsView() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery<StudyNote[]>({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })
  const [collapsed, setCollapsed] = useState(false)
  const [showForm, setShowForm] = useState(false)
  const [selectedNoteId, setSelectedNoteId] = useState<number | null>(null)
  const [conceptFilter, setConceptFilter] = useState('')
  const [sourceFilter, setSourceFilter] = useState('all')
  const [form, setForm] = useState(EMPTY_FORM)
  const [formError, setFormError] = useState<string | null>(null)
  const [warning, setWarning] = useState<string | null>(null)
  const visibleRows = data.filter(row => {
    const conceptMatches = !conceptFilter.trim() || row.concept_tag.toLowerCase().includes(conceptFilter.trim().toLowerCase())
    const sourceMatches = sourceFilter === 'all' || row.source === sourceFilter
    return conceptMatches && sourceMatches
  })

  const create = useMutation({
    mutationFn: (body: CreateStudyNoteRequest) => api.createStudyNote(body),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setShowForm(false)
      setSelectedNoteId(null)
      setForm(EMPTY_FORM)
      setFormError(null)
      setWarning(data.warnings?.length ? data.warnings[0] : null)
    },
  })
  const update = useMutation({
    mutationFn: ({ id, body }: { id: number; body: CreateStudyNoteRequest }) => api.updateStudyNote(id, body),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setShowForm(false)
      setSelectedNoteId(null)
      setForm(EMPTY_FORM)
      setFormError(null)
      setWarning(data.warnings?.length ? data.warnings[0] : null)
    },
  })
  const remove = useMutation({
    mutationFn: (id: number) => api.deleteStudyNote(id),
    onSuccess: data => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setWarning(data.warnings?.length ? data.warnings[0] : null)
    },
  })

  const resetForm = () => {
    setShowForm(false)
    setSelectedNoteId(null)
    setForm(EMPTY_FORM)
    setFormError(null)
  }

  const selectRow = (row: StudyNote) => {
    setSelectedNoteId(row.id)
    setForm({
      source: row.source,
      source_id: row.source_id,
      concept_tag: row.concept_tag,
      section_ref: row.section_ref ?? '',
      note_text: row.note_text ?? '',
    })
    setShowForm(true)
    setFormError(null)
  }

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!form.concept_tag.trim()) {
      setFormError('Concept tag is required')
      return
    }
    setFormError(null)
    const body = {
      source: form.source,
      source_id: form.source_id,
      concept_tag: form.concept_tag,
      section_ref: form.section_ref || undefined,
      note_text: form.note_text || undefined,
    }
    if (selectedNoteId !== null) {
      update.mutate({ id: selectedNoteId, body })
    } else {
      create.mutate(body)
    }
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div>
      <CollapseHeader
        label={`STUDY TAGS${data.length > 0 ? ` (${data.length})` : ''}`}
        collapsed={collapsed}
        onToggle={() => setCollapsed(c => !c)}
      />
      {collapsed ? null : data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags yet.</p>
      ) : (
        <>
          <div style={{ display: 'flex', gap: 6, marginBottom: 8 }}>
            <input
              value={conceptFilter}
              onChange={event => setConceptFilter(event.target.value)}
              placeholder="Filter concept"
              style={{ flex: 1, fontSize: 12, padding: '3px 6px' }}
            />
            <select
              value={sourceFilter}
              onChange={event => setSourceFilter(event.target.value)}
              style={{ fontSize: 12, padding: '3px 6px' }}
            >
              <option value="all">All sources</option>
              {SOURCE_OPTIONS.map(source => <option key={source} value={source}>{source}</option>)}
            </select>
          </div>
          {visibleRows.length === 0 ? (
            <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags match the filters.</p>
          ) : (
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
                  <th style={{ padding: '4px 8px' }}>Source</th>
                  <th style={{ padding: '4px 8px' }}>Concept</th>
                  <th style={{ padding: '4px 8px' }}>Section</th>
                  <th style={{ padding: '4px 8px' }}>Tagged</th>
                  <th style={{ padding: '4px 8px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {visibleRows.map(row => (
                  <tr
                    key={row.id}
                    onClick={() => selectRow(row)}
                    style={{
                      borderBottom: '1px solid #f1f5f9',
                      background: selectedNoteId === row.id ? '#eff6ff' : undefined,
                      cursor: 'pointer',
                    }}
                  >
                    <td style={{ padding: '4px 8px', color: '#475569' }}>{row.source}:{row.source_id}</td>
                    <td style={{ padding: '4px 8px' }}>{row.concept_tag}</td>
                    <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.section_ref ?? '-'}</td>
                    <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.tagged_at.slice(0, 10)}</td>
                    <td style={{ padding: '4px 8px' }}>
                      <button
                        onClick={(event) => {
                          event.stopPropagation()
                          remove.mutate(row.id)
                        }}
                        disabled={remove.isPending}
                        style={{ fontSize: 11, padding: '2px 6px', cursor: 'pointer' }}
                      >
                        Remove
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </>
      )}
      {!collapsed && <button
        onClick={() => {
          if (showForm) {
            resetForm()
          } else {
            setShowForm(true)
          }
        }}
        style={{ fontSize: 12, marginTop: 8, padding: '3px 10px', cursor: 'pointer' }}
      >
        {showForm ? 'Cancel' : 'Add Tag'}
      </button>}
      {!collapsed && showForm && (
        <form
          onSubmit={handleSubmit}
          onKeyDown={event => {
            if (event.key === 'Escape') resetForm()
          }}
          style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          {selectedNoteId !== null && (
            <div style={{ fontSize: 11, color: '#1d4ed8', fontWeight: 600 }}>
              Editing study tag #{selectedNoteId}
            </div>
          )}
          <select
            value={form.source}
            onChange={event => setForm(current => ({ ...current, source: event.target.value }))}
            style={{ fontSize: 12, padding: '3px 6px' }}
          >
            {SOURCE_OPTIONS.map(source => <option key={source} value={source}>{source}</option>)}
          </select>
          <input
            value={form.source_id}
            onChange={event => setForm(current => ({ ...current, source_id: event.target.value }))}
            placeholder="source_id"
            required
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <input
            value={form.concept_tag}
            onChange={event => setForm(current => ({ ...current, concept_tag: event.target.value }))}
            placeholder="concept_tag"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {formError && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>{formError}</span>
          )}
          <input
            value={form.section_ref}
            onChange={event => setForm(current => ({ ...current, section_ref: event.target.value }))}
            placeholder="section_ref (optional)"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          <textarea
            value={form.note_text}
            onChange={event => setForm(current => ({ ...current, note_text: event.target.value }))}
            placeholder="note (optional)"
            style={{ fontSize: 12, padding: '3px 6px' }}
          />
          {(create.error || update.error) && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>
              {((create.error || update.error) as Error).message}
            </span>
          )}
          <button
            type="submit"
            disabled={create.isPending || update.isPending}
            style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
          >
            {selectedNoteId !== null ? 'Save Edit' : 'Save'}
          </button>
        </form>
      )}
      {!collapsed && warning && (
        <div style={{
          color: '#92400e',
          background: '#fef3c7',
          padding: '4px 8px',
          borderRadius: 4,
          fontSize: 11,
          marginTop: 4,
        }}>
          {warning}
        </div>
      )}
    </div>
  )
}

function ChatHistoryView() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery<ChatSession[]>({
    queryKey: ['sessions'],
    queryFn: api.getSessions,
  })
  const [collapsed, setCollapsed] = useState(false)
  const remove = useMutation({
    mutationFn: (sessionId: string) => api.deleteSession(sessionId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['sessions'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div>
      <CollapseHeader
        label={`CHAT HISTORY${data.length > 0 ? ` (${data.length})` : ''}`}
        collapsed={collapsed}
        onToggle={() => setCollapsed(c => !c)}
      />
      {collapsed ? null : data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No chat sessions yet.</p>
      ) : (() => {
        const groups = new Map<string, ChatSession[]>()
        for (const session of data) {
          const key = session.topic_category ?? 'Uncategorized'
          const group = groups.get(key) ?? []
          group.push(session)
          groups.set(key, group)
        }
        const sorted = [...groups.entries()].sort(([a], [b]) => {
          if (a === 'Uncategorized') return 1
          if (b === 'Uncategorized') return -1
          return a.localeCompare(b)
        })
        return (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
            {sorted.map(([category, sessions]) => (
              <div key={category}>
                <div style={{
                  fontSize: 10,
                  fontWeight: 700,
                  color: '#94a3b8',
                  letterSpacing: '0.06em',
                  textTransform: 'uppercase',
                  marginBottom: 4,
                }}>
                  {category}
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {sessions.map(session => (
                    <div key={session.id} style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                        <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{session.inferred_topic}</span>
                        <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexShrink: 0, marginLeft: 8 }}>
                          <span style={{ fontSize: 11, color: '#94a3b8' }}>{session.started_at.slice(0, 10)}</span>
                          <button
                            onClick={() => remove.mutate(session.session_id)}
                            disabled={remove.isPending}
                            style={{ fontSize: 11, padding: '1px 6px', cursor: 'pointer' }}
                          >
                            Delete
                          </button>
                        </div>
                      </div>
                      <div style={{ fontSize: 11, color: '#64748b', display: 'flex', gap: 12 }}>
                        <span>{session.agent_mode}</span>
                        <span>{session.message_count} messages</span>
                      </div>
                      {session.summary_preview && (
                        <details style={{ marginTop: 6 }}>
                          <summary style={{ fontSize: 11, color: '#2563eb', cursor: 'pointer' }}>
                            Session summary
                          </summary>
                          <p style={{ fontSize: 11, color: '#475569', marginTop: 4, marginBottom: 0 }}>
                            {session.summary_preview}
                          </p>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
        )
      })()}
    </div>
  )
}

function PlansView() {
  const queryClient = useQueryClient()
  const { data: plans = [] } = useQuery({ queryKey: ['plans'], queryFn: () => api.getPlans() })
  const [selectedId, setSelectedId] = useState<number | null>(null)

  const { data: detail } = useQuery({
    queryKey: ['plan', selectedId],
    queryFn: () => api.getPlan(selectedId as number),
    enabled: selectedId != null,
  })

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ['plans'] })
    if (selectedId != null) queryClient.invalidateQueries({ queryKey: ['plan', selectedId] })
  }

  const confirmPlan = useMutation({ mutationFn: (id: number) => api.confirmPlan(id), onSuccess: invalidate })
  const deletePlan = useMutation({
    mutationFn: (id: number) => api.deletePlan(id),
    onSuccess: () => {
      setSelectedId(null)
      invalidate()
    },
  })
  const stepProgress = useMutation({
    mutationFn: ({ stepId, progress }: { stepId: number; progress: string }) =>
      api.patchPlanStep(selectedId as number, stepId, { progress }),
    onSuccess: invalidate,
  })
  const stepLifecycle = useMutation({
    mutationFn: ({ stepId, action }: { stepId: number; action: 'confirm' | 'dismiss' }) =>
      api.patchPlanStep(selectedId as number, stepId, { lifecycle_action: action }),
    onSuccess: invalidate,
  })
  const confirmChanges = useMutation({
    mutationFn: (id: number) => api.confirmPlanChanges(id),
    onSuccess: invalidate,
  })
  const dismissChanges = useMutation({
    mutationFn: (id: number) => api.dismissPlanChanges(id),
    onSuccess: invalidate,
  })

  if (plans.length === 0) {
    return <div style={{ fontSize: 12, color: '#64748b' }}>No learning plans yet.</div>
  }

  return (
    <div>
      {plans.map(plan => (
        <PlanCard
          key={plan.id}
          plan={plan}
          selected={plan.id === selectedId}
          onSelect={() => setSelectedId(plan.id === selectedId ? null : plan.id)}
          onConfirm={() => confirmPlan.mutate(plan.id)}
          onDismiss={() => deletePlan.mutate(plan.id)}
        />
      ))}
      {detail && (
        <PlanDetailView
          plan={detail}
          onStepProgress={(stepId, progress) => stepProgress.mutate({ stepId, progress })}
          onStepLifecycle={(stepId, action) => stepLifecycle.mutate({ stepId, action })}
          onConfirmChanges={() => confirmChanges.mutate(detail.id)}
          onDismissChanges={() => dismissChanges.mutate(detail.id)}
        />
      )}
    </div>
  )
}

export default function StudyLogPanel() {
  const [view, setView] = useState<View>('study-tags')

  return (
    <div style={{ padding: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 12 }}>
        <h4 style={{ margin: 0, fontSize: 13, fontWeight: 700, color: '#1e293b' }}>Study Log</h4>
        <select
          value={view}
          onChange={e => setView(e.target.value as View)}
          style={{ padding: '3px 6px', fontSize: 11, border: '1px solid #cbd5e1', borderRadius: 4 }}
        >
          <option value="study-tags">Study Tags</option>
          <option value="chat-history">Chat History</option>
          <option value="plans">Plans</option>
        </select>
      </div>
      {view === 'study-tags' && <StudyTagsView />}
      {view === 'chat-history' && <ChatHistoryView />}
      {view === 'plans' && <PlansView />}
    </div>
  )
}
