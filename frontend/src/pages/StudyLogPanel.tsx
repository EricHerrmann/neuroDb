import { useState, type FormEvent } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'
import type { ChatSession, CreateStudyNoteRequest, StudyNote } from '../api/types'

type View = 'study-tags' | 'chat-history'

function StudyTagsView() {
  const queryClient = useQueryClient()
  const { data = [], isLoading, isError, error } = useQuery<StudyNote[]>({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    source: 'openneuro',
    source_id: '',
    concept_tag: '',
    section_ref: '',
    note_text: '',
  })
  const [formError, setFormError] = useState<string | null>(null)
  const [warning, setWarning] = useState<string | null>(null)

  const create = useMutation({
    mutationFn: (body: CreateStudyNoteRequest) => api.createStudyNote(body),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ['study-log'] })
      setShowForm(false)
      setForm({ source: 'openneuro', source_id: '', concept_tag: '', section_ref: '', note_text: '' })
      setFormError(null)
      setWarning(data.warnings?.length ? data.warnings[0] : null)
    },
  })

  const handleSubmit = (event: FormEvent) => {
    event.preventDefault()
    if (!form.concept_tag.trim()) {
      setFormError('Concept tag is required')
      return
    }
    setFormError(null)
    create.mutate({
      source: form.source,
      source_id: form.source_id,
      concept_tag: form.concept_tag,
      section_ref: form.section_ref || undefined,
      note_text: form.note_text || undefined,
    })
  }

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div>
      {data.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags yet.</p>
      ) : (
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
          <thead>
            <tr style={{ borderBottom: '2px solid #e2e8f0', textAlign: 'left' }}>
              <th style={{ padding: '4px 8px' }}>Source</th>
              <th style={{ padding: '4px 8px' }}>Concept</th>
              <th style={{ padding: '4px 8px' }}>Section</th>
              <th style={{ padding: '4px 8px' }}>Tagged</th>
            </tr>
          </thead>
          <tbody>
            {data.map(row => (
              <tr key={row.id} style={{ borderBottom: '1px solid #f1f5f9' }}>
                <td style={{ padding: '4px 8px', color: '#475569' }}>{row.source}:{row.source_id}</td>
                <td style={{ padding: '4px 8px' }}>{row.concept_tag}</td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.section_ref ?? '-'}</td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>{row.tagged_at.slice(0, 10)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
      <button
        onClick={() => setShowForm(value => !value)}
        style={{ fontSize: 12, marginTop: 8, padding: '3px 10px', cursor: 'pointer' }}
      >
        {showForm ? 'Cancel' : 'Add Tag'}
      </button>
      {showForm && (
        <form
          onSubmit={handleSubmit}
          style={{ marginTop: 8, display: 'flex', flexDirection: 'column', gap: 6 }}
        >
          <select
            value={form.source}
            onChange={event => setForm(current => ({ ...current, source: event.target.value }))}
            style={{ fontSize: 12, padding: '3px 6px' }}
          >
            <option value="openneuro">openneuro</option>
            <option value="pubmed">pubmed</option>
            <option value="arxiv">arxiv</option>
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
          {create.error && (
            <span style={{ fontSize: 11, color: '#dc2626' }}>
              {(create.error as Error).message}
            </span>
          )}
          <button
            type="submit"
            disabled={create.isPending}
            style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}
          >
            Save
          </button>
        </form>
      )}
      {warning && (
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
  const { data = [], isLoading, isError, error } = useQuery<ChatSession[]>({
    queryKey: ['sessions'],
    queryFn: api.getSessions,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }
  if (data.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: 13 }}>No chat sessions yet.</p>
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
      {data.map(session => (
        <div key={session.id} style={{ padding: '8px 10px', background: '#f8fafc', border: '1px solid #e2e8f0', borderRadius: 6 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
            <span style={{ fontSize: 12, fontWeight: 600, color: '#1e293b' }}>{session.inferred_topic}</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>{session.started_at.slice(0, 10)}</span>
          </div>
          <div style={{ fontSize: 11, color: '#64748b', display: 'flex', gap: 12 }}>
            <span>{session.agent_mode}</span>
            <span>{session.message_count} messages</span>
          </div>
          {session.summary_preview && (
            <p style={{ fontSize: 11, color: '#475569', marginTop: 4, marginBottom: 0 }}>{session.summary_preview}</p>
          )}
        </div>
      ))}
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
        </select>
      </div>
      {view === 'study-tags' ? <StudyTagsView /> : <ChatHistoryView />}
    </div>
  )
}
