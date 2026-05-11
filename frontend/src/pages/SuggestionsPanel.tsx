import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { api } from '../api/client'

export default function SuggestionsPanel() {
  const queryClient = useQueryClient()
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['suggestions'],
    queryFn: api.getSuggestions,
  })
  const dismiss = useMutation({
    mutationFn: (id: number) => api.dismissImportItem(id),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ['suggestions'] }),
  })

  if (isLoading) return <div style={{ padding: 12 }}>Loading...</div>
  if (isError) {
    return <div style={{ padding: 12, color: '#dc2626' }}>Error: {(error as Error).message}</div>
  }

  const { import_queue, source_suggestions } = data!
  return (
    <div style={{ padding: 12 }}>
      <h4 style={{ marginBottom: 8 }}>Dataset Import Requests</h4>
      {import_queue.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending import suggestions.</p>
      ) : import_queue.map(item => (
        <div
          key={item.id}
          style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}
        >
          <strong>{item.title ?? item.source_id}</strong>
          {' '}
          <code style={{ fontSize: 11 }}>{item.source}:{item.source_id}</code>
          {item.chapter_ref && (
            <div style={{ fontSize: 12, color: '#64748b' }}>While reading: {item.chapter_ref}</div>
          )}
          {item.reason && (
            <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
          )}
          <button
            onClick={() => dismiss.mutate(item.id)}
            disabled={dismiss.isPending}
            style={{ fontSize: 12, marginTop: 6, padding: '3px 10px', cursor: 'pointer' }}
          >
            Dismiss
          </button>
        </div>
      ))}

      <hr style={{ margin: '12px 0', border: 'none', borderTop: '1px solid #e2e8f0' }} />

      <h4 style={{ marginBottom: 8 }}>Connector Requests</h4>
      {source_suggestions.length === 0 ? (
        <p style={{ color: '#94a3b8', fontSize: 13 }}>No pending source suggestions.</p>
      ) : source_suggestions.map(item => (
        <div
          key={item.id}
          style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: 12, marginBottom: 8 }}
        >
          <strong>{item.display_name ?? item.reference ?? '-'}</strong>
          {' '}
          <code style={{ fontSize: 11 }}>({item.suggestion_type})</code>
          {item.reason && (
            <p style={{ fontSize: 12, margin: '4px 0', color: '#475569' }}>{item.reason}</p>
          )}
        </div>
      ))}
    </div>
  )
}
