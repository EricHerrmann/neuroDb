import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'
import type { ChatSession, StudyNote } from '../api/types'

type View = 'study-tags' | 'chat-history'

function StudyTagsView() {
  const { data = [], isLoading, isError, error } = useQuery<StudyNote[]>({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }
  if (data.length === 0) {
    return <p style={{ color: '#94a3b8', fontSize: 13 }}>No study tags yet.</p>
  }

  return (
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
