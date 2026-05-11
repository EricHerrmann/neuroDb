import { useQuery } from '@tanstack/react-query'

import { api } from '../api/client'

export default function StudyLogPanel() {
  const { data = [], isLoading, isError, error } = useQuery({
    queryKey: ['study-log'],
    queryFn: api.getStudyLog,
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Study Tags ({data.length})</h4>
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
                <td style={{ padding: '4px 8px', color: '#475569' }}>
                  {row.source}:{row.source_id}
                </td>
                <td style={{ padding: '4px 8px' }}>{row.concept_tag}</td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>
                  {row.section_ref ?? '-'}
                </td>
                <td style={{ padding: '4px 8px', color: '#94a3b8' }}>
                  {row.tagged_at.slice(0, 10)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  )
}
