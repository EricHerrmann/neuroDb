import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'

const MODES = [
  { value: 'local_db', label: 'Local DB' },
  { value: 'external_db', label: 'External DB' },
  { value: 'neuro_tutor', label: 'Neuro Tutor' },
  { value: 'neuro_research', label: 'Neuro Research' },
]

export default function Sidebar({ agentMode }: { agentMode: string }) {
  const queryClient = useQueryClient()
  const { data: sessions = [] } = useQuery({
    queryKey: ['sessions'],
    queryFn: api.getSessions,
  })

  const setMode = useMutation({
    mutationFn: (mode: string) => api.setAgentMode(mode),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['preferences'] }),
  })

  return (
    <div style={{
      width: 180,
      flexShrink: 0,
      borderRight: '1px solid #e2e8f0',
      padding: 12,
      overflowY: 'auto',
      background: '#f8fafc',
    }}>
      <div>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 4 }}>
          AGENT MODE
        </div>
        <select
          value={agentMode}
          onChange={event => setMode.mutate(event.target.value)}
          style={{
            width: '100%',
            padding: '4px 6px',
            fontSize: 12,
            border: '1px solid #cbd5e1',
            borderRadius: 4,
          }}
        >
          {MODES.map(mode => <option key={mode.value} value={mode.value}>{mode.label}</option>)}
        </select>
      </div>
      <div style={{ marginTop: 16 }}>
        <div style={{ fontSize: 11, fontWeight: 700, color: '#475569', marginBottom: 4 }}>
          PREVIOUS SESSIONS
        </div>
        {sessions.length === 0 ? (
          <div style={{ fontSize: 11, color: '#94a3b8' }}>No sessions yet</div>
        ) : sessions.map(session => (
          <div
            key={session.id}
            style={{ padding: '4px 0', borderBottom: '1px solid #e2e8f0' }}
          >
            <div style={{ fontSize: 11, color: '#0f172a', lineHeight: 1.3 }}>
              {session.inferred_topic}
            </div>
            <div style={{ fontSize: 10, color: '#94a3b8' }}>
              {session.started_at.slice(0, 10)} · {session.message_count} msgs
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
